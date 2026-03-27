# Okumura-Hata - Script de Demostración

Este script demuestra las capacidades del modelo Okumura-Hata completo implementado.

## Ejemplo de Uso Básico

```python
import numpy as np
from core.models.traditional.okumura_hata import OkumuraHataModel

# Crear modelo
model = OkumuraHataModel()

# Parámetros
distances = np.array([1000, 2000, 5000, 10000])  # metros
frequency = 1800  # MHz
tx_height = 40  # metros AGL
tx_elevation = 500  # msnm (elevación del terreno en TX)
terrain_heights = np.array([500, 400, 300, 200])  # msnm (elevación en cada punto)

# Cálculo para ambiente URBANO
pl_urban = model.calculate_path_loss(
    distances, frequency, tx_height, terrain_heights,
    tx_elevation=tx_elevation,
    environment='Urban',
    city_type='medium'
)

# Cálculo para ambiente SUBURBANO
pl_suburban = model.calculate_path_loss(
    distances, frequency, tx_height, terrain_heights,
    tx_elevation=tx_elevation,
    environment='Suburban'
)

# Cálculo para ambiente RURAL
pl_rural = model.calculate_path_loss(
    distances, frequency, tx_height, terrain_heights,
    tx_elevation=tx_elevation,
    environment='Rural'
)

print(f"Urban:    {pl_urban}")
print(f"Suburban: {pl_suburban}")
print(f"Rural:    {pl_rural}")
```

## Uso con GPU (CuPy)

```python
import cupy as cp
from core.models.traditional.okumura_hata import OkumuraHataModel

# Crear modelo con soporte GPU
model_gpu = OkumuraHataModel(compute_module=cp)

# Datos en GPU
distances_gpu = cp.array([1000, 2000, 5000, 10000])
terrain_heights_gpu = cp.array([500, 400, 300, 200])

# Cálculo en GPU
pl_gpu = model_gpu.calculate_path_loss(
    distances_gpu, 1800, 40, terrain_heights_gpu,
    tx_elevation=500, environment='Urban'
)

# Convertir resultado a CPU
pl_cpu = cp.asnumpy(pl_gpu)
print(f"Path Loss (GPU): {pl_cpu}")
```

## Características Implementadas

### ✅ Altura Efectiva con Terreno
- Usa `terrain_heights` para calcular altura efectiva
- Formula: `h_eff = h_antena + elevation_tx - elevation_avg`
- Considera elevación promedio del área

### ✅ Correcciones por Ambiente
- **Urban**: Pérdidas estándar (sin corrección)
- **Suburban**: Reducción ~5-20 dB respecto a Urban
- **Rural**: Reducción ~20-40 dB respecto a Urban

### ✅ Correcciones por Tipo de Ciudad
- **Medium City**: Factor a(hm) estándar
- **Large City**: Factor a(hm) para metrópolis

### ✅ Extensión COST-231 Hata
- Automática para frecuencias > 1500 MHz
- Factor Cm: 3 dB para ciudad grande, 0 dB para mediana

### ✅ Validación de Rangos
- Frecuencia: 150-2000 MHz
- Distancia: 1-20 km (óptimo)
- Altura antena base: 30-200 m
- Altura móvil: 1-10 m
- Warnings automáticos si fuera de rango

### ✅ Soporte CPU/GPU
- Usa `self.xp` (numpy o cupy)
- Todas las operaciones vectorizadas
- Consistencia numérica CPU/GPU perfecta (< 1e-14 dB)

## Tests Implementados

Total: **26 tests exhaustivos** cubriendo:
- ✅ Inicialización (default, custom config, CuPy)
- ✅ Cálculos básicos (monotonía, valores razonables)
- ✅ Manejo de terreno (plano, elevado, variable)
- ✅ Correcciones por ambiente (Urban/Suburban/Rural)
- ✅ Correcciones por tipo de ciudad
- ✅ Extensión COST-231 (>1500 MHz)
- ✅ Casos de referencia de literatura
- ✅ Consistencia CPU/GPU
- ✅ Casos extremos (distancias min/max, grids grandes)

**Resultado: 26/26 tests OK (100%)**

## Próximo Paso: Datos de Elevación

El modelo está **LISTO** para recibir datos reales de elevación del terreno.

Próxima implementación:
```python
# TerrainLoader con soporte SRTM/GeoTIFF
terrain_loader = TerrainLoader()
terrain_data = terrain_loader.load('SRTM_N02W079.hgt')

# Interpolar elevaciones para grid de simulación
elevations = terrain_data.get_elevations(grid_lats, grid_lons)

# Usar en Okumura-Hata
path_loss = model.calculate_path_loss(
    distances, frequency, tx_height, elevations,  # <- datos reales
    tx_elevation=terrain_data.get_elevation(tx_lat, tx_lon)
)
```
