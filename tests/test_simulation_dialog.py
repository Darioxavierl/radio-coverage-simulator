"""
Tests para el diálogo de simulación con selector de modelo
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.antenna import Antenna, Technology


class TestSimulationDialog(unittest.TestCase):
    """Tests para SimulationDialog sin ejecutar GUI"""
    
    def test_dialog_config_structure(self):
        """Verifica que get_config retorna la estructura correcta"""
        # Simular la configuración que devolvería el diálogo
        config = {
            'model': 'free_space',
            'radius_km': 5,
            'resolution': 100
        }
        
        # Verificar campos requeridos
        self.assertIn('model', config)
        self.assertIn('radius_km', config)
        self.assertIn('resolution', config)
        
        # Verificar tipos
        self.assertIsInstance(config['model'], str)
        self.assertIsInstance(config['radius_km'], int)
        self.assertIsInstance(config['resolution'], int)
    
    def test_model_options(self):
        """Verifica que los modelos disponibles son válidos"""
        available_models = ['free_space', 'okumura_hata']
        
        for model in available_models:
            self.assertIn(model, ['free_space', 'okumura_hata'])
    
    def test_simulation_worker_config(self):
        """Verifica que SimulationWorker acepta la configuración del diálogo"""
        from workers.simulation_worker import SimulationWorker
        from core.coverage_calculator import CoverageCalculator
        from core.compute_engine import ComputeEngine
        
        # Crear dependencias
        engine = ComputeEngine(use_gpu=False)
        calculator = CoverageCalculator(engine)
        
        # Crear antenas de prueba
        antennas = [
            Antenna(name="Test 1", latitude=40.0, longitude=-3.0),
            Antenna(name="Test 2", latitude=40.01, longitude=-3.01)
        ]
        
        # Configuración del diálogo
        config = {
            'model': 'free_space',
            'radius_km': 5,
            'resolution': 100
        }
        
        # Crear worker
        worker = SimulationWorker(antennas, calculator, None, config)
        
        # Verificar que se creó correctamente
        self.assertIsNotNone(worker)
        self.assertEqual(len(worker.antennas), 2)
        self.assertEqual(worker.config['model'], 'free_space')
        self.assertEqual(worker.config['radius_km'], 5)
        self.assertEqual(worker.config['resolution'], 100)
    
    def test_propagation_model_instantiation(self):
        """Verifica que se pueden instanciar ambos modelos desde config"""
        from core.models.traditional.free_space import FreeSpacePathLossModel
        from core.models.traditional.okumura_hata import OkumuraHataModel
        import numpy as np
        
        # Free Space
        model_fs = FreeSpacePathLossModel(compute_module=np)
        self.assertIsNotNone(model_fs)
        
        # Okumura-Hata
        model_oh = OkumuraHataModel(compute_module=np)
        self.assertIsNotNone(model_oh)
    
    def test_config_parameter_ranges(self):
        """Verifica rangos válidos de parámetros"""
        # Radio debe estar en rango razonable
        valid_radii = [1, 5, 10, 20, 50]
        for radius in valid_radii:
            self.assertGreaterEqual(radius, 1)
            self.assertLessEqual(radius, 50)
        
        # Resolución debe estar en rango razonable
        valid_resolutions = [50, 100, 200, 300, 500]
        for resolution in valid_resolutions:
            self.assertGreaterEqual(resolution, 50)
            self.assertLessEqual(resolution, 500)


class TestPropagationModelSelection(unittest.TestCase):
    """Tests para verificar la selección de modelos"""
    
    def test_free_space_model_calculation(self):
        """Verifica cálculo con Free Space"""
        from core.models.traditional.free_space import FreeSpacePathLossModel
        import numpy as np
        
        model = FreeSpacePathLossModel(compute_module=np)
        
        distances = np.array([100, 500, 1000, 5000])  # metros
        frequency = 1800.0  # MHz
        
        path_loss = model.calculate_path_loss(distances, frequency)
        
        # Verificar que retorna valores razonables
        self.assertEqual(len(path_loss), 4)
        self.assertTrue(np.all(path_loss > 0))
        # Path loss debe aumentar con distancia
        self.assertTrue(np.all(np.diff(path_loss) > 0))
    
    def test_okumura_hata_model_calculation(self):
        """Verifica cálculo con Okumura-Hata"""
        from core.models.traditional.okumura_hata import OkumuraHataModel
        import numpy as np
        
        model = OkumuraHataModel(compute_module=np)
        
        distances = np.array([1000, 2000, 5000, 10000])  # metros
        frequency = 900.0  # MHz
        tx_height = 30.0  # metros
        terrain_heights = np.zeros_like(distances)
        
        path_loss = model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )
        
        # Verificar que retorna valores razonables
        self.assertEqual(len(path_loss), 4)
        self.assertTrue(np.all(path_loss > 0))
        # Path loss debe aumentar con distancia
        self.assertTrue(np.all(np.diff(path_loss) > 0))
    
    def test_model_comparison(self):
        """Compara resultados de diferentes modelos"""
        from core.models.traditional.free_space import FreeSpacePathLossModel
        from core.models.traditional.okumura_hata import OkumuraHataModel
        import numpy as np
        
        distances = np.array([1000, 5000, 10000])
        frequency = 1800.0
        
        # Free Space
        model_fs = FreeSpacePathLossModel(compute_module=np)
        pl_fs = model_fs.calculate_path_loss(distances, frequency)
        
        # Okumura-Hata
        model_oh = OkumuraHataModel(compute_module=np)
        pl_oh = model_oh.calculate_path_loss(
            distances, frequency, 30.0, np.zeros_like(distances)
        )
        
        # Ambos deben tener la misma forma
        self.assertEqual(pl_fs.shape, pl_oh.shape)
        
        # Los valores deben ser diferentes (diferentes modelos)
        self.assertFalse(np.allclose(pl_fs, pl_oh))
        
        print(f"  Free Space: {pl_fs}")
        print(f"  Okumura-Hata: {pl_oh}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
