import numpy as np
from typing import Dict, List, Tuple
from models.antenna import Antenna
from core.compute_engine import ComputeEngine
import logging

class CoverageCalculator:
    """Calcula mapas de cobertura para múltiples antenas"""
    
    def __init__(self, compute_engine: ComputeEngine):
        self.engine = compute_engine
        self.logger = logging.getLogger("CoverageCalculator")
    
    @property
    def xp(self):
        """Acceso dinámico al módulo de cómputo actual"""
        return self.engine.xp
    
    def calculate_single_antenna_coverage(
        self,
        antenna: Antenna,
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model,
        model_params: dict = None,
        return_details: bool = False
    ) -> np.ndarray:
        """
        Calcula cobertura para una antena

        Args:
            antenna: Objeto Antenna
            grid_lats: Array 2D con latitudes del grid
            grid_lons: Array 2D con longitudes del grid
            terrain_heights: Array 2D con elevaciones del terreno
            model: Modelo de propagación
            model_params: Parámetros adicionales para el modelo
            return_details: Si es True, retorna también path loss y ganancia

        Returns:
            Array 2D con RSRP en dBm para cada punto del grid o un dict detallado
        """
        self.logger.info(f"Calculating coverage for {antenna.name}")

        # Valores por defecto para model_params
        if model_params is None:
            model_params = {}

        # Convertir a GPU si está disponible
        if self.engine.use_gpu:
            grid_lats = self.xp.asarray(grid_lats)
            grid_lons = self.xp.asarray(grid_lons)
            terrain_heights = self.xp.asarray(terrain_heights)

        # Calcular distancias
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats, grid_lons
        )

        # Preparar parámetros para model.calculate_path_loss
        path_loss_args = {
            'distances': distances,
            'frequency': antenna.frequency_mhz,
            'tx_height': antenna.height_agl,
            'terrain_heights': terrain_heights
        }

        # Agregar parámetros adicionales del modelo
        path_loss_args.update(model_params)

        # Calcular path loss usando modelo
        path_loss = model.calculate_path_loss(**path_loss_args)

        # Aplicar patrón de antena
        antenna_gain = self._apply_antenna_pattern(
            antenna, grid_lats, grid_lons
        )

        # RSRP = Tx Power + Antenna Gain - Path Loss
        rsrp = antenna.tx_power_dbm + antenna_gain - path_loss

        # OPTIMIZACION: Mantener en GPU si use_gpu=True (conversión al final en multi-antenna)
        # No conversión aquí

        if return_details:
            return {
                'rsrp': rsrp,
                'path_loss': path_loss,
                'antenna_gain': antenna_gain,
            }

        return rsrp
    
    def calculate_multi_antenna_coverage(
        self,
        antennas: List[Antenna],
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model,
        model_params: dict = None
    ) -> Dict[str, np.ndarray]:
        """
        Calcula cobertura para múltiples antenas

        Args:
            antennas: Lista de antenas
            grid_lats: Array 2D con latitudes del grid
            grid_lons: Array 2D con longitudes del grid
            terrain_heights: Array 2D con elevaciones del terreno
            model: Modelo de propagación
            model_params: Parámetros adicionales para el modelo

        Returns:
            Dict con:
            - 'best_server': ID de antena con mejor señal en cada punto
            - 'rsrp': RSRP de la mejor antena en cada punto
            - 'individual': Dict con cobertura de cada antena
        """
        self.logger.info(f"Calculating coverage for {len(antennas)} antennas")

        results = {'individual': {}}

        # Calcular cobertura individual
        for antenna in antennas:
            if antenna.enabled and antenna.show_coverage:
                coverage = self.calculate_single_antenna_coverage(
                    antenna, grid_lats, grid_lons, terrain_heights, model, model_params
                )
                results['individual'][antenna.id] = coverage

        # Calcular best server (máximo RSRP en cada píxel)
        if results['individual']:
            coverage_stack = self.xp.stack(list(results['individual'].values()))  # CAMBIO: np.stack -> self.xp.stack
            antenna_ids = list(results['individual'].keys())

            best_indices = self.xp.argmax(coverage_stack, axis=0)  # CAMBIO: np.argmax -> self.xp.argmax
            results['rsrp'] = self.xp.max(coverage_stack, axis=0)  # CAMBIO: np.max -> self.xp.max

            # Crear mapa de best server (siempre NumPy, dtype=object no soportado en GPU)
            if self.engine.use_gpu:
                best_indices_numpy = self.xp.asnumpy(best_indices)
            else:
                best_indices_numpy = best_indices
                
            results['best_server'] = np.empty(best_indices_numpy.shape, dtype=object)
            for i, ant_id in enumerate(antenna_ids):
                mask = best_indices_numpy == i
                results['best_server'][mask] = ant_id
        
        # OPTIMIZACION: Convertir a CPU solo aquí, antes del return (una sola vez)
        if self.engine.use_gpu:
            if results['individual']:
                results['rsrp'] = self.xp.asnumpy(results['rsrp'])
                # best_server ya es NumPy (creado así porque dtype=object no se soporta en GPU)
            for antenna_id in results['individual'].keys():
                results['individual'][antenna_id] = self.xp.asnumpy(results['individual'][antenna_id])

        return results
    
    def _calculate_distances(self, ant_lat, ant_lon, grid_lats, grid_lons):
        """Calcula distancias usando fórmula Haversine"""
        R = 6371000  # Radio tierra en metros
        
        lat1 = self.xp.radians(ant_lat)
        lon1 = self.xp.radians(ant_lon)
        lat2 = self.xp.radians(grid_lats)
        lon2 = self.xp.radians(grid_lons)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = self.xp.sin(dlat/2)**2 + self.xp.cos(lat1) * self.xp.cos(lat2) * self.xp.sin(dlon/2)**2
        c = 2 * self.xp.arctan2(self.xp.sqrt(a), self.xp.sqrt(1-a))
        
        return R * c
    
    def _apply_antenna_pattern(self, antenna: Antenna, grid_lats, grid_lons):
        """Aplica patrón de radiación de la antena"""
        # Calcular ángulos azimuth desde la antena a cada punto
        azimuth_to_points = self._calculate_azimuths(
            antenna.latitude, antenna.longitude,
            grid_lats, grid_lons
        )
        
        # Diferencia angular respecto al azimuth de la antena
        angle_diff = self.xp.abs(azimuth_to_points - antenna.azimuth)
        angle_diff = self.xp.minimum(angle_diff, 360 - angle_diff)
        
        # Aplicar atenuación según beamwidth
        if antenna.antenna_type.value == "omnidirectional":
            horizontal_gain = self.xp.zeros_like(angle_diff)
        else:
            # Aproximación gaussiana del patrón
            horizontal_gain = -self.xp.minimum(
                12 * (angle_diff / (antenna.horizontal_beamwidth/2))**2,
                30  # Atenuación máxima 30 dB
            )
        
        return antenna.gain_dbi + horizontal_gain
    
    def _calculate_azimuths(self, ant_lat, ant_lon, grid_lats, grid_lons):
        """Calcula azimuth desde antena a cada punto"""
        lat1 = self.xp.radians(ant_lat)
        lon1 = self.xp.radians(ant_lon)
        lat2 = self.xp.radians(grid_lats)
        lon2 = self.xp.radians(grid_lons)

        dlon = lon2 - lon1

        # Bearing inicial geodésico (forward azimuth) en esfera.
        y = self.xp.sin(dlon) * self.xp.cos(lat2)
        x = (
            self.xp.cos(lat1) * self.xp.sin(lat2)
            - self.xp.sin(lat1) * self.xp.cos(lat2) * self.xp.cos(dlon)
        )

        azimuth = self.xp.degrees(self.xp.arctan2(y, x))
        azimuth = (azimuth + 360) % 360
        
        return azimuth

    def calculate_single_antenna_quick(
        self,
        antenna,
        center_lat: float,
        center_lon: float,
        radius_km: float = 5.0,
        resolution: int = 100,
        model=None,
        model_params: dict = None,
        terrain_loader=None
    ):
        """
        Cálculo rápido de cobertura en área cuadrada

        Args:
            antenna: Objeto Antenna
            center_lat, center_lon: Centro del área (normalmente la antena)
            radius_km: Radio en km desde el centro
            resolution: Puntos por lado del grid (100x100 = 10,000 puntos)
            model: Modelo de propagación a usar
            model_params: Parámetros adicionales para el modelo (environment, city_type, etc.)
            terrain_loader: TerrainLoader para obtener elevaciones (opcional)

        Returns:
            dict con 'lats', 'lons', 'rsrp' (arrays numpy)
        """
        self.logger.info(f"Quick coverage calculation for {antenna.name}")

        # Valores por defecto para model_params
        if model_params is None:
            model_params = {}

        # Convertir km a grados (aproximado)
        # 1 grado ≈ 111 km
        delta_deg = radius_km / 111.0

        # Crear grid
        lat_min = center_lat - delta_deg
        lat_max = center_lat + delta_deg
        lon_min = center_lon - delta_deg
        lon_max = center_lon + delta_deg

        lats = np.linspace(lat_min, lat_max, resolution)
        lons = np.linspace(lon_min, lon_max, resolution)

        grid_lats, grid_lons = np.meshgrid(lats, lons)

        # Obtener elevaciones del terreno
        if terrain_loader and terrain_loader.is_loaded():
            self.logger.debug("Loading terrain elevations for grid...")
            terrain_heights = terrain_loader.get_elevations_fast(grid_lats, grid_lons)
        else:
            terrain_heights = np.zeros_like(grid_lats)

        # Transferir a GPU si disponible
        if self.engine.use_gpu:
            self.logger.debug("Using GPU for calculation")
            grid_lats_gpu = self.xp.asarray(grid_lats)
            grid_lons_gpu = self.xp.asarray(grid_lons)
            terrain_heights_gpu = self.xp.asarray(terrain_heights)
        else:
            grid_lats_gpu = grid_lats
            grid_lons_gpu = grid_lons
            terrain_heights_gpu = terrain_heights

        # Calcular distancias
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats_gpu, grid_lons_gpu
        )

        # Preparar parámetros para model.calculate_path_loss
        # PHASE 3: Aplicar frequency override si está disponible
        frequency_to_use = model_params.get('frequency_override_mhz', None) or antenna.frequency_mhz

        path_loss_args = {
            'distances': distances,
            'frequency': frequency_to_use,
            'tx_height': antenna.height_agl,
            'terrain_heights': terrain_heights_gpu
        }

        # Agregar parámetros adicionales del modelo (Okumura-Hata)
        path_loss_args.update(model_params)

        path_loss = model.calculate_path_loss(**path_loss_args)

        # Aplicar patrón de antena
        antenna_gain = self._apply_antenna_pattern(
            antenna, grid_lats_gpu, grid_lons_gpu
        )

        # RSRP = Tx Power + Antenna Gain - Path Loss
        rsrp = antenna.tx_power_dbm + antenna_gain - path_loss

        # Convertir de vuelta a CPU
        if self.engine.use_gpu:
            rsrp = self.xp.asnumpy(rsrp)
            grid_lats = self.xp.asnumpy(grid_lats_gpu)
            grid_lons = self.xp.asnumpy(grid_lons_gpu)
            path_loss = self.xp.asnumpy(path_loss)
            antenna_gain = self.xp.asnumpy(antenna_gain)

        return {
            'lats': grid_lats,
            'lons': grid_lons,
            'rsrp': rsrp,
            'path_loss': path_loss,
            'antenna_gain': antenna_gain,
            'antenna_id': antenna.id
        }