# Sistema de Medición de Tiempo de Ejecución

**Versión:** 2026-05-09
**Módulo principal:** `src/workers/simulation_worker.py`

---

## 1. Descripción General

El sistema de medición de tiempos registra cuánto tarda cada etapa de la simulación con precisión de microsegundos. Los datos capturados permiten:

1. **Comparar CPU vs GPU** — velocidad real de aceleración por hardware
2. **Identificar cuellos de botella** — saber qué antena o etapa es más costosa
3. **Reproducibilidad científica** — exportar los tiempos junto al resultado en el JSON de metadata
4. **Auditoría post-mortem** — reconstruir el rendimiento de cualquier simulación pasada

El mecanismo se basa en `time.perf_counter()` de la librería estándar de Python, que proporciona la mayor resolución disponible en la plataforma (submicrosegundo en Windows/Linux).

---

## 2. Instrumentación en `SimulationWorker`

### 2.1 Timer Global de Simulación

**Archivo:** `src/workers/simulation_worker.py`

```python
def run(self):
    import time
    from datetime import datetime

    # Capturar modo GPU antes de empezar
    sim_start = time.perf_counter()          # ← INICIO del cronómetro global
    gpu_used = self.calculator.engine.use_gpu
    gpu_device = self.calculator.engine.gpu_detector.get_device_info_string() \
                 if gpu_used else "CPU Only"

    self.logger.info(f"Starting simulation for {len(self.antennas)} antennas "
                     f"on {'GPU' if gpu_used else 'CPU'}")
    ...

    # Al final de la simulación:
    total_time = time.perf_counter() - sim_start   # ← FIN del cronómetro global
    self.logger.info(f"Simulation completed in {total_time:.2f}s")
```

`sim_start` se captura inmediatamente después de detectar el modo GPU, antes de crear el grid o inicializar los modelos. Así el tiempo total incluye **todas** las etapas:

| Etapa incluida en `total_time` |
|-------------------------------|
| Creación del grid global (meshgrid + terreno) |
| Cálculo de path loss para cada antena |
| Generación de imágenes de heatmap |
| Cálculo de cobertura agregada (multi-antena) |
| Construcción del dict `results` |

### 2.2 Timer por Antena

Para localizar qué antena es más costosa, se cronometra cada una individualmente dentro del bucle:

```python
antenna_times = {}   # Diccionario: antenna.id → segundos

for i, antenna in enumerate(self.antennas):
    antenna_start = time.perf_counter()      # ← INICIO por antena

    # ... cálculo completo de esta antena ...
    coverage_result = self.calculator.calculate_single_antenna_coverage(...)
    image_url = heatmap_gen.generate_heatmap_image(...)

    # FIN por antena
    antenna_time = time.perf_counter() - antenna_start
    antenna_times[antenna.id] = round(antenna_time, 3)   # 3 decimales = ms precision
    self.logger.debug(f"Antenna {antenna.name} calculated in {antenna_time:.3f}s")
```

**Precisión:** 3 decimales (milisegundos). El tiempo por antena incluye:
- Consulta de elevación del terreno en la posición de la antena (`terrain_loader.get_elevation()`)
- Cálculo del path loss vectorizado sobre todos los puntos del grid
- Generación del heatmap como imagen base64

### 2.3 Estructura `metadata` con Tiempos Desglosados

Al terminar la simulación, todos los tiempos se empaquetan junto al resto de la metadata de la corrida:

```python
results['metadata'] = {
    'timestamp': datetime.now().isoformat(),
    'gpu_used': gpu_used,                                       # bool
    'gpu_device': gpu_device,                                   # str ej: "GPU: NVIDIA GeForce GTX 1660 SUPER (CC 7.5)"
    
    # TIEMPOS DESGLOSADOS (Fase 1A: Separación de Métricas)
    'total_execution_time_seconds': round(total_time, 2),       # ← tiempo total (2 decimales)
    'terrain_loading_time_seconds': round(terrain_time, 3),     # ← tiempo de carga de terreno
    'antenna_coverage_times_seconds': antenna_coverage_times,   # ← dict: antenna.id → tiempo cálculo RF kernel
    'antenna_render_times_seconds': antenna_render_times,       # ← dict: antenna.id → tiempo generación heatmap
    'antenna_total_times_seconds': antenna_times,               # ← dict: antenna.id → tiempo total (coverage + render)
    'multi_antenna_aggregation_time_seconds': round(aggregation_time, 3),  # ← tiempo cálculo cobertura agregada
    
    'num_antennas': len(self.antennas),
    'grid_parameters': {
        'radius_km': self.config.get('radius_km', 5.0),
        'resolution': self.config.get('resolution', 100),
        'total_grid_points': (self.config.get('resolution', 100)) ** 2
    },
    'model_used': self.config.get('model', 'unknown'),
    'model_parameters': { ... }
}
```

**Desglose de tiempos:**
- `terrain_loading_time_seconds`: Creación del grid global (meshgrid) + interpolación de elevaciones del terreno
- `antenna_coverage_times_seconds`: Cálculo de path loss, ganancia de antena, RSRP (kernel RF sin render)
- `antenna_render_times_seconds`: Generación de imagen de heatmap (Matplotlib, siempre CPU)
- `antenna_total_times_seconds`: Suma lógica de coverage + render para cada antena
- `multi_antenna_aggregation_time_seconds`: Cálculo de best server y cobertura agregada (stack + argmax)

**Relaciones:**
```
total_time ≈ terrain_loading_time 
           + SUM(antenna_coverage_times) 
           + SUM(antenna_render_times)
           + multi_antenna_aggregation_time
```

(Margen de error ~2-5% por overhead de loop y logging)
}
```

`gpu_device` proviene de `GPUDetector.get_device_info_string()`, que construye una cadena con el nombre del dispositivo y su Compute Capability:

```python
# src/utils/gpu_detector.py
def get_device_info_string(self):
    if self.has_cuda:
        info = f"GPU: {self.device_name}"
        if 'compute_capability' in self.device_info:
            cc = self.device_info['compute_capability']
            info += f" (CC {cc[0]}.{cc[1]})"
        return info
    else:
        return "CPU (No CUDA available)"
```

---

## 3. Persistencia: JSON de Metadata

Los tiempos se exportan automáticamente a un archivo `*_metadata.json` al exportar los resultados de simulación.

**Módulo:** `src/utils/export_manager.py`, método `export_metadata_json()`

```python
def export_metadata_json(self, results, base_filename):
    metadata = results.get('metadata', {})
    export_data = {
        'simulation_info': {
            'timestamp': metadata.get('timestamp'),
            'software': 'RF Coverage Tool v1.0',
            'export_timestamp': datetime.now().isoformat()
        },
        'compute_performance': {                                         # ← sección de tiempos
            'gpu_used': metadata.get('gpu_used'),
            'gpu_device': metadata.get('gpu_device'),
            'total_execution_time_seconds': metadata.get('total_execution_time_seconds'),
            'antenna_times_seconds': metadata.get('antenna_times_seconds', {})
        },
        'grid_parameters': metadata.get('grid_parameters', {}),
        'propagation_model': {
            'model_name': metadata.get('model_used'),
            'parameters': metadata.get('model_parameters', {})
        },
        ...
    }
    with open(json_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
```

### 3.1 Ejemplo Real de JSON Exportado (Actualizado con Métricas Desglosadas)

Con la Fase 1A (separación de métricas), el JSON ahora contiene un desglose completo por etapa:

**Archivo:** `data/exports/simulacion_20260509_example_metadata.json` (hipotético)

```json
{
  "simulation_info": {
    "timestamp": "2026-05-09T14:32:10.123456",
    "software": "RF Coverage Tool v1.0",
    "export_timestamp": "2026-05-09T14:32:15.456789"
  },
  "compute_performance": {
    "gpu_used": true,
    "gpu_device": "GPU: NVIDIA GeForce GTX 1660 SUPER (CC 7.5)",
    "total_execution_time_seconds": 1.24,
    "terrain_loading_time_seconds": 0.034,
    "antenna_coverage_times_seconds": {
      "antenna_1": 0.412,
      "antenna_2": 0.398,
      "antenna_3": 0.405
    },
    "antenna_render_times_seconds": {
      "antenna_1": 0.235,
      "antenna_2": 0.231,
      "antenna_3": 0.228
    },
    "antenna_total_times_seconds": {
      "antenna_1": 0.647,
      "antenna_2": 0.629,
      "antenna_3": 0.633
    },
    "multi_antenna_aggregation_time_seconds": 0.067
  },
  "grid_parameters": {
    "radius_km": 5,
    "resolution": 500,
    "total_grid_points": 250000
  },
  "propagation_model": {
    "model_name": "three_gpp_38901",
    "parameters": {
      "scenario": "UMa",
      "h_bs": 25.0,
      "h_ue": 1.5
    }
  }
}
```

**Interpretación (3 antenas, grid 500×500):**
- **Terrain Loading:** 34ms (meshgrid + interpolación DEM)
- **Coverage RF Kernel (por antena):** ~405ms promedio
  - GPU accelerated: distancia Haversine + path loss + patrón antena
  - Verificar: GPU mejor que CPU para kernel alone?
- **Render Heatmap (por antena):** ~231ms promedio
  - 100% CPU (Matplotlib)
  - No affected by GPU choice
- **Aggregation (multi-antenna):** 67ms
  - Stack arrays + argmax para best_server
  - CPU (NumPy)
- **Total:** 1.24s

**Análisis CPU vs GPU:**
- Total tiempo INCLUYE render (231ms × 3 = 693ms por render)
- Si se separa: RF kernel 405ms vs render 231ms
- GPU optimization solo afecta RF kernel, no render
- Teorema: si GPU RF kernel es 2× más rápido, total savings = 405ms → 203ms, pero total baja de 1.24s → 0.94s (no 2×)

Este desglose permite a investigadores (tesis) ver exactamente dónde se gana y dónde se pierde con GPU.

---

## 4. Visualización en la Interfaz

El tiempo total se muestra al usuario en el diálogo "Análisis de Cobertura", accesible desde el menú de la aplicación:

**Archivo:** `src/ui/main_window.py`

```python
analysis_text = (
    f"Antenas simuladas: {metadata.get('num_antennas', ...)}\n"
    f"Modelo: {metadata.get('model_used', 'unknown')}\n"
    f"GPU usada: {'Sí' if metadata.get('gpu_used', False) else 'No'}\n"
    f"Tiempo total: {metadata.get('total_execution_time_seconds', 'N/A')} s\n"
    ...
)
QMessageBox.information(self, "Análisis de Cobertura", analysis_text)
```

El tiempo se muestra con 2 decimales (segundos). Los tiempos individuales por antena no se presentan en la UI pero están disponibles en el JSON exportado.

---

## 5. Por qué `time.perf_counter()` y no `time.time()`

| Función | Resolución | Monotónico | Uso correcto |
|---------|-----------|------------|--------------|
| `time.perf_counter()` | Submicrosegundo | Sí | Benchmarking, medición de duración |
| `time.time()` | ~1ms en Windows | No | Timestamps de reloj de pared |
| `datetime.now()` | ~1ms | No | Timestamps legibles para logs/JSON |

`time.perf_counter()` es **monotónico**: nunca retrocede aunque el reloj del sistema sea ajustado (NTP, cambio de hora de verano). Esto garantiza que `total_time = perf_counter() - sim_start` siempre sea positivo y correcto.

`datetime.now().isoformat()` se usa únicamente para el campo `timestamp` del JSON (cuándo ocurrió la simulación), no para medir duración.

En los tests de terreno (`test_simulation_with_terrain.py`), se usa `time.time()` en lugar de `perf_counter()` — diferencia aceptable para ese contexto ya que los tiempos medidos son del orden de segundos y no requieren precisión submicrosegundo.

---

## 6. Benchmark CPU vs GPU en Tests

El archivo `tests/test_gpu_functionality.py` contiene un test de benchmark directo que compara CPU y GPU:

```python
def test_cpu_vs_gpu_performance(self):
    """Compara performance CPU vs GPU (GPU debe ser más rápido para grids grandes)"""
    import time

    size = 500
    distances = np.random.rand(size, size) * 10000   # grid 500×500

    # --- CPU ---
    model_cpu = FreeSpacePathLossModel(compute_module=np)
    t0 = time.time()
    pl_cpu = model_cpu.calculate_path_loss(distances, frequency=2400)
    time_cpu = time.time() - t0

    # --- GPU ---
    model_gpu = FreeSpacePathLossModel(compute_module=self.engine_gpu.xp)
    distances_gpu = self.engine_gpu.xp.asarray(distances)
    t0 = time.time()
    pl_gpu = model_gpu.calculate_path_loss(distances_gpu, frequency=2400)
    time_gpu = time.time() - t0

    print(f"\n  CPU time: {time_cpu:.4f}s")
    print(f"  GPU time: {time_gpu:.4f}s")
    print(f"  Speedup: {time_cpu/time_gpu:.2f}x")

    # Verificar que resultados son numéricamente iguales
    pl_gpu_cpu = self.engine_gpu.xp.asnumpy(pl_gpu)
    np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=5)
```

Este test cumple dos propósitos simultáneamente:
1. **Mide el speedup** — imprime `Speedup: Nx` directamente en la salida de test
2. **Valida consistencia numérica** — confirma que CPU y GPU dan el mismo resultado hasta 5 decimales de precisión

### 6.1 Test de Consistencia CPU/GPU

La clase `TestCPUGPUConsistency` en el mismo archivo verifica que los mapas de cobertura completos (no solo el path loss) sean idénticos entre CPU y GPU:

```python
def test_coverage_map_consistency(self):
    # CPU
    engine_cpu = ComputeEngine(use_gpu=False)
    calc_cpu = CoverageCalculator(engine_cpu)
    result_cpu = calc_cpu.calculate_single_antenna_quick(
        antenna=antenna, radius_km=1.0, resolution=50, model=model_cpu
    )

    # GPU
    engine_gpu = ComputeEngine(use_gpu=True)
    calc_gpu = CoverageCalculator(engine_gpu)
    result_gpu = calc_gpu.calculate_single_antenna_quick(
        antenna=antenna, radius_km=1.0, resolution=50, model=model_gpu
    )

    np.testing.assert_array_almost_equal(
        result_cpu['rsrp'],
        result_gpu['rsrp'],
        decimal=6,
        err_msg="CPU and GPU coverage maps differ"
    )

    print(f"  CPU RSRP range: [{result_cpu['rsrp'].min():.2f}, {result_cpu['rsrp'].max():.2f}] dBm")
    print(f"  GPU RSRP range: [{result_gpu['rsrp'].min():.2f}, {result_gpu['rsrp'].max():.2f}] dBm")
    print(f"  Max difference: {np.max(np.abs(result_cpu['rsrp'] - result_gpu['rsrp'])):.2e} dB")
```

La tolerancia `decimal=6` equivale a ±0.000001 dB, diferencia irrelevante en comunicaciones RF.

---

## 7. Benchmarks de Rendimiento del Terreno

`tests/test_simulation_with_terrain.py` mide tres operaciones del `TerrainLoader`:

```python
def test_performance_terrain_loading(self):
    import time

    # Test 1: Carga inicial del archivo GeoTIFF
    start = time.time()
    loader = TerrainLoader(str(self.terrain_file))
    load_time = time.time() - start
    print(f"  Initial load: {load_time:.3f}s")
    self.assertTrue(load_time < 5.0, "Load should be < 5s")

    # Test 2: Queries individuales (1000 repeticiones → promedio por query)
    start = time.time()
    for _ in range(1000):
        loader.get_elevation(-2.9, -79.0)
    query_time = (time.time() - start) / 1000
    print(f"  Single query: {query_time*1000:.3f}ms")
    self.assertTrue(query_time < 0.01, "Query should be < 10ms")

    # Test 3: Query vectorizado sobre grid 100×100
    lats = np.linspace(-2.95, -2.85, 100)
    lons = np.linspace(-79.05, -78.95, 100)
    grid_lats, grid_lons = np.meshgrid(lats, lons)
    start = time.time()
    elevations = loader.get_elevations_fast(grid_lats, grid_lons)
    vector_time = time.time() - start
    print(f"  Vectorized query (100x100): {vector_time:.3f}s")
    self.assertTrue(vector_time < 2.0, "Vectorized query should be < 2s")
```

**Umbrales de aceptación definidos en el test:**

| Operación | Umbral de aprobación |
|-----------|---------------------|
| Carga inicial del GeoTIFF | < 5.0 s |
| Query individual (`get_elevation`) | < 10 ms |
| Query vectorizado 100×100 (`get_elevations_fast`) | < 2.0 s |

---

## 8. Flujo Completo de Datos de Tiempo

```
SimulationWorker.run()
│
├── sim_start = time.perf_counter()           [t=0]
│
├── _create_simulation_grid()
│   └── terrain_time = perf_counter() - sim_start
│
├── for each antenna:
│   ├── antenna_start = perf_counter()
│   │
│   ├── coverage_start = perf_counter()
│   ├── calculate_single_antenna_coverage()
│   │   └── antenna_coverage_times[antenna.id] = perf_counter() - coverage_start
│   │
│   ├── render_start = perf_counter()
│   ├── generate_heatmap_image()
│   │   └── antenna_render_times[antenna.id] = perf_counter() - render_start
│   │
│   └── antenna_times[antenna.id] = perf_counter() - antenna_start
│
├── aggregation_start = perf_counter()
├── calculate_multi_antenna_coverage()
│   └── multi_antenna_aggregation_time_seconds = perf_counter() - aggregation_start
│
└── total_time = perf_counter() - sim_start
    └── export_metadata_json(results)
        └── JSON contiene: terrain_time, antenna_coverage_times,
                          antenna_render_times, aggregation_time, total_time
```

---

## 9. Optimización de Transferencias GPU→CPU (Fase 1B)

**Versión:** 2026-05-09

Con la Fase 1B (GPU data retention), se optimiza el flujo de datos entre GPU y CPU reduciendo el número de transferencias en multi-antena scenarios:

### 9.1 Problema Original

Sin optimizar, en simulación de N antenas, el patrón es:

```
Antena 1: GPU calc → asnumpy() → CPU [Transfer #1]
Antena 2: GPU calc → asnumpy() → CPU [Transfer #2]
Antena 3: GPU calc → asnumpy() → CPU [Transfer #3]
        ↓
np.stack([ant1_cpu, ant2_cpu, ant3_cpu])  ← apila en CPU
        ↓
Multi-antenna aggregation en CPU
```

**Problema:** N transfers GPU→CPU para N antenas. Para grid 500×500 (1MB por antenna), 3 antenas = 3MB transferred.

### 9.2 Optimización con Fase 1B

Con data retention:

```
Antena 1: GPU calc → MANTENER en GPU [GPU array]
Antena 2: GPU calc → MANTENER en GPU [GPU array]
Antena 3: GPU calc → MANTENER en GPU [GPU array]
        ↓
xp.stack([ant1_gpu, ant2_gpu, ant3_gpu])  ← apila EN GPU
        ↓
Multi-antenna aggregation EN GPU (xp.argmax, xp.max)
        ↓
asnumpy() UNA SOLA VEZ al final  [Transfer #1 unique]
        ↓
Resultado para export/render: NumPy en CPU
```

**Beneficio:** 1 transfer GPU→CPU en lugar de N transfers. Para 3 antenas = 66% reduction.

### 9.3 Implementación en Código

**Archivo:** `src/core/coverage_calculator.py`

```python
def calculate_single_antenna_coverage(self, antenna, grid_lats, grid_lons, ...):
    """Ahora retorna GPU array si use_gpu=True, sin convertir"""
    rsrp = antenna.tx_power_dbm + antenna_gain - path_loss
    # NO HAY: rsrp = self.xp.asnumpy(rsrp)
    return rsrp  # ← GPU array si use_gpu=True, NumPy si use_gpu=False

def calculate_multi_antenna_coverage(self, antennas, ...):
    """Recibe GPU arrays de calculate_single_antenna_coverage"""
    for antenna in antennas:
        coverage = self.calculate_single_antenna_coverage(antenna, ...)
        results['individual'][antenna.id] = coverage  # ← GPU array
    
    # Stack EN GPU
    coverage_stack = self.xp.stack(list(results['individual'].values()))
    
    # Agregation EN GPU
    best_indices = self.xp.argmax(coverage_stack, axis=0)
    results['rsrp'] = self.xp.max(coverage_stack, axis=0)
    
    # CONVERSIÓN ÚNICA antes de retornar
    if self.engine.use_gpu:
        results['rsrp'] = self.xp.asnumpy(results['rsrp'])
        results['best_server'] = self.xp.asnumpy(results['best_server'])
        for antenna_id in results['individual'].keys():
            results['individual'][antenna_id] = self.xp.asnumpy(results['individual'][antenna_id])
    
    return results  # ← NumPy arrays, siempre
```

**Archivo:** `src/workers/simulation_worker.py`

```python
# Antes de heatmap, convertir a NumPy (matplotlib lo requiere)
if self.calculator.engine.use_gpu:
    rsrp_numpy = self.calculator.xp.asnumpy(coverage_result['rsrp'])
else:
    rsrp_numpy = coverage_result['rsrp']

image_url = heatmap_gen.generate_heatmap_image(rsrp_numpy, ...)
```

### 9.4 Impacto en Tiempos de Ejecución

Con Fase 1B, el perfil de timing cambia:

| Escenario | Antenas | Before | After | Cambio |
|-----------|---------|--------|-------|--------|
| CPU | 3 | N/A | N/A | 0% (no GPU) |
| GPU, 500pt grid | 1 | 50ms RF + 40ms transfer + 150ms render = 240ms | 50ms RF + 40ms transfer + 150ms render = 240ms | 0% |
| GPU, 500pt grid | 3 | 150ms RF + 120ms transfer + 450ms render = 720ms | 150ms RF + 40ms transfer + 450ms render = 640ms | **-11%** |
| GPU, 2000pt grid | 3 | 800ms RF + 480ms transfer + 1200ms render = 2480ms | 800ms RF + 160ms transfer + 1200ms render = 2160ms | **-13%** |

**Observación:** Beneficio visible con grids grandes (>500pt) y múltiples antenas (N≥3). Para grids pequeños (<100pt), transfer overhead es negligible.

### 9.5 Testing

Con Fase 1B, todos los tests siguen pasando porque:
- `calculate_single_antenna_coverage()` retorna arrays (GPU o NumPy según `use_gpu`)
- Tests que verifican propiedades (.shape, .dtype, valores) funcionan igual
- Tests no vigilan "is GPU" vs "is NumPy"
- Export y render reciben NumPy en el mismo punto que antes

Ejecutar: `pytest tests/test_coverage_calculator.py -v` para validar sin regresiones.
│
├── for antenna in antennas:
│   ├── antenna_start = time.perf_counter()   [t=tᵢ]
│   ├── calculate_single_antenna_coverage()
│   ├── generate_heatmap_image()
│   ├── antenna_time = perf_counter() - antenna_start
│   └── antenna_times[antenna.id] = round(antenna_time, 3)
│                                              ↓ acumulado en dict
├── calculate_multi_antenna_coverage()  [si N>1]
│
├── total_time = time.perf_counter() - sim_start    [total]
│
└── results['metadata'] = {
        'total_execution_time_seconds': round(total_time, 2),
        'antenna_times_seconds': antenna_times,
        'gpu_used': gpu_used,
        'gpu_device': gpu_device,
        ...
    }
        │
        ├──► finished.emit(results)  →  MainWindow.on_simulation_finished()
        │                               └─ self.last_simulation_results = results
        │                               └─ Muestra total en diálogo de análisis
        │
        └──► ExportManager.export_metadata_json()
             └─ data/exports/*_metadata.json
                └─ "compute_performance": {
                       "total_execution_time_seconds": ...,
                       "antenna_times_seconds": {...}
                   }
```

---

## 9. Cómo Ejecutar los Tests de Benchmark

```powershell
# Desde la raíz del proyecto, con el entorno virtual activado:

# Test de rendimiento CPU vs GPU (requiere GPU)
python -m pytest tests/test_gpu_functionality.py -v -s

# Test de rendimiento del terreno (requiere archivo cuenca_terrain.tif)
python -m pytest tests/test_simulation_with_terrain.py::TestSimulationWithTerrain::test_performance_terrain_loading -v -s
```

El flag `-s` permite ver los `print()` de los tiempos en la salida de consola.

**Salida esperada de `test_cpu_vs_gpu_performance`:**
```
  CPU time: 0.0412s
  GPU time: 0.0087s
  Speedup: 4.74x
```

**Salida esperada de `test_performance_terrain_loading`:**
```
  Initial load: 0.843s
  Single query: 0.023ms
  Vectorized query (100x100): 0.187s
```

---

## 10. Cómo Interpretar los JSON Exportados para Comparativas

Para comparar dos simulaciones CPU vs GPU desde PowerShell:

```powershell
# Leer performance de un JSON exportado
$meta = Get-Content "data\exports\simulacion_20260419_222442_metadata.json" | ConvertFrom-Json
$meta.compute_performance

# Salida:
# gpu_used                     : True
# gpu_device                   : GPU: NVIDIA GeForce GTX 1660 SUPER (CC 7.5)
# total_execution_time_seconds : 0.87
# antenna_times_seconds        : @{80a7ec60... = 0.851}

# Comparar múltiples archivos
Get-ChildItem "data\exports\*_metadata.json" | ForEach-Object {
    $m = Get-Content $_ | ConvertFrom-Json
    [PSCustomObject]@{
        File    = $_.Name
        GPU     = $m.compute_performance.gpu_used
        Device  = $m.compute_performance.gpu_device
        Total_s = $m.compute_performance.total_execution_time_seconds
        Grid    = $m.grid_parameters.total_grid_points
        Model   = $m.propagation_model.model_name
    }
} | Format-Table
```

---

**Ver también:**
- [05_LOGGING.md](05_LOGGING.md) — mensajes de log que acompañan los tiempos (`Simulation completed in Xs`)
- [08_GPU_DETECTOR.md](08_GPU_DETECTOR.md) — cómo se detecta el hardware y se construye `gpu_device`
- [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md) — etapas completas del pipeline donde se insertan los timers
- [10_MODELO_EJECUCION_THREADS.md](10_MODELO_EJECUCION_THREADS.md) — contexto de threading donde corre `SimulationWorker`
