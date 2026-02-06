"""
Tests para GPUDetector
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from utils.gpu_detector import GPUDetector


class TestGPUDetector(unittest.TestCase):
    """Test suite para GPUDetector"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.detector = GPUDetector()
    
    def test_detector_initialized(self):
        """Verifica que el detector se inicializa correctamente"""
        self.assertIsNotNone(self.detector)
        self.assertIsInstance(self.detector.has_cuda, bool)
        self.assertIsInstance(self.detector.cupy_available, bool)
        self.assertIsInstance(self.detector.device_name, str)
    
    def test_get_compute_module(self):
        """Verifica que retorna un módulo válido"""
        module = self.detector.get_compute_module()
        self.assertIsNotNone(module)
        
        # Debe tener funciones básicas de numpy
        self.assertTrue(hasattr(module, 'array'))
        self.assertTrue(hasattr(module, 'zeros'))
        self.assertTrue(hasattr(module, 'ones'))
        self.assertTrue(hasattr(module, 'log10'))
    
    def test_device_info_string(self):
        """Verifica que retorna información del dispositivo"""
        info = self.detector.get_device_info_string()
        self.assertIsInstance(info, str)
        self.assertGreater(len(info), 0)
        
        # Debe contener 'GPU' o 'CPU'
        self.assertTrue('GPU' in info or 'CPU' in info)


if __name__ == '__main__':
    unittest.main()
