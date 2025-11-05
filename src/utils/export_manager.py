import logging

class ExportManager:
    def __init__(self):
        self.logger = logging.getLogger("ExportManager")
    
    def export_kml(self, results, filename):
        self.logger.info(f"Exporting to KML: {filename}")
        # TODO: Implementar
    
    def export_geotiff(self, results, filename):
        self.logger.info(f"Exporting to GeoTIFF: {filename}")
        # TODO: Implementar