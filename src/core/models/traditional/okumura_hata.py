import numpy as np
import logging

class OkumuraHataModel:
    def __init__(self, config=None, compute_module=None):
        self.config = config or {}
        self.logger = logging.getLogger("OkumuraHataModel")
        # Permitir usar numpy o cupy
        self.xp = compute_module if compute_module is not None else np
    
    def calculate_path_loss(self, distances, frequency, tx_height, terrain_heights, **kwargs):
        """
        Cálculo simplificado de Okumura-Hata (modelo urbano)
        
        Nota: Este modelo usa la altura de la antena (tx_height) pero no requiere
        perfil detallado del terreno. La altura del receptor se asume típica (1.5m).
        Para implementación completa con correcciones de terreno, se necesitarían
        datos DEM/DTED que se cargarían desde archivos externos.
        
        Args:
            distances: Distancias en metros
            frequency: Frecuencia en MHz (150-1500 MHz)
            tx_height: Altura de antena transmisora en metros (30-200m típico)
            terrain_heights: Alturas del terreno (no usado en esta versión simplificada)
        """
        self.logger.debug("Calculating path loss with Okumura-Hata")
        
        # Fórmula básica (urbana)
        hb = tx_height
        hm = 1.5  # altura móvil
        d = distances / 1000  # convertir a km
        
        # Evitar log de 0
        d = self.xp.maximum(d, 0.001)
        
        # Okumura-Hata urbano
        path_loss = (69.55 + 26.16 * self.xp.log10(frequency) - 13.82 * self.xp.log10(hb) + 
                    (44.9 - 6.55 * self.xp.log10(hb)) * self.xp.log10(d))
        
        return path_loss