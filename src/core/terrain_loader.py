import logging
import numpy as np
from pathlib import Path

class TerrainLoader:
    """
    Cargador de datos de elevación del terreno desde GeoTIFF

    Soporta archivos GeoTIFF en cualquier CRS, con transformación automática
    desde WGS84 (lat/lon) a la proyección del terreno.

    Uso:
        loader = TerrainLoader('data/terrain/cuenca_terrain.tif')
        elevation = loader.get_elevation(-2.9, -79.0)
        elevations = loader.get_elevations(lats_array, lons_array)
    """

    def __init__(self, terrain_file=None):
        """
        Inicializa el cargador de terreno

        Args:
            terrain_file: Ruta al archivo GeoTIFF (opcional)
        """
        self.logger = logging.getLogger("TerrainLoader")
        self.dataset = None
        self.data = None
        self.transformer = None
        self.bounds = None
        self.stats = {}

        if terrain_file:
            self.load(terrain_file)

    def load(self, filename):
        """
        Carga archivo GeoTIFF de elevación

        Args:
            filename: Ruta al archivo GeoTIFF

        Returns:
            bool: True si se cargó correctamente
        """
        try:
            import rasterio
            from rasterio.transform import rowcol
            from pyproj import Transformer

            filepath = Path(filename)
            if not filepath.exists():
                self.logger.error(f"Terrain file not found: {filename}")
                return False

            self.logger.info(f"Loading terrain from: {filename}")

            # Abrir dataset
            self.dataset = rasterio.open(str(filepath))
            self.data = self.dataset.read(1)  # Banda 1

            # Información del dataset
            self.logger.info(f"  CRS: {self.dataset.crs}")
            self.logger.info(f"  Dimensions: {self.data.shape}")
            self.logger.info(f"  Resolution: {self.dataset.res}")
            self.logger.info(f"  Bounds: {self.dataset.bounds}")

            # Crear transformador de coordenadas
            # De WGS84 (lat/lon, EPSG:4326) a CRS del terreno
            self.transformer = Transformer.from_crs(
                'EPSG:4326',  # WGS84 (entrada)
                self.dataset.crs,  # CRS del terreno
                always_xy=True  # Siempre (lon, lat) no (lat, lon)
            )

            # Guardar bounds
            self.bounds = self.dataset.bounds

            # Calcular estadísticas
            self._calculate_stats()

            self.logger.info(f"  Elevation range: {self.stats['min']:.1f} - {self.stats['max']:.1f} m")
            self.logger.info(f"  Mean elevation: {self.stats['mean']:.1f} m")
            self.logger.info("Terrain data loaded successfully")

            return True

        except ImportError as e:
            self.logger.error(f"Missing dependencies: {e}")
            self.logger.error("Please install: pip install rasterio pyproj")
            return False
        except Exception as e:
            self.logger.error(f"Failed to load terrain: {e}")
            return False

    def _calculate_stats(self):
        """Calcula estadísticas del terreno"""
        # Filtrar valores NoData y valores sospechosos
        # Filtro: rechazar valores < 0 (geográficamente dudosos para datos SRTM)
        # y valores > 10000m (pico más alto de Ecuador es ~6300m)

        valid_data = self.data[(self.data >= 0) & (self.data < 10000)]

        if len(valid_data) > 0:
            self.stats = {
                'min': float(np.min(valid_data)),
                'max': float(np.max(valid_data)),
                'mean': float(np.mean(valid_data)),
                'std': float(np.std(valid_data)),
                'valid_pixels': len(valid_data),
                'total_pixels': self.data.size
            }
        else:
            self.stats = {
                'min': 0, 'max': 0, 'mean': 0, 'std': 0,
                'valid_pixels': 0, 'total_pixels': 0
            }

    def get_elevation(self, lat, lon):
        """
        Obtiene elevación para un punto (lat/lon en WGS84)

        Args:
            lat: Latitud en grados
            lon: Longitud en grados

        Returns:
            float: Elevación en metros (0.0 si fuera del área)
        """
        if self.dataset is None:
            return 0.0

        try:
            from rasterio.transform import rowcol

            # Transformar a coordenadas del terreno
            x, y = self.transformer.transform(lon, lat)

            # Obtener índices del pixel
            row, col = rowcol(self.dataset.transform, x, y)

            # Verificar que está dentro del raster
            if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                elevation = float(self.data[row, col])

                # Verificar NoData y valores sospechosos (< 0 o > 10000m)
                if elevation < 0 or elevation > 10000:
                    return 0.0

                return elevation
            else:
                # Fuera del área
                return 0.0

        except Exception as e:
            self.logger.error(f"Error getting elevation for ({lat}, {lon}): {e}")
            return 0.0

    def get_elevations(self, lats, lons):
        """
        Obtiene elevaciones para arrays de coordenadas (vectorizado)

        Args:
            lats: Array numpy con latitudes
            lons: Array numpy con longitudes

        Returns:
            Array numpy con elevaciones (misma forma que entrada)
        """
        if self.dataset is None:
            return np.zeros_like(lats)

        original_shape = lats.shape
        lats_flat = lats.flatten()
        lons_flat = lons.flatten()

        elevations = np.array([
            self.get_elevation(lat, lon)
            for lat, lon in zip(lats_flat, lons_flat)
        ])

        return elevations.reshape(original_shape)

    def get_elevations_fast(self, lats, lons):
        """
        Versión optimizada de get_elevations (usa vectorización de rasterio)

        Args:
            lats: Array numpy con latitudes
            lons: Array numpy con longitudes

        Returns:
            Array numpy con elevaciones
        """
        if self.dataset is None:
            return np.zeros_like(lats)

        try:
            original_shape = lats.shape
            lats_flat = lats.flatten()
            lons_flat = lons.flatten()

            # Transformar todas las coordenadas de una vez
            xs, ys = self.transformer.transform(lons_flat, lats_flat)

            # Obtener índices de píxeles
            from rasterio.transform import rowcol
            rows, cols = rowcol(self.dataset.transform, xs, ys)

            # Inicializar array de salida
            elevations = np.zeros(len(lats_flat))

            # Extraer elevaciones
            for i, (row, col) in enumerate(zip(rows, cols)):
                if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                    elev = self.data[row, col]
                    # Filtrar NoData y valores sospechosos (0 a 10000m válido)
                    if 0 <= elev < 10000:
                        elevations[i] = elev

            return elevations.reshape(original_shape)

        except Exception as e:
            self.logger.error(f"Error in get_elevations_fast: {e}")
            return self.get_elevations(lats, lons)

    def is_loaded(self):
        """Verifica si hay datos de terreno cargados"""
        return self.dataset is not None

    def get_stats(self):
        """Retorna estadísticas del terreno"""
        return self.stats.copy() if self.stats else {}

    def close(self):
        """Cierra el dataset"""
        if self.dataset:
            self.dataset.close()
            self.dataset = None
            self.data = None
            self.logger.info("Terrain data unloaded")
