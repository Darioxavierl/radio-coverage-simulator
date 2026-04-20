# Sistema Completo de Exportación de Resultados - Guía Completa

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Descripción General](#descripción-general)
3. [Formatos de Exportación](#formatos-de-exportación)
4. [CSV + JSON para Comparativa Científica](#csv--json-para-comparativa-científica)
5. [GeoTIFF Multibanda](#geotiff-multibanda)
6. [KML con Heatmap Overlay](#kml-con-heatmap-overlay)
7. [Performance Metrics](#performance-metrics)
8. [Workflow Completo para Validación](#workflow-completo-para-validación)
9. [Ejemplos Prácticos](#ejemplos-prácticos)
10. [Troubleshooting](#troubleshooting)

---

## Introducción

El **Sistema de Exportación de Resultados** de RF Coverage Tool permite exportar simulaciones de cobertura radioeléctrica en tres formatos diferentes, optimizados para dos propósitos completamente distintos:

### Propósito 1: Visualización Geoespacial
Visualizar y analizar resultados de cobertura en sistemas GIS profesionales o mapas interactivos públicos.

### Propósito 2: Validación y Benchmarking Científico
Comparar resultados con otros simuladores (MATLAB, Python, software comercial) y realizar análisis estadístico riguroso.

---

## Descripción General

Después de ejecutar una simulación, el usuario puede exportar los resultados en **3 formatos**:

| Formato | Propósito | Contenido | Software Compatible |
|---------|----------|----------|------------------|
| **CSV + JSON** | Comparativa científica | Coordenadas, RSRP, Path Loss, Antenna Gain, metadata | MATLAB, Python, R, Excel |
| **GeoTIFF** | Análisis GIS | 3 bandas georreferenciadas: RSRP, Path Loss, Antenna Gain | QGIS, ArcGIS, Google Earth Pro |
| **KML** | Visualización web | Heatmap como overlay georeferenciado | Google Earth, Cesium, cualquier visor KML |

---

## Formatos de Exportación

### CSV + JSON para Comparativa Científica

#### ¿Cuándo usar?
- Necesitas comparar con resultados de otro software
- Quieres realizar análisis estadístico (RMSE, correlación, etc.)
- Necesitas reproducir exactamente la simulación

#### Estructura del CSV

**Archivo**: `simulacion_YYYYMMDD_HHMMSS.csv`

```csv
antenna_id,frequency_mhz,tx_power_dbm,tx_height_m,grid_lat,grid_lon,rsrp_dbm,path_loss_db,antenna_gain_dbi,model_used,environment,terrain_type
ant_001,0,0,0,-2.910000,-79.009000,-75.20,118.20,18.00,okumura_hata,Urban,N/A
ant_001,0,0,0,-2.909800,-79.009000,-76.50,119.50,18.00,okumura_hata,Urban,N/A
...
```

**Columnas**:
- `antenna_id`: Identificador de antena (string)
- `frequency_mhz`: Frecuencia de transmisión (MHz) - actualmente 0 en versión actual
- `tx_power_dbm`: Potencia de transmisión (dBm) - actualmente 0 en versión actual
- `tx_height_m`: Altura de transmisor (m) - actualmente 0 en versión actual
- `grid_lat`: Latitud del punto de grid (grados, WGS84)
- `grid_lon`: Longitud del punto de grid (grados, WGS84)
- `rsrp_dbm`: Potencia recibida (dBm) - Rango: -120 a -60 dBm típicamente
- `path_loss_db`: Pérdida de camino (dB) - Derivado del modelo de propagación
- `antenna_gain_dbi`: Ganancia de antena (dBi) - Del patrón de radiación
- `model_used`: Modelo de propagación usado (string)
- `environment`: Ambiente (Urban/Suburban/Rural) - Solo si aplicable
- `terrain_type`: Tipo de terreno (smooth/mixed/irregular) - Solo si aplicable

**Cantidad de filas**: `resolution²` (por defecto 100² = 10,000 filas por antena)

#### Estructura del JSON Metadata

**Archivo**: `simulacion_YYYYMMDD_HHMMSS_metadata.json`

```json
{
  "simulation_info": {
    "timestamp": "2026-04-19T21:47:03",
    "software": "RF Coverage Tool v1.0",
    "export_timestamp": "2026-04-19T21:50:00"
  },
  "compute_performance": {
    "gpu_used": true,
    "gpu_device": "NVIDIA GeForce GTX 1660 SUPER",
    "total_execution_time_seconds": 2.34,
    "antenna_times_seconds": {
      "ant_001": 2.34
    }
  },
  "grid_parameters": {
    "radius_km": 5.0,
    "resolution": 100,
    "total_grid_points": 10000
  },
  "propagation_model": {
    "model_name": "okumura_hata",
    "parameters": {
      "environment": "Urban",
      "city_type": "medium"
    }
  },
  "data_description": {
    "num_antennas": 1,
    "num_grid_points_per_antenna": 10000,
    "fields": [...]
  }
}
```

#### Importar en MATLAB

```matlab
% Cargar CSV
data = readtable('simulacion_20260419_214703.csv');

% Cargar metadata
metadata = jsondecode(fileread('simulacion_20260419_214703_metadata.json'));

% Extraer columnas
lat = data.grid_lat;
lon = data.grid_lon;
rsrp_ours = data.rsrp_dbm;
path_loss = data.path_loss_db;

% Comparar con software externo (asumir que 'rsrp_other' está cargado)
rmse = sqrt(mean((rsrp_ours - rsrp_other).^2));
correlation = corr(rsrp_ours, rsrp_other);

fprintf('RMSE: %.2f dB\n', rmse);
fprintf('Correlation: %.4f\n', correlation);
```

#### Importar en Python

```python
import pandas as pd
import json
import numpy as np
from scipy.stats import pearsonr

# Cargar CSV
data = pd.read_csv('simulacion_20260419_214703.csv')

# Cargar metadata
with open('simulacion_20260419_214703_metadata.json') as f:
    metadata = json.load(f)

# Extraer datos
lat = data['grid_lat'].values
lon = data['grid_lon'].values
rsrp_ours = data['rsrp_dbm'].values
path_loss = data['path_loss_db'].values

# Comparar con software externo
rmse = np.sqrt(np.mean((rsrp_ours - rsrp_other)**2))
correlation, p_value = pearsonr(rsrp_ours, rsrp_other)

print(f'RMSE: {rmse:.2f} dB')
print(f'Correlation: {correlation:.4f}')
print(f'GPU used: {metadata["compute_performance"]["gpu_used"]}')
print(f'Execution time: {metadata["compute_performance"]["total_execution_time_seconds"]}s')
```

---

### GeoTIFF Multibanda

#### ¿Cuándo usar?
- Necesitas importar en software GIS profesional (QGIS, ArcGIS)
- Quieres realizar análisis geoespacial avanzado
- Necesitas superponer con otras capas de datos

#### Estructura

**Archivo**: `simulacion_YYYYMMDD_HHMMSS.tif`

**3 Bandas Georreferenciadas**:
1. **Banda 1 - RSRP (dBm)**: Intensidad de señal recibida
2. **Banda 2 - Path Loss (dB)**: Pérdida de propagación
3. **Banda 3 - Antenna Gain (dBi)**: Ganancia de antena

**Georeferenciación**:
- CRS: EPSG:4326 (WGS84)
- Pixel size: (lon_delta/width, lat_delta/height)
- Bounds: [lat_min, lon_min] a [lat_max, lon_max]

#### Abrir en QGIS

1. **Abrir archivo**:
   - Menu: `Layer → Add Layer → Add Raster Layer`
   - Seleccionar archivo `.tif`

2. **Visualizar bandas individuales**:
   - En Layers panel: click derecho en layer
   - `Properties → Symbology`
   - Band: Seleccionar 1 (RSRP), 2 (Path Loss), o 3 (Antenna Gain)

3. **Colorear por valores**:
   - Symbology: `Single Band Pseudocolor`
   - Color ramp: Viridis, Jet, o personalizado
   - Min/Max: Automático o manual

4. **Agregar otras capas**:
   - OpenStreetMap como base
   - Shapefile con límites administrativos
   - Puntos de antenas

#### Abrir en ArcGIS

```python
# ArcGIS Pro Python script
import arcpy
from arcpy.ia import *

# Raster input
raster = 'simulacion_20260419_214703.tif'

# Extract band (RSRP)
rsrp_band = arcpy.Raster(raster, 1)

# Classify for visualization
classified = Reclassify(rsrp_band, "VALUE", 
                        "-120 -100 1;-100 -80 2;-80 -60 3")

# Save
classified.save('rsrp_classified.tif')
```

#### Análisis GIS Avanzado

**Ejemplo**: Encontrar áreas sin cobertura

```python
import rasterio
import numpy as np

# Abrir GeoTIFF
with rasterio.open('simulacion_20260419_214703.tif') as src:
    rsrp = src.read(1)  # Banda 1: RSRP
    profile = src.profile
    
    # Crear máscara: sin cobertura < -110 dBm
    no_coverage = rsrp < -110
    coverage_percentage = (1 - no_coverage.sum() / no_coverage.size) * 100
    
    print(f'Coverage: {coverage_percentage:.1f}%')
```

---

### KML con Heatmap Overlay

#### ¿Cuándo usar?
- Quieres ver la cobertura en Google Earth
- Necesitas compartir resultados con no técnicos
- Quieres comparar con datos de Google Maps/Streets

#### Estructura

**Archivo**: `simulacion_YYYYMMDD_HHMMSS.kml`

**Contenido**:
- **GroundOverlay**: Imagen de heatmap georeferenciada
- **Placemark**: Ubicación de antena

#### Abrir en Google Earth

1. Desktop (gratuito):
   - File → Open
   - Seleccionar archivo `.kml`

2. Google Earth Pro:
   - Mismos pasos
   - Más opciones de análisis

3. Web (Google Earth Engine):
   - No soporta KML directamente
   - Convertir a GeoTIFF primero

#### Ejemplo en Cesium (visualizador web)

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.100/Cesium.js"></script>
    <link rel="stylesheet" href="https://cesium.com/downloads/cesiumjs/releases/1.100/Widgets/widgets.css">
</head>
<body>
    <div id="cesiumContainer" style="width: 100%; height: 100%;"></div>
    <script>
        Cesium.Ion.defaultAccessToken = 'YOUR_TOKEN';
        const viewer = new Cesium.Viewer('cesiumContainer');
        
        // Cargar KML
        Cesium.KmlDataSource.load('simulacion_20260419_214703.kml')
            .then(kml => viewer.dataSources.add(kml));
    </script>
</body>
</html>
```

---

## Performance Metrics

### Campos Capturados en Metadata

| Campo | Unidad | Significado |
|-------|--------|------------|
| `total_execution_time_seconds` | seconds | Duración total de simulación |
| `antenna_times_seconds` | dict | Tiempo por cada antena individualmente |
| `gpu_used` | bool | Si se usó GPU o CPU |
| `gpu_device` | string | Nombre exacto del dispositivo GPU |
| `grid_parameters.total_grid_points` | int | Número total de puntos calculados |

### Cálculo de Aceleración GPU

```
Aceleración = Tiempo_CPU / Tiempo_GPU

Ejemplo:
- CPU: 250 ms
- GPU: 30 ms
- Aceleración: 250/30 = 8.33x
```

### Interpretación

| Aceleración | Significado |
|------------|------------|
| < 1x | GPU más lento (overhead de transferencia > beneficio) |
| 1-2x | GPU ligeramente más rápido |
| 2-5x | GPU beneficioso para este tamaño de grid |
| 5-10x | GPU muy beneficioso |
| > 10x | GPU excelente para grandes grids |

---

## Workflow Completo para Validación

### Paso 1: Ejecutar Simulación

1. Abrir RF Coverage Tool
2. Crear/Cargar proyecto
3. Agregar antena(s)
4. Ir a Simulación → Ejecutar
5. Seleccionar modelo de propagación
6. Ejecutar

**Resultado**: Simulación completa en segundos

### Paso 2: Exportar Resultados

1. Ir a Archivo → Exportar
2. Elegir formato:
   - **CSV + JSON**: Para comparativa MATLAB/Python
   - **GeoTIFF**: Para QGIS/ArcGIS
   - **KML**: Para Google Earth

**Resultado**: Archivos generados en `data/exports/`

### Paso 3: Importar en Software Externo

**Opción A - MATLAB**:
```matlab
data = readtable('simulacion_*.csv');
metadata = jsondecode(fileread('simulacion_*_metadata.json'));
% Análisis...
```

**Opción B - Python**:
```python
import pandas as pd
data = pd.read_csv('simulacion_*.csv')
# Análisis...
```

**Opción C - QGIS**:
- Layer → Add Raster Layer → simulacion_*.tif

**Opción D - Google Earth**:
- File → Open → simulacion_*.kml

### Paso 4: Comparar Resultados

**En MATLAB/Python**:
```matlab
% Calcular RMSE
rmse = sqrt(mean((ours - other).^2));

% Calcular correlación
r = corr(ours, other);

% Gráfico
scatter(ours, other); hold on;
plot([-120 -60], [-120 -60], 'r--');
xlabel('Our Results (dBm)'); ylabel('Other Software (dBm)');
title(sprintf('RMSE=%.2f dB, r=%.4f', rmse, r));
```

### Paso 5: Calcular Métricas de Error

**RMSE (Root Mean Square Error)**:
```
RMSE = sqrt(mean((ours - other)²))
- Ideal: 0 dB
- Aceptable: < 2 dB
```

**Error Absoluto Promedio (MAE)**:
```
MAE = mean(|ours - other|)
- Ideal: 0 dB
- Aceptable: < 1.5 dB
```

**Correlación de Pearson**:
```
r = cov(ours, other) / (std_ours * std_other)
- Ideal: 1.0
- Aceptable: > 0.95
```

**CDF del Error**:
```
Plot: CDF(error)
- 50% de puntos dentro de ±X dB
- 90% de puntos dentro de ±Y dB
```

### Paso 6: Reportar Benchmarking

**Plantilla de reporte**:

```
VALIDACIÓN Y BENCHMARKING - RF Coverage Tool
==============================================

Fecha: 2026-04-19
Modelo: Okumura-Hata
Ambiente: Urban
Grid: 100x100 = 10,000 puntos
Radio: 5 km

PERFORMANCE GPU vs CPU:
  - CPU: 250 ms
  - GPU: 30 ms
  - Aceleración: 8.33x

COMPARATIVA CON [SOFTWARE EXTERNO]:
  - RMSE: 1.23 dB
  - MAE: 0.98 dB
  - Correlación: 0.9876
  - % puntos dentro ±1dB: 85%
  - % puntos dentro ±2dB: 98%

CONCLUSIÓN: Resultados muy consistentes. Diferencias <2dB esperadas
por variaciones en parámetros de modelo.
```

---

## Ejemplos Prácticos

### Ejemplo 1: Comparar con MATLAB

**MATLAB**:
```matlab
% Cargar nuestros resultados
data = readtable('rf_coverage_ours.csv');
our_rsrp = data.rsrp_dbm;

% Cargar archivo de MATLAB (simulación hecha en MATLAB)
matlab_data = readtable('matlab_results.csv');
matlab_rsrp = matlab_data.rsrp_dbm;

% Comparar
rmse = sqrt(mean((our_rsrp - matlab_rsrp).^2));
fprintf('RMSE vs MATLAB: %.2f dB\n', rmse);

% Visualizar
figure; scatter(our_rsrp, matlab_rsrp, 'o', 'filled');
xlabel('RF Coverage Tool (dBm)'); ylabel('MATLAB (dBm)');
title(sprintf('Comparativa - RMSE=%.2f dB', rmse));
grid on; axis equal;
```

### Ejemplo 2: Análisis GIS con QGIS

1. Abrir QGIS
2. Layer → Add Raster Layer → `simulacion_20260419_214703.tif`
3. Seleccionar Banda 1 (RSRP)
4. Properties → Symbology → Single Band Pseudocolor
5. Color Ramp: Viridis
6. Click Classify
7. Agregar OpenStreetMap: Layer → Add Layer → XYZ Tiles → OpenStreetMap
8. Ver resultados en mapa

### Ejemplo 3: Visualización Google Earth

1. Descargar archivo `.kml`
2. Abrir Google Earth Desktop
3. File → Open → seleccionar `.kml`
4. Heatmap aparece en el mapa
5. Click en antenna marker para ver ubicación

### Ejemplo 4: Benchmarking GPU/CPU

```python
import json

# Cargar metadata
with open('simulacion_GPU.json') as f:
    gpu_meta = json.load(f)

with open('simulacion_CPU.json') as f:
    cpu_meta = json.load(f)

gpu_time = gpu_meta['compute_performance']['total_execution_time_seconds']
cpu_time = cpu_meta['compute_performance']['total_execution_time_seconds']
acceleration = cpu_time / gpu_time

print(f'GPU: {gpu_time:.3f}s')
print(f'CPU: {cpu_time:.3f}s')
print(f'Aceleración: {acceleration:.1f}x')
```

---

## Troubleshooting

### Problema: CSV vacío
**Causa**: No hay datos en coverage
**Solución**: Verificar que simulación completó correctamente

### Problema: GeoTIFF no abre en QGIS
**Causa**: rasterio no instalado o formato incorrecto
**Solución**: `pip install rasterio`

### Problema: KML no aparece en Google Earth
**Causa**: Overlay coordinates incorrectas
**Solución**: Verificar bounds en metadata JSON

### Problema: Performance metrics no coinciden
**Causa**: Diferencias en resolución o modelo
**Solución**: Usar mismos parámetros en ambos softwares

---

## Conclusión

El sistema de exportación proporciona **máxima flexibilidad** para:
- ✅ Visualizar resultados en GIS profesional (GeoTIFF)
- ✅ Compartir con no técnicos (KML)
- ✅ Validar contra otros simuladores (CSV)
- ✅ Benchmarking de performance (metadata JSON)
- ✅ Análisis estadístico riguroso (MATLAB/Python)

**Todos los formatos se generan automáticamente** y están listos para usar inmediatamente.

---

## Referencias

- [GDAL/rasterio Documentation](https://rasterio.readthedocs.io/)
- [Google Earth KML Reference](https://developers.google.com/kml/documentation)
- [QGIS Documentation](https://docs.qgis.org/)
- [MATLAB Documentation](https://www.mathworks.com/help/)
