"""
Tests para el sistema de proyectos (guardar/cargar)
"""
import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Agregar src al path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.project import Project
from models.antenna import Antenna, Technology, AntennaType
from models.site import Site
from core.project_manager import ProjectManager


class TestProject(unittest.TestCase):
    """Tests para la clase Project"""
    
    def setUp(self):
        """Configuración antes de cada test"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_filepath = os.path.join(self.temp_dir, "test_project.rfproj")
    
    def tearDown(self):
        """Limpieza después de cada test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_project_creation(self):
        """Verifica creación de proyecto con valores por defecto"""
        project = Project(name="Test Project")
        
        self.assertEqual(project.name, "Test Project")
        self.assertIsNotNone(project.id)
        self.assertIsNotNone(project.created_date)
        self.assertIsNotNone(project.modified_date)
        self.assertFalse(project.has_unsaved_changes())
    
    def test_project_save_and_load(self):
        """Verifica que se pueda guardar y cargar un proyecto"""
        # Crear proyecto
        project = Project(
            name="Test Project",
            description="Proyecto de prueba",
            author="Test User",
            center_lat=40.4168,
            center_lon=-3.7038,
            zoom_level=15
        )
        
        # Agregar antena
        antenna = Antenna(
            name="Test Antenna",
            latitude=40.4168,
            longitude=-3.7038,
            frequency_mhz=1800.0,
            tx_power_dbm=43.0,
            technology=Technology.LTE_1800
        )
        project.antennas[antenna.id] = antenna
        
        # Agregar sitio
        site = Site(
            name="Test Site",
            latitude=40.4168,
            longitude=-3.7038,
            site_type="Macro"
        )
        project.sites[site.id] = site
        
        # Guardar
        project.save_to_file(self.test_filepath)
        
        # Verificar que el archivo existe
        self.assertTrue(os.path.exists(self.test_filepath))
        
        # Cargar
        loaded_project = Project.load_from_file(self.test_filepath)
        
        # Verificar datos básicos
        self.assertEqual(loaded_project.id, project.id)
        self.assertEqual(loaded_project.name, "Test Project")
        self.assertEqual(loaded_project.description, "Proyecto de prueba")
        self.assertEqual(loaded_project.author, "Test User")
        self.assertEqual(loaded_project.center_lat, 40.4168)
        self.assertEqual(loaded_project.center_lon, -3.7038)
        self.assertEqual(loaded_project.zoom_level, 15)
        
        # Verificar antenas
        self.assertEqual(len(loaded_project.antennas), 1)
        loaded_antenna = list(loaded_project.antennas.values())[0]
        self.assertEqual(loaded_antenna.name, "Test Antenna")
        self.assertEqual(loaded_antenna.frequency_mhz, 1800.0)
        self.assertEqual(loaded_antenna.technology, Technology.LTE_1800)
        
        # Verificar sitios
        self.assertEqual(len(loaded_project.sites), 1)
        loaded_site = list(loaded_project.sites.values())[0]
        self.assertEqual(loaded_site.name, "Test Site")
        self.assertEqual(loaded_site.site_type, "Macro")
    
    def test_project_modification_tracking(self):
        """Verifica el tracking de cambios sin guardar"""
        project = Project(name="Test")
        
        # Recién creado, no tiene cambios sin guardar
        self.assertFalse(project.has_unsaved_changes())
        
        # Marcar como modificado
        project.mark_as_modified()
        self.assertTrue(project.has_unsaved_changes())
        
        # Guardar
        project.save_to_file(self.test_filepath)
        self.assertFalse(project.has_unsaved_changes())
    
    def test_project_filepath_tracking(self):
        """Verifica que se guarde el filepath del proyecto"""
        project = Project(name="Test")
        
        # Sin guardar, no tiene filepath
        self.assertIsNone(project.get_filepath())
        
        # Después de guardar, tiene filepath
        project.save_to_file(self.test_filepath)
        self.assertEqual(project.get_filepath(), self.test_filepath)
        
        # Al cargar, también tiene filepath
        loaded = Project.load_from_file(self.test_filepath)
        self.assertEqual(loaded.get_filepath(), self.test_filepath)
    
    def test_project_with_multiple_antennas(self):
        """Verifica proyecto con múltiples antenas"""
        project = Project(name="Multi Antenna Test")
        
        # Agregar 3 antenas
        for i in range(3):
            antenna = Antenna(
                name=f"Antenna {i+1}",
                latitude=40.0 + i*0.01,
                longitude=-3.0 + i*0.01,
                frequency_mhz=1800.0 + i*100
            )
            project.antennas[antenna.id] = antenna
        
        # Guardar y cargar
        project.save_to_file(self.test_filepath)
        loaded = Project.load_from_file(self.test_filepath)
        
        # Verificar
        self.assertEqual(len(loaded.antennas), 3)
        antenna_names = [a.name for a in loaded.antennas.values()]
        self.assertIn("Antenna 1", antenna_names)
        self.assertIn("Antenna 2", antenna_names)
        self.assertIn("Antenna 3", antenna_names)
    
    def test_project_json_structure(self):
        """Verifica la estructura del JSON guardado"""
        project = Project(
            name="Structure Test",
            description="Testing JSON structure"
        )
        project.save_to_file(self.test_filepath)
        
        # Leer JSON directamente
        with open(self.test_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verificar campos requeridos
        required_fields = [
            'id', 'name', 'description', 'created_date', 'modified_date',
            'center_lat', 'center_lon', 'zoom_level',
            'sites', 'antennas', 'simulation_config'
        ]
        
        for field in required_fields:
            self.assertIn(field, data)
    
    def test_empty_project(self):
        """Verifica que se pueda guardar y cargar un proyecto vacío"""
        project = Project(name="Empty Project")
        project.save_to_file(self.test_filepath)
        
        loaded = Project.load_from_file(self.test_filepath)
        
        self.assertEqual(loaded.name, "Empty Project")
        self.assertEqual(len(loaded.antennas), 0)
        self.assertEqual(len(loaded.sites), 0)


class TestSiteSerialization(unittest.TestCase):
    """Tests para serialización/deserialización de Site"""
    
    def test_site_to_dict(self):
        """Verifica conversión de Site a diccionario"""
        site = Site(
            name="Test Site",
            latitude=40.5,
            longitude=-3.5,
            ground_elevation=650.0,
            structure_height=40.0,
            site_type="Macro",
            environment="Urban"
        )
        
        data = site.to_dict()
        
        self.assertEqual(data['name'], "Test Site")
        self.assertEqual(data['latitude'], 40.5)
        self.assertEqual(data['site_type'], "Macro")
        self.assertEqual(data['structure_height'], 40.0)
    
    def test_site_from_dict(self):
        """Verifica creación de Site desde diccionario"""
        data = {
            'id': 'test-site-123',
            'name': "Test Site",
            'latitude': 40.5,
            'longitude': -3.5,
            'ground_elevation': 650.0,
            'structure_height': 40.0,
            'site_type': "Macro",
            'environment': "Urban",
            'antenna_ids': ['ant1', 'ant2'],
            'color': "#0000FF",
            'icon': "tower",
            'visible': True,
            'address': "Test Address",
            'notes': "Test notes"
        }
        
        site = Site.from_dict(data)
        
        self.assertEqual(site.id, 'test-site-123')
        self.assertEqual(site.name, "Test Site")
        self.assertEqual(site.latitude, 40.5)
        self.assertEqual(site.site_type, "Macro")
        self.assertEqual(len(site.antenna_ids), 2)
    
    def test_site_roundtrip(self):
        """Verifica que Site sobreviva to_dict -> from_dict"""
        original = Site(
            name="Roundtrip Test",
            latitude=40.0,
            longitude=-4.0,
            site_type="Pico"
        )
        original.antenna_ids = ['a1', 'a2', 'a3']
        
        # Convertir a dict y volver
        data = original.to_dict()
        restored = Site.from_dict(data)
        
        self.assertEqual(original.id, restored.id)
        self.assertEqual(original.name, restored.name)
        self.assertEqual(original.latitude, restored.latitude)
        self.assertEqual(original.site_type, restored.site_type)
        self.assertEqual(original.antenna_ids, restored.antenna_ids)


class TestProjectManager(unittest.TestCase):
    """Tests para ProjectManager"""
    
    def setUp(self):
        """Configuración antes de cada test"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ProjectManager(projects_dir=self.temp_dir)
    
    def tearDown(self):
        """Limpieza después de cada test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_new_project(self):
        """Verifica creación de nuevo proyecto"""
        project = self.manager.create_new_project("New Test")
        
        self.assertEqual(project.name, "New Test")
        self.assertIsNotNone(project.id)
        self.assertEqual(self.manager.current_project, project)
    
    def test_save_project_auto_filepath(self):
        """Verifica guardado automático de proyecto"""
        project = Project(name="Auto Save Test")
        
        # Guardar sin especificar filepath
        filepath = self.manager.save_project(project)
        
        self.assertTrue(os.path.exists(filepath))
        self.assertIn("Auto Save Test", filepath)
    
    def test_list_projects(self):
        """Verifica listado de proyectos"""
        # Crear varios proyectos
        for i in range(3):
            project = Project(name=f"Project {i+1}")
            self.manager.save_project(project)
        
        # Listar
        projects = self.manager.list_projects()
        
        self.assertEqual(len(projects), 3)
        names = [p['name'] for p in projects]
        self.assertIn("Project 1", names)
        self.assertIn("Project 2", names)
        self.assertIn("Project 3", names)
    
    def test_search_projects(self):
        """Verifica búsqueda de proyectos"""
        # Crear proyectos
        p1 = Project(name="Madrid Network", description="Red de Madrid")
        p2 = Project(name="Barcelona Network", description="Red de Barcelona")
        p3 = Project(name="Valencia Test", description="Prueba Valencia")
        
        self.manager.save_project(p1)
        self.manager.save_project(p2)
        self.manager.save_project(p3)
        
        # Buscar por nombre
        results = self.manager.search_projects("Madrid")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Madrid Network")
        
        # Buscar por descripción
        results = self.manager.search_projects("Barcelona")
        self.assertEqual(len(results), 1)
        
        # Buscar genérico
        results = self.manager.search_projects("Network")
        self.assertEqual(len(results), 2)
    
    def test_create_backup(self):
        """Verifica creación de backups"""
        project = Project(name="Backup Test")
        filepath = self.manager.save_project(project)
        
        # Crear backup
        backup_path = self.manager.create_backup(filepath)
        
        self.assertIsNotNone(backup_path)
        self.assertTrue(os.path.exists(backup_path))
        self.assertIn("backup", backup_path)
    
    def test_get_project_info(self):
        """Verifica obtención de info sin cargar proyecto completo"""
        project = Project(
            name="Info Test",
            description="Test description",
            author="Test Author"
        )
        
        # Agregar antenas para info
        for i in range(5):
            ant = Antenna(name=f"Ant {i}")
            project.antennas[ant.id] = ant
        
        filepath = self.manager.save_project(project)
        
        # Obtener info
        info = self.manager.get_project_info(filepath)
        
        self.assertEqual(info['name'], "Info Test")
        self.assertEqual(info['author'], "Test Author")
        self.assertEqual(info['antenna_count'], 5)
        self.assertEqual(info['site_count'], 0)


if __name__ == '__main__':
    unittest.main()
