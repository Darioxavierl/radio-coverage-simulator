from typing import List, Optional, Dict
from models.antenna import Antenna
from PyQt6.QtCore import QObject, pyqtSignal
import logging

class AntennaManager(QObject):
    """Gestiona todas las antenas del proyecto"""
    
    # Señales para actualizar UI
    antenna_added = pyqtSignal(str)  # antenna_id
    antenna_removed = pyqtSignal(str)
    antenna_modified = pyqtSignal(str)
    antenna_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.antennas: Dict[str, Antenna] = {}
        self.selected_antenna_id: Optional[str] = None
        self.logger = logging.getLogger("AntennaManager")
    
    def add_antenna(self, antenna: Antenna) -> str:
        """Agrega nueva antena"""
        self.antennas[antenna.id] = antenna
        self.logger.info(f"Antenna added: {antenna.name} ({antenna.id})")
        self.antenna_added.emit(antenna.id)
        return antenna.id
    
    def create_antenna_at_location(self, lat: float, lon: float, 
                                   site_id: Optional[str] = None) -> str:
        """Crea antena en ubicación específica"""
        antenna = Antenna(
            latitude=lat,
            longitude=lon,
            site_id=site_id,
            name=f"Antenna {len(self.antennas) + 1}"
        )
        return self.add_antenna(antenna)
    
    def remove_antenna(self, antenna_id: str) -> bool:
        """Elimina antena"""
        if antenna_id in self.antennas:
            del self.antennas[antenna_id]
            self.logger.info(f"Antenna removed: {antenna_id}")
            self.antenna_removed.emit(antenna_id)
            return True
        return False
    
    def update_antenna(self, antenna_id: str, **kwargs):
        """Actualiza propiedades de antena"""
        if antenna_id in self.antennas:
            antenna = self.antennas[antenna_id]
            for key, value in kwargs.items():
                if hasattr(antenna, key):
                    setattr(antenna, key, value)
            self.logger.info(f"Antenna updated: {antenna_id}")
            self.antenna_modified.emit(antenna_id)
    
    def get_antenna(self, antenna_id: str) -> Optional[Antenna]:
        """Obtiene antena por ID"""
        return self.antennas.get(antenna_id)
    
    def get_all_antennas(self) -> List[Antenna]:
        """Obtiene todas las antenas"""
        return list(self.antennas.values())
    
    def get_enabled_antennas(self) -> List[Antenna]:
        """Obtiene solo antenas habilitadas"""
        return [ant for ant in self.antennas.values() if ant.enabled]
    
    def select_antenna(self, antenna_id: Optional[str]):
        """Selecciona antena"""
        self.selected_antenna_id = antenna_id
        if antenna_id:
            self.antenna_selected.emit(antenna_id)
    
    def move_antenna(self, antenna_id: str, new_lat: float, new_lon: float):
        """Mueve antena a nueva ubicación"""
        self.update_antenna(antenna_id, latitude=new_lat, longitude=new_lon)
    
    def duplicate_antenna(self, antenna_id: str) -> Optional[str]:
        """Duplica antena existente"""
        original = self.get_antenna(antenna_id)
        if original:
            import copy
            new_antenna = copy.deepcopy(original)
            new_antenna.id = str(uuid.uuid4())
            new_antenna.name = f"{original.name} (Copy)"
            # Desplazar ligeramente
            new_antenna.latitude += 0.001
            new_antenna.longitude += 0.001
            return self.add_antenna(new_antenna)
        return None