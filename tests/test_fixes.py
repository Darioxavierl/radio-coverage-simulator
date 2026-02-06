"""
Test rápido para verificar las correcciones del sistema de proyectos
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.project import Project


class TestProjectFixes(unittest.TestCase):
    """Tests para verificar correcciones"""
    
    def test_project_has_methods(self):
        """Verifica que Project tiene los métodos necesarios"""
        project = Project(name="Test")
        
        # Verificar métodos existen
        self.assertTrue(hasattr(project, 'mark_as_modified'))
        self.assertTrue(hasattr(project, 'has_unsaved_changes'))
        self.assertTrue(hasattr(project, 'get_filepath'))
        self.assertTrue(callable(project.mark_as_modified))
        self.assertTrue(callable(project.has_unsaved_changes))
        self.assertTrue(callable(project.get_filepath))
    
    def test_project_created_date_auto_init(self):
        """Verifica que created_date se inicializa automáticamente"""
        project = Project(name="Test")
        
        self.assertIsNotNone(project.created_date)
        self.assertNotEqual(project.created_date, "")
        self.assertIsInstance(project.created_date, str)
    
    def test_project_filepath_none_by_default(self):
        """Verifica que filepath es None por defecto"""
        project = Project(name="Test")
        
        self.assertIsNone(project.get_filepath())
    
    def test_project_unsaved_changes_false_by_default(self):
        """Verifica que has_unsaved_changes es False por defecto"""
        project = Project(name="Test")
        
        self.assertFalse(project.has_unsaved_changes())
    
    def test_matplotlib_backend(self):
        """Verifica que matplotlib usa backend Agg"""
        # Importar heatmap_generator para que configure matplotlib
        from utils.heatmap_generator import HeatmapGenerator
        
        import matplotlib
        backend = matplotlib.get_backend()
        
        # Debe ser 'agg' o 'Agg'
        self.assertEqual(backend.lower(), 'agg')
        print(f"  ✓ Matplotlib backend: {backend}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
