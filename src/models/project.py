@dataclass
class Project:
    """Representa un proyecto completo"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Project"
    description: str = ""
    created_date: str = ""
    modified_date: str = ""
    author: str = ""
    
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
        
        self.modified_date = datetime.now().isoformat()
        
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
        
        return project