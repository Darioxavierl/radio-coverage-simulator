from dataclasses import dataclass, field
from typing import List, Dict, Optional
import uuid
import json
from datetime import datetime
from models.antenna import Antenna
from models.site import Site

@dataclass
class Project:
    """Representa un proyecto completo"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Project"
    description: str = ""
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_date: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = ""
    
    # Control interno
    _filepath: Optional[str] = None  # Ruta del archivo .rfproj
    _has_unsaved_changes: bool = False  # Flag de cambios sin guardar
    
    # Configuración del proyecto
    center_lat: float = 0.0
    center_lon: float = 0.0
    zoom_level: int = 13
    terrain_file: Optional[str] = None
    
    # Referencias a entidades
    sites: Dict[str, Site] = field(default_factory=dict)
    antennas: Dict[str, Antenna] = field(default_factory=dict)
    
    # Configuración de simulación
    simulation_config: Dict = field(default_factory=dict)
    
    def save_to_file(self, filepath: str):
        """Guarda proyecto en archivo .rfproj (JSON)"""
        import json
        from datetime import datetime
        import os
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        self.modified_date = datetime.now().isoformat()
        self._filepath = filepath
        self._has_unsaved_changes = False
        
        project_data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_date': self.created_date,
            'modified_date': self.modified_date,
            'author': self.author,
            'center_lat': self.center_lat,
            'center_lon': self.center_lon,
            'zoom_level': self.zoom_level,
            'terrain_file': self.terrain_file,
            'sites': {sid: site.to_dict() for sid, site in self.sites.items()},
            'antennas': {aid: ant.to_dict() for aid, ant in self.antennas.items()},
            'simulation_config': self.simulation_config
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=4, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'Project':
        """Carga proyecto desde archivo"""
        import json
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        project = cls()
        project.id = data['id']
        project.name = data['name']
        project.description = data.get('description', '')
        project.created_date = data.get('created_date', '')
        project.modified_date = data.get('modified_date', '')
        project.author = data.get('author', '')
        project.center_lat = data['center_lat']
        project.center_lon = data['center_lon']
        project.zoom_level = data['zoom_level']
        project.terrain_file = data.get('terrain_file')
        project.simulation_config = data.get('simulation_config', {})
        
        # Cargar sitios y antenas
        project.sites = {sid: Site.from_dict(sdata) 
                        for sid, sdata in data.get('sites', {}).items()}
        project.antennas = {aid: Antenna.from_dict(adata) 
                           for aid, adata in data.get('antennas', {}).items()}
        
        # Guardar filepath y marcar como guardado
        project._filepath = filepath
        project._has_unsaved_changes = False
        
        return project
    
    def mark_as_modified(self):
        """Marca el proyecto como modificado"""
        self._has_unsaved_changes = True
    
    def has_unsaved_changes(self) -> bool:
        """Retorna si hay cambios sin guardar"""
        return self._has_unsaved_changes
    
    def get_filepath(self) -> Optional[str]:
        """Retorna la ruta del archivo del proyecto"""
        return self._filepath