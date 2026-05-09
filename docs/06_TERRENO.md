# Terreno y Cartografía: Carga de DEM, Transformaciones de Coordenadas e Interpolación

**Versión:** 2026-05-08

## 1. Propósito

El subsistema de terreno proporciona la base cartográfica (Modelo Digital de Elevación, DEM) sobre la cual se calcula cobertura. Transforma coordenadas WGS84 geográficas a píxeles raster, interpola alturas en grillas y valida integridad de datos.

## 2. Stack Tecnológico

| Librería | Función | Versión |
|----------|---------|---------|
| rasterio | Lectura GeoTIFF, metadata CRS | 1.3+ |
| pyproj | Transformaciones de coordenadas | 3.4+ |
| NumPy/CuPy | Interpolación vectorizada | 1.20+/11.0+ |

## 3. Flujo de Carga de Terreno

```
Archivo GeoTIFF
    │
    ├─ rasterio.open()
    │
    ├─ Metadata: CRS, bounds, transform
    │
    ├─ Lee array de elevaciones: (H, W)
    │
    ├─ Valida: no-data, bordes, consistencia
    │
    └─→ TerrainLoader cacheado
         │
         ├─ Disponible para transformación
         │
         └─→ CoverageCalculator
              │
              ├─ Obtiene alturas en grid 100×100
              │
              └─→ Cálculos de distancia 3D
```

## 4. TerrainLoader: Clase Principal

**Ubicación**: `src/core/terrain_loader.py`

### 4.1 Inicialización

```python
import rasterio
from pyproj import Transformer, CRS
import numpy as np

class TerrainLoader:
    """
    Carga y gestiona Modelo Digital de Elevación (DEM).
    
    Responsabilidades:
    - Leer GeoTIFF con rasterio
    - Mantener transformación de coordenadas WGS84 ↔ CRS raster
    - Interpolar alturas en puntos arbitrarios
    - Caché de resultados
    """
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.dataset = None
        self.elevation_data = None
        self.crs = None
        self.bounds = None
        self.transform = None
        self.transformer = None
        
        # Caché de alturas interpoladas
        self._height_cache = {}
        
        # Cargar archivo
        self._load_terrain()
    
    def _load_terrain(self):
        """Abre GeoTIFF y extrae metadata"""
        
        with rasterio.open(self.filepath) as src:
            # Metadata
            self.crs = src.crs                    # ej. EPSG:32717 (UTM 17S)
            self.bounds = src.bounds              # (left, bottom, right, top) en CRS
            self.transform = src.transform        # Affine transform
            self.width = src.width                # Ej. 5000 píxeles
            self.height = src.height              # Ej. 4000 píxeles
            
            # Leer datos (banda 1, típicamente)
            self.elevation_data = src.read(1)     # shape: (4000, 5000), dtype: float32
            
            # Validar no-data
            self.nodata_value = src.nodata        # Valor para "sin dato", ej. -9999
            
        # Crear transformador WGS84 → CRS raster
        self.transformer = Transformer.from_crs(
            "EPSG:4326",                          # WGS84 (lat, lon)
            self.crs,                             # Raster CRS (típ. UTM)
            always_xy=True                        # Convención x, y (lon, lat)
        )
        
        self.logger.info(
            f"Terrain loaded: {self.filepath}"
            f" | CRS: {self.crs}"
            f" | Size: {self.width}×{self.height} px"
            f" | Bounds: {self.bounds}"
        )
```

### 4.2 Metadata del Raster

**Ejemplo real: Raster de Cuenca, Ecuador**

```
Archivo: cuenca_terrain.tif

Metadata:
┌──────────────────────────────────┐
│ CRS: EPSG:32717 (UTM 17S)        │
│ Resolución: 10 m × 10 m          │
│ Dimensiones: 5000 × 4000 píxeles │
│ Cobertura: 50 km × 40 km         │
│                                  │
│ Bounds (metros UTM):             │
│   Izq (W):  670000 m             │
│   Der (E):  720000 m             │
│   Inf (S): 9680000 m             │
│   Sup (N): 9720000 m             │
│                                  │
│ Rango de elevaciones:            │
│   Mínima: 1200 m (s.n.m.)        │
│   Máxima: 4100 m (s.n.m.)        │
│   No-data: -9999 (marcador)      │
└──────────────────────────────────┘

Array elevation_data:
  shape: (4000, 5000)
  dtype: float32
  Min: 1200.5, Max: 4099.8
  No-data count: 127 píxeles
```

## 5. Transformación de Coordenadas: WGS84 ↔ UTM

### 5.1 Problema

Un usuario coloca una antena en **(-2.9001°, -79.0059°)** (latitud, longitud en WGS84).

¿En qué píxel del raster se encuentra?

### 5.2 Proceso de Transformación

**Paso 1: WGS84 → UTM**

```python
def get_pixel_from_wgs84(self, lat: float, lon: float) -> tuple:
    """
    Convierte coordenadas WGS84 (lat, lon) a píxel raster (row, col)
    """
    
    # Transformar WGS84 → UTM 17S
    x_utm, y_utm = self.transformer.transform(lon, lat)
    
    # Entrada: lon=-79.0059°, lat=-2.9001°
    # Salida: x_utm=699056.4 m, y_utm=9679234.7 m
    
    print(f"Input:  lat={lat}, lon={lon}")
    print(f"UTM:    x={x_utm:.1f}, y={y_utm:.1f}")
    
    return x_utm, y_utm

# Llamada
x_utm, y_utm = get_pixel_from_wgs84(-2.9001, -79.0059)
# x_utm = 699056.4 m
# y_utm = 9679234.7 m
```

**Paso 2: UTM → Píxeles Raster**

```python
from rasterio.transform import rowcol

def get_pixel_from_wgs84(self, lat: float, lon: float) -> tuple:
    """Completo: WGS84 → Píxel"""
    
    # Step 1: WGS84 → UTM
    x_utm, y_utm = self.transformer.transform(lon, lat)
    
    # Step 2: UTM → Píxel
    # rowcol(transform, x, y) → (row, col)
    row, col = rowcol(self.transform, x_utm, y_utm)
    
    # Entrada: x_utm=699056.4, y_utm=9679234.7
    # Affine transform típico (10 m resolución):
    #   a=10.0, b=0, c=670000     (orientación y origen X)
    #   d=0, e=-10.0, f=9720000   (orientación y origen Y)
    # 
    # Cálculo:
    #   col = (x_utm - 670000) / 10 = (699056.4 - 670000) / 10 = 2905.64 → 2905
    #   row = (9720000 - y_utm) / 10 = (9720000 - 9679234.7) / 10 = 4076.53 → 4076
    
    print(f"Pixel:  row={row}, col={col}")
    
    return int(row), int(col)

# Llamada
row, col = get_pixel_from_wgs84(-2.9001, -79.0059)
# row = 4076 (vertical, desde arriba)
# col = 2905 (horizontal, desde izquierda)
```

**Paso 3: Leer Altura en Píxel**

```python
def get_height_at_point(self, lat: float, lon: float) -> float:
    """Obtiene altura en un punto WGS84"""
    
    row, col = self.get_pixel_from_wgs84(lat, lon)
    
    # Validar que el píxel esté dentro del raster
    if row < 0 or row >= self.height or col < 0 or col >= self.width:
        raise ValueError(f"Point ({lat}, {lon}) outside raster bounds")
    
    # Leer altura
    height = self.elevation_data[row, col]
    
    # Validar no-data
    if height == self.nodata_value:
        self.logger.warning(f"No-data value at ({lat}, {lon})")
        return None
    
    return float(height)

# Llamada
height = get_height_at_point(-2.9001, -79.0059)
# height ≈ 2450.3 m (s.n.m.)
```

### 5.3 Visualización del Mapeo

```
Coordenadas WGS84:
┌─────────────────────────────┐
│  (-2.9001°, -79.0059°)      │
│  (lat, lon) en grados       │
└──────────────┬──────────────┘
               │ pyproj.Transformer
               ↓
Coordenadas UTM:
┌─────────────────────────────┐
│  (699056.4, 9679234.7) m    │
│  (x, y) en metros           │
│  En CRS EPSG:32717          │
└──────────────┬──────────────┘
               │ rasterio.transform.rowcol()
               ↓
Píxeles Raster:
┌─────────────────────────────┐
│  (row=4076, col=2905)       │
│  Índices en array NumPy     │
└──────────────┬──────────────┘
               │ elevation_data[row, col]
               ↓
Altura:
┌─────────────────────────────┐
│  2450.3 m (s.n.m.)          │
│  dtype: float32             │
└─────────────────────────────┘
```

## 6. Interpolación Vectorizada en Grid

### 6.1 Problema: 10,000 Puntos a la Vez

En vez de preguntar altura en un punto, necesitamos alturas en toda una grilla 100×100.

```python
def get_heights_fast(self, lats_2d: np.ndarray, lons_2d: np.ndarray) -> np.ndarray:
    """
    Entrada:
      lats_2d: shape (100, 100), dtype float64
      lons_2d: shape (100, 100), dtype float64
    
    Salida:
      heights: shape (100, 100), dtype float32
      
    Método: Vectorización con NumPy (sin loops)
    """
    
    # Flatten (100, 100) → (10000,) para transformación
    lats_flat = lats_2d.flatten()       # (10000,)
    lons_flat = lons_2d.flatten()       # (10000,)
    
    # Transformar WGS84 → UTM (10k puntos simultáneamente)
    xs_utm, ys_utm = self.transformer.transform(lons_flat, lats_flat)
    # xs_utm shape: (10000,), dtype float64
    # ys_utm shape: (10000,), dtype float64
    
    # Convertir UTM → píxeles (rasterio.transform.rowcol vectorizado)
    rows, cols = rowcol(self.transform, xs_utm, ys_utm)
    # rows shape: (10000,), dtype int
    # cols shape: (10000,), dtype int
    
    # Clipping a límites del raster
    rows = np.clip(rows, 0, self.height - 1)
    cols = np.clip(cols, 0, self.width - 1)
    
    # Lectura vectorizada (advanced indexing)
    heights_flat = self.elevation_data[rows, cols]
    # heights_flat shape: (10000,), dtype float32
    
    # Reshape a (100, 100)
    heights = heights_flat.reshape((100, 100))
    
    # Marcar no-data como NaN
    heights[heights == self.nodata_value] = np.nan
    
    return heights

# Llamada en CoverageCalculator
grid_lats, grid_lons = np.meshgrid(...)  # (100, 100) cada uno
terrain_heights = terrain_loader.get_heights_fast(grid_lats, grid_lons)
# terrain_heights shape: (100, 100), dtype float32
```

### 6.2 Timing de Interpolación

```
Operación                  | Tiempo
────────────────────────────────────
Flatten (100, 100)         | 0.01 ms
Transform WGS84 → UTM      | 1.2 ms  (pyproj)
rowcol (10k) vectorizado   | 0.5 ms
Indexing [rows, cols]      | 0.2 ms
Clip + NaN                 | 0.1 ms
Reshape (10000,)→(100,100)| 0.01 ms
────────────────────────────────────
TOTAL                      | ~2 ms
```

Comparación loop vs vectorización:

```python
# ❌ LENTO: Loop (10,000 iteraciones)
heights_loop = np.zeros((100, 100))
for i in range(100):
    for j in range(100):
        row, col = get_pixel(lats[i, j], lons[i, j])
        heights_loop[i, j] = elevation_data[row, col]
# Tiempo: ~80-100 ms

# ✅ RÁPIDO: Vectorizado
heights_vector = get_heights_fast(lats_2d, lons_2d)
# Tiempo: ~2 ms

# Speedup: 40-50×
```

## 7. Validaciones Críticas

### 7.1 Chequeo de Integridad del Raster

```python
def validate_terrain_file(filepath: str) -> dict:
    """Valida que el raster sea válido antes de usarlo"""
    
    issues = []
    
    with rasterio.open(filepath) as src:
        # Chequeo 1: Tiene 1 banda
        if src.count != 1:
            issues.append(f"Expected 1 band, found {src.count}")
        
        # Chequeo 2: Data type numérico
        if src.dtypes[0] not in ['float32', 'float64', 'int16', 'int32']:
            issues.append(f"Unsupported dtype: {src.dtypes[0]}")
        
        # Chequeo 3: CRS definido
        if src.crs is None:
            issues.append("CRS not defined")
        
        # Chequeo 4: Rango de elevaciones razonable
        data = src.read(1)
        valid_data = data[data != src.nodata]
        
        if len(valid_data) == 0:
            issues.append("All values are no-data")
        
        min_elev = np.min(valid_data)
        max_elev = np.max(valid_data)
        
        if max_elev < min_elev:
            issues.append("Min elevation > Max elevation")
        
        if max_elev - min_elev < 10:
            issues.append("Elevation range too small (<10m)")
        
        # Chequeo 5: No-data handling
        nodata_count = np.sum(data == src.nodata)
        nodata_pct = 100 * nodata_count / data.size
        
        if nodata_pct > 50:
            issues.append(f"Too many no-data values ({nodata_pct:.1f}%)")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'min_elev': float(min_elev),
        'max_elev': float(max_elev),
        'nodata_pct': float(nodata_pct),
    }

# Ejemplo de uso
result = validate_terrain_file('cuenca_terrain.tif')
if not result['valid']:
    for issue in result['issues']:
        logger.error(f"Terrain validation: {issue}")
```

### 7.2 Detección de Límites

```python
def get_valid_coverage_region(self) -> dict:
    """
    Retorna región de cobertura válida (sin no-data)
    en coordenadas WGS84
    """
    
    # Encontrar píxeles válidos
    valid_mask = self.elevation_data != self.nodata_value
    
    if not np.any(valid_mask):
        raise ValueError("No valid elevation data in raster")
    
    # Bounding box de píxeles válidos
    rows_valid, cols_valid = np.where(valid_mask)
    min_row, max_row = rows_valid.min(), rows_valid.max()
    min_col, max_col = cols_valid.min(), cols_valid.max()
    
    # Convertir a coordenadas UTM (esquinas)
    corners_utm = [
        (self.bounds.left + min_col * 10, self.bounds.top - min_row * 10),   # NW
        (self.bounds.left + max_col * 10, self.bounds.top - min_row * 10),   # NE
        (self.bounds.left + max_col * 10, self.bounds.top - max_row * 10),   # SE
        (self.bounds.left + min_col * 10, self.bounds.top - max_row * 10),   # SW
    ]
    
    # Convertir UTM → WGS84
    corners_wgs84 = [
        self.transformer.transform(x, y, inverse=True)
        for x, y in corners_utm
    ]
    
    lons = [c[0] for c in corners_wgs84]
    lats = [c[1] for c in corners_wgs84]
    
    return {
        'lat_min': min(lats),
        'lat_max': max(lats),
        'lon_min': min(lons),
        'lon_max': max(lons),
        'valid_pixels': np.sum(valid_mask),
        'total_pixels': valid_mask.size,
        'coverage_pct': 100 * np.sum(valid_mask) / valid_mask.size,
    }
```

## 8. Integración con CoverageCalculator

```python
# Ubicación: src/core/coverage_calculator.py

class CoverageCalculator:
    def __init__(self, terrain_loader: TerrainLoader):
        self.terrain = terrain_loader
        # ...
    
    def calculate_coverage_with_terrain(
        self,
        antenna_lat, antenna_lon,
        grid_lats, grid_lons,
        model_params
    ):
        """Incluye elevación del terreno en cálculos"""
        
        # Obtener alturas en grid (vectorizado)
        receiver_heights = self.terrain.get_heights_fast(grid_lats, grid_lons)
        # shape: (100, 100)
        
        # Altura de antena (AMSL = altitud s.n.m.)
        antenna_height_agl = antenna_params.height_agl  # 15 m
        ant_pixel_height = self.terrain.get_height_at_point(
            antenna_lat, antenna_lon
        )
        antenna_height_amsl = ant_pixel_height + antenna_height_agl
        
        # Calcular distancia 3D incluyendo elevación
        # En lugar de solo distancia 2D (Haversine)
        distances_2d = calculate_haversine(...)  # (100, 100)
        height_diff = receiver_heights - antenna_height_amsl  # (100, 100)
        distances_3d = np.sqrt(distances_2d**2 + height_diff**2)
        
        # Path loss basado en distancia 3D
        path_loss = calculate_path_loss(distances_3d, ...)
        
        return path_loss
```

## 9. Caché y Performance

```python
def get_heights_fast(self, lats_2d, lons_2d) -> np.ndarray:
    """
    Con caché: evita recalcular interpolación
    para mismos datos
    """
    
    # Generar clave de caché (hash de coordenadas)
    cache_key = (
        hash(lats_2d.tobytes()),
        hash(lons_2d.tobytes())
    )
    
    if cache_key in self._height_cache:
        self.logger.debug("Using cached heights")
        return self._height_cache[cache_key]
    
    # Calcular (si no está en caché)
    heights = ... # (cálculo completo)
    
    # Guardar en caché
    self._height_cache[cache_key] = heights.copy()
    
    # Limpiar caché si crece demasiado (últimas 10)
    if len(self._height_cache) > 10:
        oldest_key = next(iter(self._height_cache))
        del self._height_cache[oldest_key]
    
    return heights
```

---

**Ver también**: [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md), [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md)
