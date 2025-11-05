import logging

class FreeSpacePathLossModel:
    """
    Modelo de pérdidas de espacio libre (FSPL)
    
    FSPL(dB) = 20*log10(d) + 20*log10(f) + 32.45
    donde:
    - d = distancia en km
    - f = frecuencia en MHz
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.logger = logging.getLogger("FreeSpaceModel")
        self.name = "Free Space Path Loss"
    
    def calculate_path_loss(self, distances, frequency, tx_height=None, 
                           terrain_heights=None, **kwargs):
        """
        Calcula pérdida de trayecto en espacio libre
        
        Args:
            distances: Array con distancias en METROS
            frequency: Frecuencia en MHz
            tx_height: Altura antena (no se usa en FSPL básico)
            terrain_heights: Alturas terreno (no se usa en FSPL básico)
        
        Returns:
            Array con path loss en dB
        """
        import numpy as np
        
        # Convertir distancias de metros a kilómetros
        d_km = distances / 1000.0
        
        # Evitar log de 0 (mínimo 1 metro = 0.001 km)
        d_km = np.maximum(d_km, 0.001)
        
        # FSPL = 20*log10(d_km) + 20*log10(f_MHz) + 32.45
        fspl = 20 * np.log10(d_km) + 20 * np.log10(frequency) + 32.45
        
        self.logger.debug(f"Calculated FSPL for f={frequency}MHz, "
                         f"d_min={d_km.min():.3f}km, d_max={d_km.max():.3f}km")
        
        return fspl
    
    def get_coverage_map(self, antenna_params, terrain_data, compute_engine):
        """Interfaz para compatibilidad (no usado directamente)"""
        pass