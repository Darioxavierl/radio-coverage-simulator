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

    def get_radial_profiles(self, tx_lat, tx_lon, rx_lats, rx_lons, n_samples=50, max_distance_m=None):
        """
        Extrae perfiles de elevación radiales TX → cada receptor (o hasta max_distance_m).

        Para cada receptor i, muestrea n_samples puntos equiespaciados a lo largo
        de la línea TX → receptor_i y retorna sus elevaciones.
        
        ✅ FIX: Parámetro max_distance_m permite extender perfiles hasta 15km para ITU-R P.1546
        (backward compatible: None = comportamiento actual)

        Args:
            tx_lat: Latitud del transmisor (escalar)
            tx_lon: Longitud del transmisor (escalar)
            rx_lats: Array (N,) de latitudes de receptores
            rx_lons: Array (N,) de longitudes de receptores
            n_samples: Número de muestras por perfil (default: 50)
            max_distance_m: Distancia máxima de perfil en metros (optional)
                           - None (default): usa comportamiento actual (hasta receptor)
                           - número: extiende perfil hasta max_distance_m

        Returns:
            Array (N, n_samples) con elevaciones del terreno por perfil.
            Retorna zeros si el terreno no está cargado.
        """
        rx_lats = np.asarray(rx_lats).ravel()
        rx_lons = np.asarray(rx_lons).ravel()
        n_receptors = len(rx_lats)

        if self.dataset is None:
            return np.zeros((n_receptors, n_samples))

        # ✅ FIX: Calcular distancia real para cada receptor
        distances = self._haversine_distance(
            tx_lat, tx_lon,
            rx_lats, rx_lons
        )  # (N,) - distancia de cada receptor desde TX
        
        # ✅ FIX: Usar max_distance_m si se proporciona (extender hasta 15 km para ITU)
        if max_distance_m is not None:
            max_distances = np.maximum(distances, max_distance_m)
        else:
            max_distances = distances  # Comportamiento actual: hasta receptor

        # Parámetro lineal [0, 1] para interpolar TX → max_distances[i]
        t = np.linspace(0.0, 1.0, n_samples)  # (n_samples,)

        # ✅ FIX: Generar waypoints hasta max_distances en lugar de solo hasta receptor
        # Calcular dirección unitaria hacia cada receptor
        direction_lat = (rx_lats - tx_lat) / (distances + 1e-10)  # Normalizar, evitar /0
        direction_lon = (rx_lons - tx_lon) / (distances + 1e-10)
        
        # Interpolar: punto[i,j] = TX + direction[i] * max_distances[i] * t[j]
        all_lats = tx_lat + np.outer(direction_lat * max_distances, t)  # (N, n_samples)
        all_lons = tx_lon + np.outer(direction_lon * max_distances, t)  # (N, n_samples)

        self.logger.info(f"get_radial_profiles: n_receptors={n_receptors}, n_samples={n_samples}, all_lats.shape={all_lats.shape}")

        # Aplanar para un único call vectorizado
        elevations_flat = self.get_elevations_fast(
            all_lats.ravel(), all_lons.ravel()
        )  # (N * n_samples,)

        self.logger.info(f"get_elevations_fast returned shape {elevations_flat.shape}, will reshape to ({n_receptors}, {n_samples})")
        
        result = elevations_flat.reshape(n_receptors, n_samples)
        self.logger.info(f"After reshape: result.shape={result.shape}")
        
        return result

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
    
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calcula distancia Haversine entre dos puntos (lat/lon)
        
        Args:
            lat1, lon1: Punto 1 en grados decimales
            lat2, lon2: Punto 2 en grados decimales
        
        Returns:
            Distancia en metros
        """
        # Radio terrestre en metros
        R = 6.371e6
        
        # Convertir a radianes
        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)
        
        # Diferencias
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Fórmula Haversine
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        distance = R * c
        
        return distance
    
    
    def get_profile_distances(self, tx_lat, tx_lon, rx_lats, rx_lons, n_samples=50, max_distance_m=None):
        """
        Calcula distancias Haversine para muestras de perfil radial.
        
        ✅ VERSIÓN SEGURA: Mantiene comportamiento original cuando max_distance_m=None
        
        Para cada receptor i, retorna array de n_samples distancias Haversine
        desde TX hasta cada punto del perfil radial.
        
        - Si max_distance_m=None (default): Usa interpolación lineal en lat/lon
          → Comportamiento original, no afecta otros modelos
        - Si max_distance_m especificado: Usa fórmula inversa Haversine para distancias EXACTAS
          → ITU-R P.1546 obtiene puntos a 0, 300m, 600m, ..., 15000m exactos
        
        Args:
            tx_lat: Latitud del transmisor (escalar)
            tx_lon: Longitud del transmisor (escalar)
            rx_lats: Array (N,) de latitudes de receptores
            rx_lons: Array (N,) de longitudes de receptores
            n_samples: Número de muestras por perfil (default: 50)
            max_distance_m: Distancia máxima de perfil en metros (optional)
                           - None: usa interpolación lineal (comportamiento original)
                           - número: extiende a esa distancia con precisión Haversine
        
        Returns:
            Array (N, n_samples) con distancias en metros desde TX
        """
        rx_lats = np.asarray(rx_lats).ravel()
        rx_lons = np.asarray(rx_lons).ravel()
        n_receptors = len(rx_lats)
        
        # ============================================================================
        # CASO 1: max_distance_m=None → COMPORTAMIENTO ORIGINAL (otros modelos)
        # ============================================================================
        if max_distance_m is None:
            # Calcular distancia real para cada receptor
            distances_to_rx = self._haversine_distance(
                tx_lat, tx_lon,
                rx_lats, rx_lons
            )  # (N,)
            
            # Parámetro lineal [0, 1] para interpolar TX → RX
            t = np.linspace(0.0, 1.0, n_samples)  # (n_samples,)
            
            # Generar waypoints con interpolación lineal en lat/lon
            all_lats = tx_lat + np.outer(rx_lats - tx_lat, t)  # (N, n_samples)
            all_lons = tx_lon + np.outer(rx_lons - tx_lon, t)  # (N, n_samples)
            
            # Calcular distancias Haversine desde TX a cada waypoint
            distances = self._haversine_distance(
                tx_lat,  # Escalar (TX)
                tx_lon,  # Escalar (TX)
                all_lats,  # (N, n_samples)
                all_lons  # (N, n_samples)
            )
            
            self.logger.info(f"get_profile_distances: n_receptors={n_receptors}, n_samples={n_samples}, "
                            f"distances shape={distances.shape}, "
                            f"range=[{np.min(distances):.1f}, {np.max(distances):.1f}] m "
                            f"(original behavior: linear interpolation)")
            
            return distances
        
        # ============================================================================
        # CASO 2: max_distance_m especificado → PRECISION HAVERSINE (ITU-R P.1546)
        # ============================================================================
        
        # Calcular distancia y rumbo real para cada receptor
        distances_to_rx = self._haversine_distance(
            tx_lat, tx_lon,
            rx_lats, rx_lons
        )  # (N,)
        
        # Usar max_distance_m si es mayor que distancia al receptor
        max_distances = np.maximum(distances_to_rx, max_distance_m)
        
        # Calcular rumbo (bearing) desde TX a cada receptor
        # bearing = atan2(sin(Δλ)*cos(φ2), cos(φ1)*sin(φ2) − sin(φ1)*cos(φ2)*cos(Δλ))
        tx_lat_rad = np.radians(tx_lat)
        rx_lats_rad = np.radians(rx_lats)
        delta_lon = np.radians(rx_lons - tx_lon)
        
        y = np.sin(delta_lon) * np.cos(rx_lats_rad)
        x = np.cos(tx_lat_rad) * np.sin(rx_lats_rad) - np.sin(tx_lat_rad) * np.cos(rx_lats_rad) * np.cos(delta_lon)
        bearings = np.arctan2(y, x)  # (N,) - en radianes
        
        # Generar distancias exactas para cada muestra (lineal desde 0 a max_dist)
        distances_samples = np.linspace(0.0, 1.0, n_samples)  # [0, 1/(n-1), ..., 1]
        distances_array = np.outer(max_distances, distances_samples)  # (N, n_samples)
        
        # Convertir distancias a lat/lon usando fórmula de destino Haversine inversa
        # dest_lat = asin(sin(tx_lat)*cos(d) + cos(tx_lat)*sin(d)*cos(bearing))
        # dest_lon = tx_lon + atan2(sin(bearing)*sin(d)*cos(tx_lat), cos(d) - sin(tx_lat)*sin(dest_lat))
        
        R = 6371000.0  # Radio de la Tierra en metros
        delta_angles = distances_array / R  # Ángulo subtendido (radianes)
        
        # Broadcast para cálculos vectorizados
        bearings_col = bearings[:, np.newaxis]  # (N, 1)
        
        # Calcular lat/lon de destino usando fórmula inversa Haversine
        dest_lats_rad = np.arcsin(
            np.sin(tx_lat_rad) * np.cos(delta_angles) +
            np.cos(tx_lat_rad) * np.sin(delta_angles) * np.cos(bearings_col)
        )
        
        dest_lons_rad = tx_lon * np.pi/180.0 + np.arctan2(
            np.sin(bearings_col) * np.sin(delta_angles) * np.cos(tx_lat_rad),
            np.cos(delta_angles) - np.sin(tx_lat_rad) * np.sin(dest_lats_rad)
        )
        
        # Convertir de vuelta a grados
        dest_lats = np.degrees(dest_lats_rad)
        dest_lons = np.degrees(dest_lons_rad)
        
        # Calcular distancias Haversine reales (verificación)
        actual_distances = self._haversine_distance(
            tx_lat,
            tx_lon,
            dest_lats,  # (N, n_samples)
            dest_lons   # (N, n_samples)
        )
        
        self.logger.info(f"get_profile_distances: n_receptors={n_receptors}, n_samples={n_samples}, "
                        f"distances shape={actual_distances.shape}, "
                        f"range=[{np.min(actual_distances):.1f}, {np.max(actual_distances):.1f}] m "
                        f"(Haversine inverse precision for ITU-R P.1546)")
        
        return actual_distances
    
    
    def get_smoothed_profiles(self, terrain_profiles, window_size_m=1000.0, profile_distances=None):
        """
        Aplica suavizado Gaussian (smooth-earth) a perfiles de elevación.
        
        FASE 1 - Paso 1.2: Suavizado de terreno para difracción correcta
        
        El suavizado Gaussian simula el efecto de earth-curvature y simplifica
        la determinación de obstáculos para cálculos de difracción.
        
        Args:
            terrain_profiles: Array (N, n_samples) con elevaciones en msnm
            window_size_m: Tamaño de ventana Gaussian en metros (default: 1km)
            profile_distances: Array (N, n_samples) con distancias desde TX (opcional)
                             Si no se proporciona, usa índices como proxy
        
        Returns:
            Array (N, n_samples) con perfiles suavizados en msnm
        """
        from scipy.ndimage import gaussian_filter1d
        
        terrain_profiles = np.asarray(terrain_profiles)
        n_receptors, n_samples = terrain_profiles.shape
        
        # Si no se proporcionan distancias, usar índices como proxy
        # Window size en términos de índices de muestra
        if profile_distances is None:
            # Asumir que n_samples corresponden a 15 km (rango estándar h_eff)
            max_distance = 15000  # metros
            window_indices = int(window_size_m / (max_distance / n_samples))
        else:
            # Calcular sigma en términos de índices usando distancias reales
            # Convertir window_size_m a índices usando spacing medio
            profile_distances = np.asarray(profile_distances)
            
            # Calcular espaciado promedio entre muestras
            spacing_m = np.mean(np.diff(profile_distances, axis=1))
            window_indices = max(1, int(window_size_m / spacing_m))
        
        # Sigma para Gaussian (window_indices ~= 3*sigma para corte ~99%)
        sigma = window_indices / 3.0
        
        # Aplicar filtro Gaussian 1D a cada perfil
        smoothed = np.zeros_like(terrain_profiles)
        for i in range(n_receptors):
            smoothed[i, :] = gaussian_filter1d(terrain_profiles[i, :], sigma=sigma, mode='nearest')
        
        # Calcular estadísticas de suavizado
        diff_dB_equivalent = 10 * np.log10(np.maximum(np.abs(smoothed - terrain_profiles), 1e-3))
        mean_smoothing_db = np.mean(diff_dB_equivalent)
        max_smoothing_db = np.max(diff_dB_equivalent)
        
        self.logger.info(f"get_smoothed_profiles: window_size={window_size_m:.0f}m, sigma={sigma:.2f} indices, "
                        f"mean_smoothing={mean_smoothing_db:.2f} dB, max_smoothing={max_smoothing_db:.2f} dB")
        
        return smoothed
