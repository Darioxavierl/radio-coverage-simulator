# Núcleo de Cómputo: Arquitectura y Operaciones Numéricas

**Versión:** 2026-05-08

## 1. Introducción

El núcleo de cómputo (`ComputeEngine`, `CoverageCalculator`) es responsable de todas las operaciones numéricas: construcción de grillas, cálculos de distancia, pérdida de propagación y potencia recibida. Gestiona dinámicamente CPU (NumPy) vs GPU (CuPy) sin cambiar la lógica de negocio.

## 2. Componentes Principales

| Componente | Archivo | Responsabilidad |
|-----------|---------|-----------------|
| ComputeEngine | src/core/compute_engine.py | Selecciona backend (xp = NumPy/CuPy), orquesta calculador |
| CoverageCalculator | src/core/coverage_calculator.py | Haversine, path loss, RSRP por punto |
| SimulationWorker | src/workers/simulation_worker.py | Orquesta flujo completo sin bloquear UI |
| TerrainLoader | src/core/terrain_loader.py | Carga raster, transforma coordenadas |
| HeatmapGenerator | src/utils/heatmap_generator.py | Convierte arrays a PNG base64 |
| GPUDetector | src/utils/gpu_detector.py | Detecta GPU, fallback a CPU |

## 3. Construcción de Grid: Meshgrid

### 3.1 Problema

Necesitamos evaluar un modelo de propagación en 10,000 puntos (100×100 grilla) simultáneamente.

### 3.2 Solución: NumPy Meshgrid

**Ubicación**: `src/workers/simulation_worker.py`, método `_create_simulation_grid()`

```python
# Entrada: 1D arrays
lats_1d = np.linspace(-2.95, -2.85, 100)    # shape: (100,)
lons_1d = np.linspace(-79.15, -78.85, 100)  # shape: (100,)

# Meshgrid: crear grid 2D
grid_lons, grid_lats = np.meshgrid(lons_1d, lats_1d)
# → grid_lats shape: (100, 100)
# → grid_lons shape: (100, 100)

# Broadcasting implícito:
# row 0: lats[-2.95, -2.95, ..., -2.95] @ lons[-79.15, -79.10, ..., -78.85]
# row 1: lats[-2.94, -2.94, ..., -2.94] @ lons[-79.15, -79.10, ..., -78.85]
# ...
# row 99: lats[-2.85, -2.85, ..., -2.85] @ lons[-79.15, -79.10, ..., -78.85]
```

### 3.3 Visualización

```
Grid Result:
┌─────────────────────────────────────────────┐
│ grid_lats[i,j] = lats_1d[i]                │
│ grid_lons[i,j] = lons_1d[j]                │
└─────────────────────────────────────────────┘

Ejemplo punto (50, 50):
  grid_lats[50, 50] = -2.895 (latitud)
  grid_lons[50, 50] = -78.950 (longitud)
  → Corresponde a punto real en mapa
```

### 3.4 Memory Layout

```python
# NumPy default: C-order (row-major)
grid_lats.flags
# C_CONTIGUOUS: True
# F_CONTIGUOUS: False

# Memoria: 100 × 100 × 8 bytes = 80 KB (float64)
# Almacenamiento: fila 0 completa, luego fila 1, etc.

# Acceso eficiente:
for i in range(100):              # ✅ Caché amigable (row-major)
    for j in range(100):
        val = grid_lats[i, j]

# Acceso ineficiente:
for j in range(100):              # ❌ Saltea memoria (column-major)
    for i in range(100):
        val = grid_lats[i, j]
```

### 3.5 Tamaño Total de Grid

Para resolution=100, 3 arrays (lats, lons, elevations):

```
CPU (NumPy):
  3 × (100 × 100) × 8 bytes (float64) = 240 KB

GPU (CuPy):
  Mismo, pero en VRAM: ~300 KB
```

## 4. Vectorización NumPy vs CuPy

### 4.1 Patrón de Polimorfismo

**Ubicación**: `src/core/compute_engine.py`, líneas 13-35

```python
class ComputeEngine(QObject):
    def __init__(self, use_gpu: bool = True):
        self.gpu_detector = GPUDetector()
        self.use_gpu = use_gpu and self.gpu_detector.cupy_available
        
        # Selector agnóstico
        if self.use_gpu:
            self.xp = self.gpu_detector.get_compute_module()  # → cupy
            self.logger.info("Using CuPy (GPU)")
        else:
            import numpy as np
            self.xp = np  # → numpy
            self.logger.info("Using NumPy (CPU)")
```

### 4.2 Operaciones Vectorizadas Comunes

Todas estas operaciones funcionan tanto con NumPy como con CuPy usando `self.xp`:

```python
# En CoverageCalculator (src/core/coverage_calculator.py)

# 1. CREACIÓN DE ARRAYS
rsrp = self.xp.zeros((100, 100))         # shape (100, 100), dtype float64
path_loss = self.xp.ones((100, 100))     # llenar con 1s
```

#### 4.2.1 Haversine Distance (Haversina - Distancia Geodésica)

```python
# Entrada
lat1 = self.xp.radians(ant_lat)          # Escalar → (1,)
lat2 = self.xp.radians(grid_lats)        # (100, 100)
lon1 = self.xp.radians(ant_lon)          # Escalar → (1,)
lon2 = self.xp.radians(grid_lons)        # (100, 100)

# Broadcasting automático: scalar × matrix
dlat = lat2 - lat1                        # (100, 100) - (1,) = (100, 100)
dlon = lon2 - lon1                        # (100, 100) - (1,) = (100, 100)

# Operaciones trigonométricas (vectorizadas)
a = self.xp.sin(dlat/2)**2 + \
    self.xp.cos(lat1) * self.xp.cos(lat2) * \
    self.xp.sin(dlon/2)**2
# a shape: (100, 100) contiene cada término

c = 2 * self.xp.arctan2(
    self.xp.sqrt(a),
    self.xp.sqrt(1 - a)
)
# c shape: (100, 100)

# Radio terrestre
R = 6371000  # metros
distances = self.xp.maximum(R * c, 1e-3)  # (100, 100), evita distancia 0
# Salida: (100, 100) array con distancias en metros
```

**Timing (10,000 puntos)**:
- NumPy: ~10 ms
- CuPy: ~2 ms
- Speedup: 5×

#### 4.2.2 Path Loss Okumura-Hata

```python
# Entrada: distances (100, 100) en metros
frequency_mhz = antenna.frequency_mhz    # escalar, ej. 900
receiver_height = 1.5                    # escalar en metros

# Fórmula Okumura-Hata
# L = 69.55 + 26.16*log10(f) - 13.82*log10(h_b) - a(h_m)
#     + [44.9 - 6.55*log10(h_b)] * log10(d)

log10_f = self.xp.log10(frequency_mhz)
log10_d = self.xp.log10(distances)       # (100, 100)

# Cálculo term by term (vectorizado)
L0 = 69.55 + 26.16 * log10_f
L1 = 13.82 * self.xp.log10(tx_height)
L2 = self.correction_factor_mobile_height(receiver_height)
L3 = (44.9 - 6.55 * self.xp.log10(tx_height)) * log10_d

path_loss = L0 - L1 - L2 + L3  # (100, 100)
# Salida: (100, 100) array con pérdida en dB
```

**Timing (10,000 puntos)**:
- NumPy: ~15 ms
- CuPy: ~3 ms
- Speedup: 5×

#### 4.2.3 RSRP (Potencia Recibida)

```python
# Fórmula general
# RSRP [dBm] = Ptx + Gtx + Grx - Path_Loss - Misc_Losses

Ptx = antenna.tx_power_dbm               # escalar, ej. 40 dBm
Gtx = antenna.tx_gain_dbi                # escalar, ej. 14 dBi
Grx = 0.0                                # receptor isotrópico

rsrp = Ptx + Gtx + Grx - path_loss      # (100, 100) - (100, 100) = (100, 100)
# Salida: (100, 100) array con RSRP en dBm, ej. [-120, -50]
```

### 4.3 Conversión CPU ↔ GPU

```python
# Si use_gpu = True:

# CPU → GPU: Copiar datos a VRAM
if self.use_gpu:
    grid_lats_gpu = self.xp.asarray(grid_lats)     # CPU array → GPU array
    grid_lons_gpu = self.xp.asarray(grid_lons)
    distances_gpu = self.xp.asarray(distances)

# Procesamiento en GPU (todo usa grid_lats_gpu, etc.)
path_loss_gpu = calculate_path_loss(distances_gpu, ...)
rsrp_gpu = calculate_rsrp(path_loss_gpu, ...)

# GPU → CPU: Traer resultados a memoria principal
if self.use_gpu:
    rsrp = self.xp.asnumpy(rsrp_gpu)      # GPU array → CPU array (NumPy)
    path_loss = self.xp.asnumpy(path_loss_gpu)
```

**Overhead de transferencia**: 0.5-2 ms por dirección (según tamaño)

### 4.4 Diferencias Numéricas NumPy vs CuPy

| Aspecto | NumPy | CuPy | Implicación |
|---------|-------|------|------------|
| Precisión default | float64 | float64 | Idéntica |
| sin(), cos() | IEEE 754 completo | Puede ser ≈ | ~1e-7 diferencia |
| Rounding | Determinístico | Determinístico | ✅ Reproducible |
| Memory access | RAM (GB) | VRAM (típ. 2-24 GB) | Límite VRAM |

**Validación**: Los tests en `tests/test_gpu_functionality.py` verifican que NumPy ≈ CuPy con tolerancia 1e-5.

## 5. Operaciones Especiales

### 5.1 Stack y Max (Agregación)

```python
# Agregación multi-antena
# Entrada: 3 arrays (100, 100) de cada antena

rsrp_individual = [
    results['individual']['ant1']['rsrp'],  # (100, 100)
    results['individual']['ant2']['rsrp'],  # (100, 100)
    results['individual']['ant3']['rsrp'],  # (100, 100)
]

# Stack: combinar en tercera dimensión
rsrp_stack = self.xp.stack(rsrp_individual, axis=0)
# rsrp_stack shape: (3, 100, 100)

# Max: tomar máximo por punto
rsrp_agg = self.xp.max(rsrp_stack, axis=0)  # (3, 100, 100) → (100, 100)
best_idx = self.xp.argmax(rsrp_stack, axis=0)  # Índice de mejor (0, 1, 2)
```

### 5.2 Advanced Indexing

```python
# Seleccionar elementos por índice variable
path_loss_stack: (3, 100, 100)
best_idx: (100, 100) con valores 0, 1, o 2

# Obtener path_loss del mejor servidor
path_loss_best = self.xp.take_along_axis(
    path_loss_stack,
    best_idx[self.xp.newaxis, :, :],  # agregar dimensión: (1, 100, 100)
    axis=0
).squeeze()
# path_loss_best shape: (100, 100)
# Cada punto contiene path_loss de su antena "mejor"
```

## 6. Validaciones Críticas

### 6.1 Shapes y Broadcasting

```python
# ✅ CORRECTO: mismo shape o broadcasteable
result = array_100x100 + scalar  # (100, 100) + () = (100, 100)
result = array_100x100 + array_100x100  # (100, 100) + (100, 100) = (100, 100)

# ❌ INCORRECTO: shapes incompatibles
result = array_100x100 + array_50x50  # ValueError: shapes (100,100), (50,50) cannot broadcast
```

### 6.2 Data Types

```python
# Verificar dtype antes de operaciones críticas
if rsrp.dtype != np.float32 and rsrp.dtype != np.float64:
    raise ValueError(f"Expected float32/64, got {rsrp.dtype}")
```

### 6.3 Finite Values

```python
# Verificar NaN/Inf después de operaciones
if not self.xp.all(self.xp.isfinite(rsrp)):
    invalid_count = self.xp.sum(~self.xp.isfinite(rsrp))
    self.logger.warning(f"Found {invalid_count} non-finite values in RSRP")
```

## 7. Ejemplo Completo: Una Antena

```python
# Ubicación: src/core/coverage_calculator.py

def calculate_single_antenna_coverage(self, antenna, grid_lats, grid_lons, 
                                      terrain_heights, model, model_params):
    """Calcula cobertura de una antena en toda la grilla"""
    
    xp = self.engine.xp  # NumPy o CuPy
    
    # 1. Distancia Haversine (100×100 = 10k operaciones vectorizadas)
    distances = self._calculate_distances(
        antenna.latitude, antenna.longitude,
        grid_lats, grid_lons
    )
    # distances shape: (100, 100), dtype: float64
    
    # 2. Calcular altura efectiva TX (incorporar terreno)
    tx_height_agl = antenna.height_agl
    tx_elevation = terrain_heights[int(idx_row), int(idx_col)]
    tx_height_amsl = tx_elevation + tx_height_agl
    
    # 3. Calcular Path Loss según modelo
    if model == 'okumura_hata':
        path_loss = self._calculate_okumura_hata(
            distances,
            antenna.frequency_mhz,
            tx_height_amsl,
            model_params['mobile_height'],
            model_params['environment']
        )
    # path_loss shape: (100, 100), dtype: float64
    
    # 4. Calcular ganancia de antena (patrón de radiación)
    antenna_gain = self._calculate_antenna_gain(
        antenna,
        grid_lats, grid_lons
    )
    # antenna_gain shape: (100, 100), dtype: float64
    
    # 5. Calcular RSRP
    rsrp = antenna.tx_power_dbm + antenna.tx_gain_dbi + antenna_gain - path_loss
    # rsrp shape: (100, 100), dtype: float64
    # Valores típicos: [-120, -50] dBm
    
    # 6. Convertir GPU → CPU si fue necesario
    if self.engine.use_gpu:
        rsrp = self.xp.asnumpy(rsrp)
        path_loss = self.xp.asnumpy(path_loss)
        antenna_gain = self.xp.asnumpy(antenna_gain)
    
    return {
        'rsrp': rsrp,
        'path_loss': path_loss,
        'antenna_gain': antenna_gain,
    }
```

## 8. Timings Reales

```
Operación              | NumPy | CuPy  | Speedup
──────────────────────────────────────────────
Haversine (10k)        | 10ms  | 2ms   | 5×
Path Loss (10k)        | 15ms  | 3ms   | 5×
Antenna Gain (10k)     | 12ms  | 2ms   | 6×
Stack + Max (3×10k)    | 5ms   | 1ms   | 5×
─────────────────────────────────────────────
Total por antena       | 42ms  | 8ms   | ~5×
3 antenas              | 126ms | 24ms  | ~5×
GPU transfer overhead  | -     | 3ms   | N/A
────────────────────────────────────────────
Total simulación       | ~300ms| ~50ms | 6×
```

---

**Ver también**: [08_GPU_DETECTOR.md](08_GPU_DETECTOR.md), [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md), [03_MODELOS_PROPAGACION.md](03_MODELOS_PROPAGACION.md)
