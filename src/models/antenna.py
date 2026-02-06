from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import uuid
from enum import Enum

class AntennaType(Enum):
    OMNIDIRECTIONAL = "omnidirectional"
    SECTORIAL = "sectorial"
    DIRECTIONAL = "directional"

class Technology(Enum):
    GSM_900 = "GSM 900"
    GSM_1800 = "GSM 1800"
    UMTS_2100 = "UMTS 2100"
    LTE_700 = "LTE 700"
    LTE_1800 = "LTE 1800"
    LTE_2600 = "LTE 2600"
    NR_3500 = "5G NR 3500"
    NR_28000 = "5G NR 28000"

@dataclass
class Antenna:
    """Representa una antena en el sistema"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Antenna"
    site_id: Optional[str] = None
    
    # Ubicación
    latitude: float = 0.0
    longitude: float = 0.0
    height_agl: float = 30.0  # Altura sobre el suelo (metros)
    
    # Parámetros RF
    frequency_mhz: float = 1800.0
    bandwidth_mhz: float = 20.0
    tx_power_dbm: float = 43.0
    technology: Technology = Technology.LTE_1800
    
    # Orientación
    azimuth: float = 0.0       # 0-360 grados
    mechanical_tilt: float = 0.0
    electrical_tilt: float = 0.0
    
    # Patrón de antena
    antenna_type: AntennaType = AntennaType.OMNIDIRECTIONAL  # Por defecto omnidireccional
    pattern_file: str = "sector_65deg.json"
    horizontal_beamwidth: float = 65.0
    vertical_beamwidth: float = 10.0
    gain_dbi: float = 2.0  # Ganancia típica omnidireccional: 2-3 dBi, sectorial: 15-18 dBi
    
    # Visualización
    color: str = "#FF0000"
    visible: bool = True
    show_coverage: bool = True
    
    # Metadatos
    enabled: bool = True
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario para guardar"""
        return {
            'id': self.id,
            'name': self.name,
            'site_id': self.site_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'height_agl': self.height_agl,
            'frequency_mhz': self.frequency_mhz,
            'bandwidth_mhz': self.bandwidth_mhz,
            'tx_power_dbm': self.tx_power_dbm,
            'technology': self.technology.value,
            'azimuth': self.azimuth,
            'mechanical_tilt': self.mechanical_tilt,
            'electrical_tilt': self.electrical_tilt,
            'antenna_type': self.antenna_type.value,
            'pattern_file': self.pattern_file,
            'horizontal_beamwidth': self.horizontal_beamwidth,
            'vertical_beamwidth': self.vertical_beamwidth,
            'gain_dbi': self.gain_dbi,
            'color': self.color,
            'visible': self.visible,
            'show_coverage': self.show_coverage,
            'enabled': self.enabled,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Antenna':
        """Deserializa desde diccionario"""
        antenna = cls()
        for key, value in data.items():
            if key == 'technology':
                antenna.technology = Technology(value)
            elif key == 'antenna_type':
                antenna.antenna_type = AntennaType(value)
            elif hasattr(antenna, key):
                setattr(antenna, key, value)
        return antenna