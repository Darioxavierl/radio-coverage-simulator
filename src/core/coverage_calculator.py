import numpy as np
from typing import Dict, List, Tuple
from models.antenna import Antenna
from core.compute_engine import ComputeEngine
import logging

class CoverageCalculator:
    """Calcula mapas de cobertura para múltiples antenas"""
    
    def __init__(self, compute_engine: ComputeEngine):
        self.engine = compute_engine
        self.xp = compute_engine.xp
        self.logger = logging.getLogger("CoverageCalculator")
    
    def calculate_single_antenna_coverage(
        self, 
        antenna: Antenna,
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model
    ) -> np.ndarray:
        """
        Calcula cobertura para una antena
        
        Returns:
            Array 2D con RSRP en dBm para cada punto del grid
        """
        self.logger.info(f"Calculating coverage for {antenna.name}")
        
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
        
        # Calcular path loss usando modelo
        path_loss = model.calculate_path_loss(
            distances=distances,
            frequency=antenna.frequency_mhz,
            tx_height=antenna.height_agl,
            terrain_heights=terrain_heights
        )
        
        # Aplicar patrón de antena
        antenna_gain = self._apply_antenna_pattern(
            antenna, grid_lats, grid_lons
        )
        
        # RSRP = Tx Power + Antenna Gain - Path Loss
        rsrp = antenna.tx_power_dbm + antenna_gain - path_loss
        
        # Convertir de vuelta a CPU si es necesario
        if self.engine.use_gpu:
            rsrp = self.xp.asnumpy(rsrp)
        
        return rsrp
    
    def calculate_multi_antenna_coverage(
        self,
        antennas: List[Antenna],
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model
    ) -> Dict[str, np.ndarray]:
        """
        Calcula cobertura para múltiples antenas
        
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
                    antenna, grid_lats, grid_lons, terrain_heights, model
                )
                results['individual'][antenna.id] = coverage
        
        # Calcular best server (máximo RSRP en cada píxel)
        if results['individual']:
            coverage_stack = np.stack(list(results['individual'].values()))
            antenna_ids = list(results['individual'].keys())
            
            best_indices = np.argmax(coverage_stack, axis=0)
            results['rsrp'] = np.max(coverage_stack, axis=0)
            
            # Crear mapa de best server
            results['best_server'] = np.empty(best_indices.shape, dtype=object)
            for i, ant_id in enumerate(antenna_ids):
                mask = best_indices == i
                results['best_server'][mask] = ant_id
        
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
        dlat = grid_lats - ant_lat
        dlon = grid_lons - ant_lon
        
        azimuth = self.xp.degrees(self.xp.arctan2(dlon, dlat))
        azimuth = (azimuth + 360) % 360
        
        return azimuth

    def calculate_single_antenna_quick(
        self,
        antenna,
        center_lat: float,
        center_lon: float,
        radius_km: float = 5.0,
        resolution: int = 100,
        model=None
    ):
        """
        Cálculo rápido de cobertura en área cuadrada
        
        Args:
            antenna: Objeto Antenna
            center_lat, center_lon: Centro del área (normalmente la antena)
            radius_km: Radio en km desde el centro
            resolution: Puntos por lado del grid (100x100 = 10,000 puntos)
            model: Modelo de propagación a usar
        
        Returns:
            dict con 'lats', 'lons', 'rsrp' (arrays numpy)
        """
        self.logger.info(f"Quick coverage calculation for {antenna.name}")
        
        import numpy as np
        
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
        
        # Transferir a GPU si disponible
        if self.engine.use_gpu:
            print("Uso GPU")
            grid_lats_gpu = self.xp.asarray(grid_lats)
            grid_lons_gpu = self.xp.asarray(grid_lons)
        else:
            grid_lats_gpu = grid_lats
            grid_lons_gpu = grid_lons
        
        # Calcular distancias
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats_gpu, grid_lons_gpu
        )
        
        # Path loss
        terrain_heights = self.xp.zeros_like(distances)  # Terreno plano por ahora
        
        path_loss = model.calculate_path_loss(
            distances=distances,
            frequency=antenna.frequency_mhz,
            tx_height=antenna.height_agl,
            terrain_heights=terrain_heights
        )
        
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
        
        return {
            'lats': grid_lats,
            'lons': grid_lons,
            'rsrp': rsrp,
            'antenna_id': antenna.id
        }