@dataclass
class Site:
    """Representa un sitio/emplazamiento que puede tener múltiples antenas"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Site"
    
    # Ubicación
    latitude: float = 0.0
    longitude: float = 0.0
    ground_elevation: float = 0.0  # Elevación del terreno (msnm)
    structure_height: float = 30.0  # Altura de torre/edificio
    
    # Clasificación
    site_type: str = "Macro"  # Macro, Micro, Pico, Indoor
    environment: str = "Urban"  # Urban, Suburban, Rural
    
    # Antenas asociadas
    antenna_ids: list = field(default_factory=list)
    
    # Visualización
    color: str = "#0000FF"
    icon: str = "tower"
    visible: bool = True
    
    # Metadatos
    address: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'ground_elevation': self.ground_elevation,
            'structure_height': self.structure_height,
            'site_type': self.site_type,
            'environment': self.environment,
            'antenna_ids': self.antenna_ids,
            'color': self.color,
            'icon': self.icon,
            'visible': self.visible,
            'address': self.address,
            'notes': self.notes
        }