import numpy as np
import logging

class OkumuraHataModel:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("OkumuraHataModel")
    
    def calculate_path_loss(self, distances, frequency, tx_height, terrain_heights, **kwargs):
        """Cálculo simplificado de Okumura-Hata"""
        self.logger.info("Calculating path loss with Okumura-Hata")
        
        # Fórmula básica (urbana)
        hb = tx_height
        hm = 1.5  # altura móvil
        d = distances / 1000  # convertir a km
        
        # Evitar log de 0
        d = np.maximum(d, 0.001)
        
        # Okumura-Hata urbano
        path_loss = (69.55 + 26.16 * np.log10(frequency) - 13.82 * np.log10(hb) + 
                    (44.9 - 6.55 * np.log10(hb)) * np.log10(d))
        
        return path_loss