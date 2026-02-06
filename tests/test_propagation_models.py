"""
Tests para modelos de propagación
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from core.models.traditional.free_space import FreeSpacePathLossModel
from core.models.traditional.okumura_hata import OkumuraHataModel


class TestFreeSpaceModel(unittest.TestCase):
    """Test suite para Free Space Path Loss Model"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.model = FreeSpacePathLossModel()
    
    def test_initialization(self):
        """Verifica inicialización correcta"""
        self.assertIsNotNone(self.model)
        self.assertEqual(self.model.name, "Free Space Path Loss")
        self.assertIsNotNone(self.model.xp)
    
    def test_path_loss_calculation(self):
        """Verifica cálculo de path loss"""
        # Distancias de 1 km = 1000 m
        distances = np.array([1000, 2000, 5000, 10000])
        frequency = 2400  # MHz
        
        path_loss = self.model.calculate_path_loss(distances, frequency)
        
        # Verificar shape
        self.assertEqual(path_loss.shape, distances.shape)
        
        # Path loss debe aumentar con la distancia
        self.assertTrue(np.all(path_loss[1:] > path_loss[:-1]))
        
        # Valores razonables (entre 80 y 150 dB para estas distancias)
        self.assertTrue(np.all(path_loss > 80))
        self.assertTrue(np.all(path_loss < 150))
    
    def test_fspl_formula(self):
        """Verifica fórmula FSPL exacta"""
        # FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.45
        d_m = 1000  # 1 km
        f_mhz = 2400
        
        distances = np.array([d_m])
        path_loss = self.model.calculate_path_loss(distances, f_mhz)
        
        # Cálculo manual
        d_km = d_m / 1000
        expected = 20 * np.log10(d_km) + 20 * np.log10(f_mhz) + 32.45
        
        np.testing.assert_almost_equal(path_loss[0], expected, decimal=2)
    
    def test_with_cupy(self):
        """Verifica funcionamiento con CuPy si está disponible"""
        try:
            import cupy as cp
            model_gpu = FreeSpacePathLossModel(compute_module=cp)
            
            distances = cp.array([1000, 2000, 5000])
            frequency = 2400
            
            path_loss = model_gpu.calculate_path_loss(distances, frequency)
            
            # Debe ser array de CuPy
            self.assertTrue(type(path_loss).__module__.startswith('cupy'))
            
            # Verificar valores razonables
            path_loss_cpu = cp.asnumpy(path_loss)
            self.assertTrue(np.all(path_loss_cpu > 80))
            self.assertTrue(np.all(path_loss_cpu < 150))
            
            print(f"\n  GPU test passed: {path_loss_cpu}")
            
        except ImportError:
            self.skipTest("CuPy not available")


class TestOkumuraHataModel(unittest.TestCase):
    """Test suite para Okumura-Hata Model"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()
    
    def test_initialization(self):
        """Verifica inicialización correcta"""
        self.assertIsNotNone(self.model)
        self.assertIsNotNone(self.model.xp)
    
    def test_path_loss_calculation(self):
        """Verifica cálculo de path loss"""
        distances = np.array([1000, 2000, 5000, 10000])
        frequency = 1800  # MHz
        tx_height = 30  # metros
        terrain_heights = np.zeros_like(distances)
        
        path_loss = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )
        
        # Verificar shape
        self.assertEqual(path_loss.shape, distances.shape)
        
        # Path loss debe aumentar con la distancia
        self.assertTrue(np.all(path_loss[1:] > path_loss[:-1]))
        
        # Valores razonables para Okumura-Hata urbano
        self.assertTrue(np.all(path_loss > 100))
        self.assertTrue(np.all(path_loss < 180))


class TestModelConsistency(unittest.TestCase):
    """Tests de consistencia entre CPU y GPU"""
    
    def test_cpu_gpu_consistency(self):
        """Verifica que CPU y GPU dan mismos resultados"""
        try:
            import cupy as cp
            
            # Crear modelos
            model_cpu = FreeSpacePathLossModel(compute_module=np)
            model_gpu = FreeSpacePathLossModel(compute_module=cp)
            
            # Datos de prueba
            distances_cpu = np.array([1000, 2000, 5000, 10000])
            distances_gpu = cp.array([1000, 2000, 5000, 10000])
            frequency = 2400
            
            # Calcular
            pl_cpu = model_cpu.calculate_path_loss(distances_cpu, frequency)
            pl_gpu = model_gpu.calculate_path_loss(distances_gpu, frequency)
            
            # Convertir GPU a CPU
            pl_gpu_cpu = cp.asnumpy(pl_gpu)
            
            # Deben ser iguales (tolerancia por errores numéricos)
            np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=10)
            
            print(f"\n  CPU results: {pl_cpu}")
            print(f"  GPU results: {pl_gpu_cpu}")
            print(f"  Max difference: {np.max(np.abs(pl_cpu - pl_gpu_cpu)):.2e} dB")
            print("  ✅ CPU and GPU results are consistent")
            
        except ImportError:
            self.skipTest("CuPy not available - cannot test GPU consistency")


if __name__ == '__main__':
    unittest.main()
