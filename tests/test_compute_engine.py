"""
Tests para ComputeEngine
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from core.compute_engine import ComputeEngine


class TestComputeEngine(unittest.TestCase):
    """Test suite para ComputeEngine"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.engine_cpu = ComputeEngine(use_gpu=False)
        self.engine_gpu = ComputeEngine(use_gpu=True)
    
    def test_initialization_cpu(self):
        """Verifica inicialización en modo CPU"""
        self.assertIsNotNone(self.engine_cpu)
        self.assertFalse(self.engine_cpu.use_gpu)
        self.assertIsNotNone(self.engine_cpu.xp)
        
        # Debe ser numpy
        self.assertEqual(self.engine_cpu.xp.__name__, 'numpy')
    
    def test_initialization_gpu(self):
        """Verifica inicialización en modo GPU"""
        self.assertIsNotNone(self.engine_gpu)
        
        # Si CuPy no está disponible, debe usar CPU
        if not self.engine_gpu.gpu_detector.cupy_available:
            self.assertFalse(self.engine_gpu.use_gpu)
            self.assertEqual(self.engine_gpu.xp.__name__, 'numpy')
    
    def test_compute_operations_cpu(self):
        """Verifica operaciones básicas en CPU"""
        xp = self.engine_cpu.xp
        
        # Crear array
        arr = xp.array([1, 2, 3, 4, 5])
        self.assertEqual(len(arr), 5)
        
        # Operaciones matemáticas
        result = xp.sqrt(arr)
        self.assertEqual(len(result), 5)
        
        # Log10
        log_result = xp.log10(xp.array([10, 100, 1000]))
        expected = np.array([1, 2, 3])
        np.testing.assert_array_almost_equal(log_result, expected)
    
    def test_switch_compute_mode(self):
        """Verifica cambio entre CPU y GPU"""
        engine = ComputeEngine(use_gpu=False)
        
        # Debe estar en CPU
        self.assertFalse(engine.use_gpu)
        
        # Intentar cambiar a GPU
        success = engine.switch_compute_mode(True)
        
        # Si CuPy no disponible, no debe cambiar
        if not engine.gpu_detector.cupy_available:
            self.assertFalse(success)
            self.assertFalse(engine.use_gpu)
        
        # Cambiar de vuelta a CPU debe siempre funcionar
        success = engine.switch_compute_mode(False)
        self.assertTrue(success)
        self.assertFalse(engine.use_gpu)


if __name__ == '__main__':
    unittest.main()
