import numpy as np
import base64
from io import BytesIO
import logging

# Configurar matplotlib para usar backend no-interactivo (thread-safe)
import matplotlib
matplotlib.use('Agg')  # Debe estar antes de importar pyplot

from matplotlib import pyplot as plt
from matplotlib.colors import Normalize
import matplotlib.cm as cm

class HeatmapGenerator:
    """Genera imágenes de heatmap para cobertura RF"""
    
    def __init__(self):
        self.logger = logging.getLogger("HeatmapGenerator")
    
    def generate_heatmap_image(self, rsrp_data, colormap='jet', 
                              vmin=-120, vmax=-60, alpha=0.6):
        """
        Genera imagen PNG de heatmap
        
        Args:
            rsrp_data: Array 2D con valores RSRP en dBm
            colormap: Nombre del colormap (jet, viridis, plasma, etc)
            vmin, vmax: Rango de valores para el colormap
            alpha: Transparencia (0-1)
        
        Returns:
            Imagen PNG como data URL (base64)
        """
        try:
            # Normalizar valores
            norm = Normalize(vmin=vmin, vmax=vmax)
            cmap = cm.get_cmap(colormap)
            
            # Aplicar colormap
            colored = cmap(norm(rsrp_data))
            
            # Ajustar alpha
            colored[:, :, 3] = alpha
            
            # Donde RSRP es muy bajo (< -120 dBm), hacer transparente
            mask = rsrp_data < -120
            colored[mask, 3] = 0
            
            # Convertir a imagen
            fig, ax = plt.subplots(figsize=(10, 10), dpi=100)
            ax.imshow(colored, origin='lower', interpolation='bilinear')
            ax.axis('off')
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
            
            # Guardar en memoria
            buffer = BytesIO()
            plt.savefig(buffer, format='png', transparent=True, 
                       bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            
            # Convertir a base64
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            self.logger.error(f"Error generating heatmap: {e}")
            return None
    
    def generate_geojson_heatmap(self, lats, lons, rsrp_data, threshold=-100):
        """
        Genera GeoJSON con polígonos de cobertura
        
        Args:
            lats, lons: Arrays 2D con coordenadas
            rsrp_data: Array 2D con RSRP
            threshold: Umbral en dBm para considerar cobertura
        
        Returns:
            Dict GeoJSON
        """
        # TODO: Implementar contornos de cobertura
        pass