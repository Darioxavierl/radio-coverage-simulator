# Sistema de Exportacion: CSV, GeoTIFF, KML y Metadata JSON

**Version:** 2026-05-31

## 1. Proposito

El sistema de exportacion permite serializar los resultados de simulacion a formatos externos para analisis posterior, interoperabilidad con otras herramientas y trazabilidad experimental. En la implementacion actual no existe un metodo operativo tipo `export_all()` que genere todos los archivos de una sola vez. El flujo real parte desde la interfaz grafica, donde el usuario exporta bajo demanda uno de los formatos disponibles a partir de `MainWindow.last_simulation_results`.

**Componentes principales**:

- `src/ui/main_window.py`: coordina la exportacion desde la GUI.
- `src/utils/export_manager.py`: implementa la serializacion a CSV, metadata JSON, GeoTIFF y KML.

## 2. Flujo real de exportacion

El punto de entrada operativo es `MainWindow.export_results(format_type)`. Ese metodo:

1. verifica que existan resultados previos de simulacion;
2. construye un nombre base con timestamp `simulacion_YYYYMMDD_HHMMSS`;
3. abre un dialogo de guardado segun el formato solicitado;
4. delega la escritura al `ExportManager`.

En el caso de CSV, la exportacion real genera dos archivos relacionados:

- `*.csv`: tabla detallada por punto de grilla y por antena;
- `*_metadata.json`: metadata complementaria para reproducibilidad.

En GeoTIFF, la GUI solicita ademas el CRS de salida antes de escribir el raster. En KML, el exportador crea el archivo `.kml` y, si la cobertura viene como `data:image/...;base64`, extrae la imagen PNG a un archivo acompanante para maximizar compatibilidad con visores KML.

## 3. Estructura esperada de resultados

El `ExportManager` trabaja sobre el diccionario de resultados generado por `SimulationWorker`. El esquema relevante para exportacion es:

```python
results = {
    'individual': {
        antenna_id: {
            'antenna': {...},
            'lats': np.ndarray,
            'lons': np.ndarray,
            'rsrp': np.ndarray,
            'path_loss': np.ndarray,
            'antenna_gain': np.ndarray,
            'los_map': np.ndarray | None,
            'bounds': ((south, west), (north, east)),
            'image_url': 'data:image/png;base64,...',
            'los_image_url': 'data:image/png;base64,...'
        }
    },
    'aggregated': {
        'lats': np.ndarray,
        'lons': np.ndarray,
        'rsrp': np.ndarray,
        'path_loss': np.ndarray,
        'antenna_gain': np.ndarray,
        'los_map': np.ndarray | None,
        'bounds': ((south, west), (north, east)),
        'image_url': 'data:image/png;base64,...',
        'los_image_url': 'data:image/png;base64,...'
    },
    'metadata': {
        'timestamp': ...,
        'model_used': ...,
        'model_parameters': {...},
        'grid_parameters': {...},
        'gpu_used': ...,
        'gpu_device': ...,
        'total_execution_time_seconds': ...,
        ...
    }
}
```

Si existe `results['aggregated']`, tanto `export_geotiff()` como `export_kml()` priorizan esa cobertura agregada. Si no existe, toman la primera cobertura individual disponible como fallback.

## 4. Exportacion CSV

### 4.1 Objetivo

`export_csv(results, base_filename)` genera un archivo tabular orientado a comparativa cientifica y postprocesamiento externo. No produce un resumen estadistico separado. La granularidad real es una fila por punto de grilla y por antena.

### 4.2 Archivo generado

```text
simulacion_20260531_103015.csv
```

### 4.3 Columnas

Las columnas base son:

```text
antenna_id,
frequency_mhz,
tx_power_dbm,
tx_height_m,
grid_lat,
grid_lon,
rsrp_dbm,
path_loss_db,
antenna_gain_dbi,
model_used,
environment,
terrain_type
```

Si al menos una cobertura individual contiene `los_map`, el exportador anade una columna adicional:

```text
los_nlos
```

### 4.4 Logica de serializacion

- Recorre `results['individual']` antena por antena.
- Aplana `lats`, `lons`, `rsrp`, `path_loss` y `antenna_gain`.
- Escribe una fila por cada punto de la grilla.
- Inserta parametros de la antena y del modelo en cada fila para facilitar comparaciones fuera de la aplicacion.
- Si hay mapa LOS, serializa `1` para LOS, `0` para sombra y cadena vacia cuando esa antena no tiene dato disponible.

### 4.5 Alcance practico

Este formato es el mas util para:

- analisis estadistico en Python, R o Excel;
- comparaciones punto a punto frente a otras herramientas;
- trazabilidad de parametros RF junto con el valor numerico exportado.

## 5. Exportacion Metadata JSON

### 5.1 Objetivo

`export_metadata_json(results, base_filename)` genera un archivo auxiliar con informacion de contexto y rendimiento. En la GUI este JSON se exporta junto con el CSV para que la tabla numerica no quede desacoplada de la configuracion usada para producirla.

### 5.2 Archivo generado

```text
simulacion_20260531_103015_metadata.json
```

### 5.3 Estructura principal

El JSON exportado contiene, entre otros, los siguientes bloques:

- `simulation_info`: timestamp original, timestamp de exportacion y nombre del software.
- `compute_performance`: uso de GPU, dispositivo, tiempo total y tiempos por antena o por etapa si estan disponibles.
- `grid_parameters`: descripcion de la grilla de simulacion.
- `propagation_model`: nombre del modelo usado y sus parametros.
- `data_description`: numero de antenas, numero de puntos y lista de campos exportados en el CSV.

### 5.4 Observacion importante

El esquema se alimenta desde `results['metadata']`. Por eso cualquier cambio en los campos generados por `SimulationWorker` debe mantenerse sincronizado con `ExportManager.export_metadata_json()`.

## 6. Exportacion GeoTIFF

### 6.1 Objetivo

`export_geotiff(results, filename, target_crs='EPSG:4326')` produce un raster georreferenciado multibanda apto para software SIG. El contenido exportado no se limita a RSRP: tambien incluye perdidas de trayecto y ganancia de antena, y puede incorporar una banda LOS/NLOS cuando esa informacion existe.

### 6.2 Seleccion de cobertura

- Si existe `results['aggregated']`, se exporta la cobertura agregada.
- Si no existe, se exporta la primera cobertura individual.

### 6.3 Bandas escritas

Bandas base:

1. `RSRP (dBm)`
2. `Path Loss (dB)`
3. `Antenna Gain (dBi)`

Banda opcional:

4. `LOS Map (1=LOS, 0=Shadow)`

### 6.4 Georreferenciacion y reproyeccion

La georreferenciacion se construye a partir de `lats`, `lons` y los limites del grid. La grilla de simulacion original esta en WGS84 (`EPSG:4326`), pero la implementacion actual permite reproyectar a otro CRS de salida mediante `rasterio.warp.reproject()`.

Desde la GUI se ofrecen actualmente estas opciones:

- `EPSG:4326`
- `EPSG:32717`
- `EPSG:32718`

La reproyeccion usa:

- interpolacion bilineal para RSRP, path loss y ganancia;
- vecino mas cercano para la banda LOS, preservando su naturaleza discreta.

### 6.5 Metadatos del raster

El exportador anade etiquetas de descripcion por banda y tags globales con el CRS de origen y el CRS exportado. Esto mejora la interpretacion posterior del archivo en QGIS, ArcGIS u otras herramientas SIG.

## 7. Exportacion KML

### 7.1 Objetivo

`export_kml(results, filename)` genera un archivo KML orientado a visualizacion geoespacial, especialmente en Google Earth. La implementacion actual no exporta poligonos vectoriales de cobertura ni placemarks detallados por antena como producto principal. Exporta overlays raster georreferenciados.

### 7.2 Contenido real del KML

El documento KML incluye:

- un `GroundOverlay` principal con el heatmap RSRP;
- un `GroundOverlay` adicional para LOS, solo si existe `los_image_url`;
- un `Placemark` simple en el centro de la cobertura exportada.

### 7.3 Manejo de imagenes

Si `image_url` o `los_image_url` vienen como `data URL` en base64:

- se decodifican a PNG;
- se guardan junto al `.kml`;
- el KML referencia esos archivos locales en lugar de mantener el contenido embebido.

Esta decision mejora la compatibilidad con clientes KML reales, que suelen manejar mejor referencias a imagenes externas que recursos `data:` incrustados.

### 7.4 Cobertura exportada

Igual que en GeoTIFF, el KML prioriza la cobertura agregada si existe. Esto hace que el producto exportado coincida mejor con la vista principal que el usuario suele analizar en la GUI.

## 8. Relacion con la interfaz grafica

El sistema de exportacion no vive aislado del flujo de usuario. Despues de cada simulacion, `MainWindow.on_simulation_finished()` conserva los resultados en memoria para permitir exportaciones posteriores. A partir de ahi:

- la exportacion CSV tambien genera metadata JSON;
- la exportacion GeoTIFF pide CRS de salida;
- la exportacion KML se basa en los overlays ya generados durante el flujo de visualizacion.

En otras palabras, exportacion y visualizacion comparten la misma estructura de resultados, lo cual evita recalculos adicionales y mantiene consistencia entre lo que el usuario inspecciona y lo que finalmente guarda a disco.

## 9. Diferencia entre formatos estandar e implementacion propia

Conviene distinguir claramente dos niveles:

- **Formatos estandar**: CSV, GeoTIFF y KML son formatos externos ya establecidos y no constituyen un aporte original del trabajo.
- **Implementacion propia**: la seleccion de campos, la forma de serializar la grilla RF, la composicion multibanda del GeoTIFF, el overlay KML a partir de imagenes generadas por el simulador, el esquema del metadata JSON y la integracion con la GUI si son decisiones de implementacion desarrolladas dentro del proyecto.

Esta distincion es importante para documentacion tecnica y tambien para la redaccion academica de la tesis.

## 10. Limitaciones actuales

- No existe una exportacion masiva que genere todos los formatos en un solo paso.
- El KML representa la cobertura como overlay raster, no como capa vectorial analitica.
- El metadata JSON depende del esquema de `results['metadata']` y requiere sincronizacion cuando ese esquema cambia.
- El CSV privilegia trazabilidad cientifica por punto de grilla, no un resumen compacto orientado a reportes ejecutivos.

---

**Ver tambien**: [MANUAL_TECNICO.md](MANUAL_TECNICO.md), [GUIA_CAPITULO_METODOLOGIA.md](GUIA_CAPITULO_METODOLOGIA.md)
