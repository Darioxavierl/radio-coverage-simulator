from PyQt6.QtCore import QObject, pyqtSignal
import logging
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from models.project import Project

class ProjectManager(QObject):
    """Gestor de proyectos con funcionalidad de listado, búsqueda y backup"""
    
    # Señales
    project_loaded = pyqtSignal(str)  # project_id
    project_saved = pyqtSignal(str)   # project_id
    project_created = pyqtSignal(str) # project_id
    
    def __init__(self, projects_dir: str = "data/projects"):
        super().__init__()
        self.logger = logging.getLogger("ProjectManager")
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.current_project: Optional[Project] = None
    
    def create_new_project(self, name: str = "Nuevo Proyecto") -> Project:
        """Crea un nuevo proyecto"""
        project = Project(name=name)
        self.current_project = project
        self.project_created.emit(project.id)
        self.logger.info(f"New project created: {name}")
        return project
    
    def load_project(self, filepath: str) -> Project:
        """Carga un proyecto desde archivo"""
        project = Project.load_from_file(filepath)
        self.current_project = project
        self.project_loaded.emit(project.id)
        self.logger.info(f"Project loaded: {filepath}")
        return project
    
    def save_project(self, project: Project, filepath: Optional[str] = None) -> str:
        """Guarda un proyecto. Si filepath es None, usa el guardado en el proyecto"""
        if filepath is None:
            filepath = project.get_filepath()
            if filepath is None:
                # Generar nombre de archivo basado en el nombre del proyecto
                safe_name = "".join(c for c in project.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filepath = str(self.projects_dir / f"{safe_name}.rfproj")
        
        project.save_to_file(filepath)
        self.project_saved.emit(project.id)
        self.logger.info(f"Project saved: {filepath}")
        return filepath
    
    def list_projects(self) -> List[dict]:
        """Lista todos los proyectos en el directorio"""
        projects = []
        
        for file_path in self.projects_dir.glob("*.rfproj"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                projects.append({
                    'filepath': str(file_path),
                    'name': data.get('name', 'Unknown'),
                    'id': data.get('id', ''),
                    'created_date': data.get('created_date', ''),
                    'modified_date': data.get('modified_date', ''),
                    'author': data.get('author', ''),
                    'description': data.get('description', ''),
                    'antenna_count': len(data.get('antennas', {})),
                    'site_count': len(data.get('sites', {}))
                })
            except Exception as e:
                self.logger.warning(f"Could not read project {file_path}: {e}")
        
        # Ordenar por fecha de modificación (más reciente primero)
        projects.sort(key=lambda x: x['modified_date'], reverse=True)
        
        return projects
    
    def delete_project(self, filepath: str) -> bool:
        """Elimina un archivo de proyecto"""
        try:
            file_path = Path(filepath)
            if file_path.exists():
                # Crear backup antes de eliminar
                self.create_backup(filepath)
                file_path.unlink()
                self.logger.info(f"Project deleted: {filepath}")
                return True
        except Exception as e:
            self.logger.error(f"Error deleting project: {e}")
        return False
    
    def create_backup(self, filepath: str) -> Optional[str]:
        """Crea un backup de un proyecto"""
        try:
            file_path = Path(filepath)
            if not file_path.exists():
                return None
            
            # Crear directorio de backups
            backup_dir = self.projects_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Nombre del backup con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_backup_{timestamp}.rfproj"
            backup_path = backup_dir / backup_name
            
            # Copiar archivo
            import shutil
            shutil.copy2(file_path, backup_path)
            
            self.logger.info(f"Backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return None
    
    def search_projects(self, query: str) -> List[dict]:
        """Busca proyectos por nombre o descripción"""
        all_projects = self.list_projects()
        query_lower = query.lower()
        
        results = [
            p for p in all_projects
            if query_lower in p['name'].lower() or 
               query_lower in p.get('description', '').lower() or
               query_lower in p.get('author', '').lower()
        ]
        
        return results
    
    def get_recent_projects(self, limit: int = 10) -> List[dict]:
        """Obtiene los proyectos más recientes"""
        projects = self.list_projects()
        return projects[:limit]
    
    def get_project_info(self, filepath: str) -> Optional[dict]:
        """Obtiene información de un proyecto sin cargarlo completamente"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'filepath': filepath,
                'name': data.get('name', 'Unknown'),
                'id': data.get('id', ''),
                'created_date': data.get('created_date', ''),
                'modified_date': data.get('modified_date', ''),
                'author': data.get('author', ''),
                'description': data.get('description', ''),
                'antenna_count': len(data.get('antennas', {})),
                'site_count': len(data.get('sites', {})),
                'center_lat': data.get('center_lat', 0),
                'center_lon': data.get('center_lon', 0)
            }
        except Exception as e:
            self.logger.error(f"Error reading project info: {e}")
            return None