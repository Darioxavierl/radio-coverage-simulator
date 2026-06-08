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
        Exporta resultados como CSV completo para comparativa científica.

        Para despliegues multi-antena: exporta UNA fila por punto de grid usando el
        RSRP del best server (antena dominante), equivalente al export de Atoll.
        Para despliegues mono-antena: exporta las filas de esa única antena.

        Args:
            results: Dict con structure {'individual': {...}, 'aggregated': {...}, 'metadata': {...}}
            base_filename: Nombre base sin extensión
        """
        csv_file = f"{base_filename}.csv"

        # El aggregated con 'best_server' solo existe en despliegues multi-antena.
        # Para mono-antena, results['aggregated'] es una copia del individual y no
        # contiene 'best_server'.
        agg = results.get('aggregated')
        use_aggregated = agg is not None and 'best_server' in agg

        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                header = [
                    'antenna_id', 'frequency_mhz', 'tx_power_dbm', 'tx_height_m',
                    'grid_lat', 'grid_lon',
                    'rsrp_dbm', 'path_loss_db', 'antenna_gain_dbi',
                    'model_used', 'environment', 'terrain_type'
                ]

                if use_aggregated:
                    has_los = agg.get('los_map') is not None
                else:
                    has_los = any(
                        cov.get('los_map') is not None
                        for cov in results['individual'].values()
                    )

                if has_los:
                    header.append('los_nlos')

                writer.writerow(header)

                metadata = results.get('metadata', {})
                model_params = metadata.get('model_parameters', {})

                if use_aggregated:
                    # ── Multi-antena: una fila por punto, RSRP del best server ──
                    # Lookup antenna_id → info (frecuencia, potencia, altura)
                    antenna_info_lookup = {
                        ant_id: cov.get('antenna', {})
                        for ant_id, cov in results['individual'].items()
                    }

                    lats = agg['lats'].flatten()
                    lons = agg['lons'].flatten()
                    rsrp = agg['rsrp'].flatten()
                    path_loss = agg.get('path_loss', np.zeros_like(rsrp)).flatten()
                    antenna_gain = agg.get('antenna_gain', np.zeros_like(rsrp)).flatten()
                    best_server = agg['best_server'].flatten()

                    los_flat = None
                    if has_los and agg.get('los_map') is not None:
                        los_flat = agg['los_map'].flatten()

                    for i, (lat, lon, r, pl, ag, ant_id) in enumerate(
                        zip(lats, lons, rsrp, path_loss, antenna_gain, best_server)
                    ):
                        ant_info = antenna_info_lookup.get(ant_id, {})
                        row = [
                            ant_id,
                            ant_info.get('frequency_mhz', ''),
                            ant_info.get('tx_power_dbm', ''),
                            ant_info.get('tx_height_m', ''),
                            round(float(lat), 6),
                            round(float(lon), 6),
                            round(float(r), 2),
                            round(float(pl), 2),
                            round(float(ag), 2),
                            metadata.get('model_used', 'unknown'),
                            model_params.get('environment', 'N/A'),
                            model_params.get('terrain_type', 'N/A')
                        ]
                        if has_los:
                            row.append(int(round(float(los_flat[i]))) if los_flat is not None else '')
                        writer.writerow(row)

                    self.logger.info(f"CSV (aggregated best-server): {len(lats)} puntos, {csv_file}")

                else:
                    # ── Mono-antena: comportamiento original ──
                    for antenna_id, coverage in results['individual'].items():
                        antenna_info = coverage.get('antenna', {})
                        lats = coverage['lats'].flatten()
                        lons = coverage['lons'].flatten()
                        rsrp = coverage['rsrp'].flatten()
                        path_loss = coverage.get('path_loss', np.zeros_like(rsrp)).flatten()
                        antenna_gain = coverage.get('antenna_gain', np.zeros_like(rsrp)).flatten()

                        los_map = coverage.get('los_map')
                        if has_los and los_map is not None:
                            los_iter = [int(round(float(v))) for v in los_map.flatten()]
                        else:
                            los_iter = [''] * len(lats)

                        for lat, lon, r, pl, ag, los_val in zip(
                            lats, lons, rsrp, path_loss, antenna_gain, los_iter
                        ):
                            row = [
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
                            ]
                            if has_los:
                                row.append(los_val)
                            writer.writerow(row)

                    self.logger.info(f"CSV (individual): {csv_file}")

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

    def _write_geotiff_single(self, coverage, filename, target_crs):
        """
        Escribe un GeoTIFF multibanda para una cobertura individual o agregada.

        Bandas:
          1. RSRP (dBm)
          2. Path Loss (dB)
          3. Antenna Gain (dBi)
          4. LOS Map (1=LOS, 0=Shadow)  — solo si coverage contiene 'los_map'

        Args:
            coverage: Dict de cobertura con lats, lons, rsrp, path_loss, etc.
            filename:  Ruta completa del archivo de salida
            target_crs: CRS destino (ej. 'EPSG:4326', 'EPSG:32717')

        Returns:
            str: ruta del archivo escrito
        """
        import rasterio
        from rasterio.transform import Affine
        from rasterio.warp import calculate_default_transform, reproject, Resampling

        lats_2d = coverage['lats']
        lons_2d = coverage['lons']
        rsrp_2d       = coverage['rsrp'].astype(np.float32)
        path_loss_2d  = coverage.get('path_loss',    np.zeros_like(rsrp_2d)).astype(np.float32)
        antenna_gain_2d = coverage.get('antenna_gain', np.zeros_like(rsrp_2d)).astype(np.float32)

        los_2d_raw = coverage.get('los_map')
        has_los    = los_2d_raw is not None
        los_2d     = los_2d_raw.astype(np.float32) if has_los else None

        west  = float(lons_2d.min())
        east  = float(lons_2d.max())
        south = float(lats_2d.min())
        north = float(lats_2d.max())
        height, width = rsrp_2d.shape

        transform = Affine(
            (east - west) / width, 0, west,
            0, -(north - south) / height, north
        )
        source_crs = 'EPSG:4326'

        if target_crs != source_crs:
            dst_transform, dst_width, dst_height = calculate_default_transform(
                source_crs, target_crs, width, height, west, south, east, north
            )

            rsrp_out        = np.zeros((dst_height, dst_width), dtype=np.float32)
            path_loss_out   = np.zeros((dst_height, dst_width), dtype=np.float32)
            antenna_gain_out = np.zeros((dst_height, dst_width), dtype=np.float32)

            for src, dst_arr in [
                (rsrp_2d,        rsrp_out),
                (path_loss_2d,   path_loss_out),
                (antenna_gain_2d, antenna_gain_out),
            ]:
                reproject(
                    source=src, destination=dst_arr,
                    src_transform=transform, src_crs=source_crs,
                    dst_transform=dst_transform, dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

            los_out = None
            if has_los:
                los_out = np.zeros((dst_height, dst_width), dtype=np.float32)
                reproject(
                    source=los_2d, destination=los_out,
                    src_transform=transform, src_crs=source_crs,
                    dst_transform=dst_transform, dst_crs=target_crs,
                    resampling=Resampling.nearest,
                )

            output_transform = dst_transform
            output_crs    = target_crs
            output_height = dst_height
            output_width  = dst_width
        else:
            rsrp_out        = rsrp_2d
            path_loss_out   = path_loss_2d
            antenna_gain_out = antenna_gain_2d
            los_out          = los_2d
            output_transform = transform
            output_crs       = source_crs
            output_height    = height
            output_width     = width

        band_count = 4 if (has_los and los_out is not None) else 3
        with rasterio.open(
            filename, 'w',
            driver='GTiff',
            height=output_height,
            width=output_width,
            count=band_count,
            dtype=np.float32,
            crs=output_crs,
            transform=output_transform,
        ) as dst:
            dst.write(rsrp_out,        1)
            dst.write(path_loss_out,   2)
            dst.write(antenna_gain_out, 3)
            dst.update_tags(1, DESCRIPTION='RSRP (dBm)')
            dst.update_tags(2, DESCRIPTION='Path Loss (dB)')
            dst.update_tags(3, DESCRIPTION='Antenna Gain (dBi)')
            if has_los and los_out is not None:
                dst.write(los_out, 4)
                dst.update_tags(4, DESCRIPTION='LOS Map (1=LOS, 0=Shadow)')
            dst.update_tags(export_crs=output_crs, source_crs=source_crs)

        self.logger.info(f"GeoTIFF escrito: {filename}")
        return str(filename)

    def export_geotiff(self, results, filename, target_crs='EPSG:4326'):
        """
        Exporta como GeoTIFF multibanda georeferenciado.

        Genera un archivo por cobertura:
          - {filename}              → cobertura agregada (o única antena)
          - {stem}_{ant_id}.tif    → cobertura individual de cada antena
                                     (solo cuando hay más de una antena)

        Bandas en cada archivo:
          1. RSRP (dBm)
          2. Path Loss (dB)
          3. Antenna Gain (dBi)
          4. LOS Map (1=LOS, 0=Shadow) — si disponible

        Args:
            results:    Dict con structure {'individual': {...}, 'aggregated': {...}}
            filename:   Ruta completa del archivo GeoTIFF agregado
            target_crs: CRS de salida (ej. 'EPSG:4326', 'EPSG:32717')

        Returns:
            list[str]: lista de rutas de todos los archivos creados
        """
        import re

        try:
            import rasterio  # noqa: F401 — verificar dependencia temprano
        except ImportError:
            self.logger.error("rasterio not installed. Install: pip install rasterio")
            raise

        try:
            # Validar CRS destino para evitar archivos corruptos
            PyprojCRS.from_string(target_crs)

            created_files = []
            tif_path = Path(filename)

            def safe_id(antenna_id):
                return re.sub(r'[^\w]', '_', str(antenna_id))

            # ---------------------------------------------------------------
            # 1. Archivo AGREGADO (siempre, en la ruta que pide el usuario)
            # ---------------------------------------------------------------
            agg = results.get('aggregated') or results['individual'][
                list(results['individual'].keys())[0]
            ]
            self.logger.info(f"Exportando GeoTIFF agregado: {filename}")
            self._write_geotiff_single(agg, filename, target_crs)
            created_files.append(str(filename))

            # ---------------------------------------------------------------
            # 2. Archivos INDIVIDUALES (solo si hay más de una antena)
            # ---------------------------------------------------------------
            individual = results.get('individual', {})
            if len(individual) > 1:
                for ant_id, cov in individual.items():
                    ind_filename = tif_path.with_name(
                        f'{tif_path.stem}_{safe_id(ant_id)}{tif_path.suffix}'
                    )
                    ant_name = cov.get('antenna', {}).get('name', ant_id)
                    self.logger.info(f"Exportando GeoTIFF individual '{ant_name}': {ind_filename}")
                    self._write_geotiff_single(cov, ind_filename, target_crs)
                    created_files.append(str(ind_filename))

            self.logger.info(
                f"GeoTIFF exportado: {len(created_files)} archivo(s) en {tif_path.parent}"
            )
            return created_files

        except Exception as e:
            self.logger.error(f"Error exporting GeoTIFF: {e}")
            raise

    # ------------------------------------------------------------------
    # Helpers privados para KML
    # ------------------------------------------------------------------

    def _extract_overlay_png(self, image_url, output_path):
        """
        Extrae una imagen data-URL (base64) a un archivo PNG en disco.

        Args:
            image_url: data URL "data:image/...;base64,<data>" o ruta directa
            output_path: Path completo de destino (ej. Path('/tmp/foo.png'))

        Returns:
            str: nombre de archivo relativo (solo el basename) para referenciar en KML,
                 o None si image_url está vacío o no es un data URL.
        """
        if not image_url:
            return None
        if image_url.startswith('data:image') and ';base64,' in image_url:
            b64_data = image_url.split(';base64,', 1)[1]
            image_bytes = base64.b64decode(b64_data)
            with open(output_path, 'wb') as f:
                f.write(image_bytes)
            return Path(output_path).name
        # Si ya es una ruta o URL directa, devolverla tal cual
        return image_url

    def _build_ground_overlay_block(self, name, description, icon_href,
                                    bounds, draw_order=0, visibility=1):
        """
        Construye un bloque XML <GroundOverlay> completo.

        Args:
            name: Nombre de la capa
            description: Descripción
            icon_href: Ruta/URL del PNG
            bounds: [[south, west], [north, east]]
            draw_order: Orden de renderizado en Google Earth (mayor = encima)
            visibility: 1=visible, 0=oculto por defecto

        Returns:
            str: bloque XML listo para insertar en el documento KML
        """
        south = bounds[0][0]
        west  = bounds[0][1]
        north = bounds[1][0]
        east  = bounds[1][1]
        return f'''    <GroundOverlay>
      <name>{name}</name>
      <description>{description}</description>
      <visibility>{visibility}</visibility>
      <drawOrder>{draw_order}</drawOrder>
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
    </GroundOverlay>'''

    def export_kml(self, results, filename):
        """
        Exporta como KML con heatmap georeferenciado como overlay.

        Genera un KML con carpetas anidadas:
          - "Cobertura Agregada": RSRP y LOS del mapa combinado (visible por defecto)
          - "Cobertura Individual": una subcarpeta por antena con sus propios
            overlays RSRP y LOS (ocultos por defecto, activar en Google Earth)

        Args:
            results: Dict con structure {'individual': {...}, 'aggregated': {...}}
            filename: Ruta completa del archivo KML

        Returns:
            str: ruta del archivo KML creado
        """
        import re

        try:
            kml_path = Path(filename)
            stem = kml_path.stem

            def safe_id(antenna_id):
                return re.sub(r'[^\w]', '_', str(antenna_id))

            # ---------------------------------------------------------------
            # 1. Carpeta AGREGADO
            # ---------------------------------------------------------------
            agg = results.get('aggregated') or results['individual'][
                list(results['individual'].keys())[0]
            ]

            agg_rsrp_png = self._extract_overlay_png(
                agg.get('image_url', ''),
                kml_path.with_name(f'{stem}_agg_rsrp.png')
            )
            agg_los_png = self._extract_overlay_png(
                agg.get('los_image_url', ''),
                kml_path.with_name(f'{stem}_agg_los.png')
            )

            agg_rsrp_block = ''
            if agg_rsrp_png:
                agg_rsrp_block = self._build_ground_overlay_block(
                    name='RSRP Agregado',
                    description='Potencia de señal recibida - mejor servidor (dBm)',
                    icon_href=agg_rsrp_png,
                    bounds=agg['bounds'],
                    draw_order=10,
                    visibility=1
                )

            agg_los_block = ''
            if agg_los_png:
                agg_los_block = self._build_ground_overlay_block(
                    name='LOS Agregado',
                    description='Línea de visión directa (verde=LOS, naranja=sombra)',
                    icon_href=agg_los_png,
                    bounds=agg['bounds'],
                    draw_order=9,
                    visibility=1
                )

            aggregated_folder = f'''  <Folder>
    <name>Cobertura Agregada</name>
    <visibility>1</visibility>
{agg_rsrp_block}
{agg_los_block}
  </Folder>'''

            # ---------------------------------------------------------------
            # 2. Carpeta INDIVIDUAL — una subcarpeta por antena
            # ---------------------------------------------------------------
            individual_subfolders = []
            for ant_id, cov in results['individual'].items():
                sid = safe_id(ant_id)
                ant_name = cov.get('antenna', {}).get('name', ant_id)

                ind_rsrp_png = self._extract_overlay_png(
                    cov.get('image_url', ''),
                    kml_path.with_name(f'{stem}_{sid}_rsrp.png')
                )
                ind_los_png = self._extract_overlay_png(
                    cov.get('los_image_url', ''),
                    kml_path.with_name(f'{stem}_{sid}_los.png')
                )

                rsrp_block = ''
                if ind_rsrp_png:
                    rsrp_block = self._build_ground_overlay_block(
                        name=f'RSRP – {ant_name}',
                        description=f'Potencia de señal recibida de {ant_name} (dBm)',
                        icon_href=ind_rsrp_png,
                        bounds=cov['bounds'],
                        draw_order=5,
                        visibility=0
                    )

                los_block = ''
                if ind_los_png:
                    los_block = self._build_ground_overlay_block(
                        name=f'LOS – {ant_name}',
                        description=f'Línea de visión directa de {ant_name}',
                        icon_href=ind_los_png,
                        bounds=cov['bounds'],
                        draw_order=4,
                        visibility=0
                    )

                subfolder = f'''    <Folder>
      <name>{ant_name}</name>
      <visibility>0</visibility>
{rsrp_block}
{los_block}
    </Folder>'''
                individual_subfolders.append(subfolder)

            individual_folder = f'''  <Folder>
    <name>Cobertura Individual</name>
    <visibility>0</visibility>
    <description>Activa cada antena individualmente en el panel de capas</description>
{chr(10).join(individual_subfolders)}
  </Folder>'''

            # ---------------------------------------------------------------
            # 3. Placemark centro
            # ---------------------------------------------------------------
            bounds = agg['bounds']
            center_lon = (bounds[0][1] + bounds[1][1]) / 2
            center_lat = (bounds[0][0] + bounds[1][0]) / 2

            placemark_block = f'''  <Placemark>
    <name>Coverage Center</name>
    <Point>
      <coordinates>{center_lon},{center_lat},0</coordinates>
    </Point>
  </Placemark>'''

            # ---------------------------------------------------------------
            # 4. Documento KML completo
            # ---------------------------------------------------------------
            n_individual = len(results['individual'])
            kml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>RF Coverage Simulation</name>
    <description>Exported from RF Coverage Tool — {n_individual} antenna(s)</description>
{aggregated_folder}
{individual_folder}
{placemark_block}
  </Document>
</kml>'''

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(kml_content)

            self.logger.info(f"KML exportado con {n_individual} antena(s): {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Error exporting KML: {e}")
            raise
