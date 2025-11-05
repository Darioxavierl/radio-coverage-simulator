import logging

class TerrainLoader:
    def __init__(self):
        self.logger = logging.getLogger("TerrainLoader")
    
    def load(self, filename):
        self.logger.info(f"Loading terrain: {filename}")
        # TODO: Implementar carga real
        return None