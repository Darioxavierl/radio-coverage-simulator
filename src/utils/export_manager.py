import json
import csv
import base64
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

from pyproj import CRS as PyprojCRS


class ExportManager:
    """Manager para exportar resultados de simulación en múltiples formatos"""

    def __init__(self):
        self.logger = logging.getLogger("ExportManager")

    def export_csv(self, results, base_filename):
        """
        Exporta resultados como CSV completo para comparativa científica

        Args:
            results: Dict con structure {'individual': {...}, 'aggregated': {...}, 'metadata': {...}}
            base_filename: Nombre base sin extensión
        """
        csv_file = f"{base_filename}.csv"

        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header con todos los datos necesarios para comparativa
                header = [
                    'antenna_id', 'frequency_mhz', 'tx_power_dbm', 'tx_height_m',
                    'grid_lat', 'grid_lon',
                    'rsrp_dbm', 'path_loss_db', 'antenna_gain_dbi',
                    'model_used', 'environment', 'terrain_type'
                ]
                writer.writerow(header)

                # Obtener metadata
                metadata = results.get('metadata', {})
                model_params = metadata.get('model_parameters', {})

                for antenna_id, coverage in results['individual'].items():
                    antenna_info = coverage.get('antenna', {})
                    lats = coverage['lats'].flatten()
                    lons = coverage['lons'].flatten()
                    rsrp = coverage['rsrp'].flatten()
                    path_loss = coverage.get('path_loss', np.zeros_like(rsrp)).flatten()
                    antenna_gain = coverage.get('antenna_gain', np.zeros_like(rsrp)).flatten()

                    for lat, lon, r, pl, ag in zip(lats, lons, rsrp, path_loss, antenna_gain):
                        writer.writerow([
                            antenna_id,
                            antenna_info.get('frequency_mhz', ''),
                            antenna_info.get('tx_power_dbm', ''),
                            antenna_info.get('tx_height_m', ''),
                            round(float(lat), 6),
                            round(float(lon), 6),
                            round(float(r), 2),
                            round(float(pl), 2),
                            round(float(ag), 2),
                            metadata.get('model_used', 'unknown'),
                            model_params.get('environment', 'N/A'),
                            model_params.get('terrain_type', 'N/A')
                        ])

            self.logger.info(f"CSV exported: {csv_file}")
            return csv_file

        except Exception as e:
            self.logger.error(f"Error exporting CSV: {e}")
            raise

    def export_metadata_json(self, results, base_filename):
        """
        Exporta metadata completa como JSON para reproducibilidad

        Args:
            results: Dict con results de simulación
            base_filename: Nombre base sin extensión
        """
        json_file = f"{base_filename}_metadata.json"

        try:
            metadata = results.get('metadata', {})
            export_data = {
                'simulation_info': {
                    'timestamp': metadata.get('timestamp'),
                    'software': 'RF Coverage Tool v1.0',
                    'export_timestamp': datetime.now().isoformat()
                },
                'compute_performance': {
                    'gpu_used': metadata.get('gpu_used'),
                    'gpu_device': metadata.get('gpu_device'),
                    'total_execution_time_seconds': metadata.get('total_execution_time_seconds'),

                    # Compatibilidad: si existe esquema nuevo úsalo, si no usa el viejo
                    'antenna_times_seconds': metadata.get(
                        'antenna_total_times_seconds',
                        metadata.get('antenna_times_seconds', {})
                    ),

                    # Nuevas métricas por etapa
                    'terrain_loading_time_seconds': metadata.get('terrain_loading_time_seconds'),
                    'antenna_total_times_seconds': metadata.get(
                        'antenna_total_times_seconds',
                        metadata.get('antenna_times_seconds', {})
                    ),
                    'antenna_coverage_times_seconds': metadata.get('antenna_coverage_times_seconds', {}),
                    'antenna_render_times_seconds': metadata.get('antenna_render_times_seconds', {}),
                    'multi_antenna_aggregation_time_seconds': metadata.get(
                        'multi_antenna_aggregation_time_seconds'
                    )
                },
                'grid_parameters': metadata.get('grid_parameters', {}),
                'propagation_model': {
                    'model_name': metadata.get('model_used'),
                    'parameters': metadata.get('model_parameters', {})
                },
                'data_description': {
                    'num_antennas': metadata.get('num_antennas'),
                    'num_grid_points_per_antenna': metadata.get('grid_parameters', {}).get('total_grid_points'),
                    'fields': ['antenna_id', 'frequency_mhz', 'tx_power_dbm', 'tx_height_m',
                              'grid_lat', 'grid_lon', 'rsrp_dbm', 'path_loss_db', 'antenna_gain_dbi',
                              'model_used', 'environment', 'terrain_type']
                }
            }

            with open(json_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            self.logger.info(f"Metadata JSON exported: {json_file}")
            return json_file

        except Exception as e:
            self.logger.error(f"Error exporting metadata JSON: {e}")
            raise

    def export_geotiff(self, results, filename, target_crs='EPSG:4326'):
        """
        Exporta como GeoTIFF multibanda georeferenciado

        Bandas:
        1. RSRP (dBm)
        2. Path Loss (dB)
        3. Antenna Gain (dBi)

        Args:
            results: Dict con results de simulación
            filename: Ruta completa del archivo GeoTIFF
            target_crs: CRS de salida (ej. 'EPSG:4326', 'EPSG:32717')
        """
        try:
            import rasterio
            from rasterio.transform import Affine
            from rasterio.warp import calculate_default_transform, reproject, Resampling
        except ImportError:
            self.logger.error("rasterio not installed. Install: pip install rasterio")
            raise

        try:
            # Validar CRS destino para evitar archivos corruptos
            PyprojCRS.from_string(target_crs)

            # PHASE 7: Usar agregada si existe, si no usar primera antena individual
            if 'aggregated' in results:
                self.logger.info("Exporting aggregated coverage to GeoTIFF")
                coverage = results['aggregated']
            else:
                self.logger.info("Exporting individual coverage (first antenna) to GeoTIFF")
                antenna_id = list(results['individual'].keys())[0]
                coverage = results['individual'][antenna_id]

            # Extraer datos
            lats_2d = coverage['lats']
            lons_2d = coverage['lons']
            rsrp_2d = coverage['rsrp'].astype(np.float32)
            path_loss_2d = coverage.get('path_loss', np.zeros_like(rsrp_2d)).astype(np.float32)
            antenna_gain_2d = coverage.get('antenna_gain', np.zeros_like(rsrp_2d)).astype(np.float32)

            # Crear transform para georeferenciación
            west = float(lons_2d.min())
            east = float(lons_2d.max())
            south = float(lats_2d.min())
            north = float(lats_2d.max())

            height, width = rsrp_2d.shape

            transform = Affine(
                (east - west) / width, 0, west,
                0, -(north - south) / height, north
            )

            # CRS y datos fuente (la grilla de simulación está en lat/lon WGS84)
            source_crs = 'EPSG:4326'

            # Reproyectar si el usuario selecciona un CRS diferente al de origen
            if target_crs != source_crs:
                dst_transform, dst_width, dst_height = calculate_default_transform(
                    source_crs,
                    target_crs,
                    width,
                    height,
                    west,
                    south,
                    east,
                    north,
                )

                rsrp_out = np.zeros((dst_height, dst_width), dtype=np.float32)
                path_loss_out = np.zeros((dst_height, dst_width), dtype=np.float32)
                antenna_gain_out = np.zeros((dst_height, dst_width), dtype=np.float32)

                reproject(
                    source=rsrp_2d,
                    destination=rsrp_out,
                    src_transform=transform,
                    src_crs=source_crs,
                    dst_transform=dst_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )
                reproject(
                    source=path_loss_2d,
                    destination=path_loss_out,
                    src_transform=transform,
                    src_crs=source_crs,
                    dst_transform=dst_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )
                reproject(
                    source=antenna_gain_2d,
                    destination=antenna_gain_out,
                    src_transform=transform,
                    src_crs=source_crs,
                    dst_transform=dst_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

                output_transform = dst_transform
                output_crs = target_crs
                output_height = dst_height
                output_width = dst_width
            else:
                rsrp_out = rsrp_2d
                path_loss_out = path_loss_2d
                antenna_gain_out = antenna_gain_2d
                output_transform = transform
                output_crs = source_crs
                output_height = height
                output_width = width

            # Escribir GeoTIFF con 3 bandas
            with rasterio.open(
                filename, 'w',
                driver='GTiff',
                height=output_height,
                width=output_width,
                count=3,  # 3 bandas
                dtype=np.float32,
                crs=output_crs,
                transform=output_transform
            ) as dst:
                dst.write(rsrp_out, 1)          # Banda 1: RSRP
                dst.write(path_loss_out, 2)     # Banda 2: Path Loss
                dst.write(antenna_gain_out, 3)  # Banda 3: Antenna Gain

                # Agregar descripciones de bandas
                dst.update_tags(1, DESCRIPTION='RSRP (dBm)')
                dst.update_tags(2, DESCRIPTION='Path Loss (dB)')
                dst.update_tags(3, DESCRIPTION='Antenna Gain (dBi)')
                dst.update_tags(export_crs=output_crs, source_crs=source_crs)

            self.logger.info(f"GeoTIFF multibanda exportado: {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Error exporting GeoTIFF: {e}")
            raise

    def export_kml(self, results, filename):
        """
        Exporta como KML con heatmap georeferenciado como overlay

        Args:
            results: Dict con results de simulación
            filename: Ruta completa del archivo KML
        """
        try:
            # PHASE 7: Usar agregada si existe, si no usar primera antena individual
            if 'aggregated' in results:
                self.logger.info("Exporting aggregated coverage to KML")
                coverage = results['aggregated']
                antenna_name = 'Aggregated Coverage'
            else:
                self.logger.info("Exporting individual coverage (first antenna) to KML")
                antenna_id = list(results['individual'].keys())[0]
                coverage = results['individual'][antenna_id]
                antenna_name = antenna_id

            # Obtener bounds
            bounds = coverage['bounds']
            north = bounds[1][0]
            south = bounds[0][0]
            east = bounds[1][1]
            west = bounds[0][1]

            # Obtener imagen heatmap
            image_url = coverage.get('image_url', '')
            icon_href = image_url

            # Si viene en data URL, exportar PNG externo para mayor compatibilidad KML
            if image_url.startswith('data:image') and ';base64,' in image_url:
                base64_data = image_url.split(';base64,', 1)[1]
                image_bytes = base64.b64decode(base64_data)

                kml_path = Path(filename)
                image_filename = f"{kml_path.stem}_overlay.png"
                image_path = kml_path.with_name(image_filename)

                with open(image_path, 'wb') as img_file:
                    img_file.write(image_bytes)

                icon_href = image_filename

            # Crear KML
            kml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>RF Coverage Simulation - {antenna_name}</name>
    <description>Exported from RF Coverage Tool</description>

    <GroundOverlay>
      <name>Coverage Heatmap</name>
      <description>RSRP Coverage (dBm)</description>
      <Icon>
                <href>{icon_href}</href>
        <viewBoundScale>0.75</viewBoundScale>
      </Icon>
      <LatLonBox>
        <north>{north}</north>
        <south>{south}</south>
        <east>{east}</east>
        <west>{west}</west>
        <rotation>0</rotation>
      </LatLonBox>
      <transparency>0.7</transparency>
    </GroundOverlay>

    <Placemark>
      <name>Coverage Center</name>
      <Point>
        <coordinates>{(west+east)/2},{(south+north)/2},0</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>'''

            with open(filename, 'w') as f:
                f.write(kml_content)

            self.logger.info(f"KML exportado: {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Error exporting KML: {e}")
            raise
