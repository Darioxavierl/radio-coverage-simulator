"""
Tests específicos para verificar funcionalidad GPU
Estos tests REQUIEREN GPU disponible
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from utils.gpu_detector import GPUDetector
from core.compute_engine import ComputeEngine
from core.coverage_calculator import CoverageCalculator
from core.models.traditional.free_space import FreeSpacePathLossModel
from models.antenna import Antenna, AntennaType, Technology


class TestGPUFunctionality(unittest.TestCase):
    """Tests que verifican que GPU realmente se usa"""
    
    @classmethod
    def setUpClass(cls):
        """Verificar si GPU está disponible"""
        detector = GPUDetector()
        if not detector.cupy_available:
            raise unittest.SkipTest("GPU not available - skipping GPU tests")
    
    def setUp(self):
        """Setup antes de cada test"""
        self.detector = GPUDetector()
        self.engine_gpu = ComputeEngine(use_gpu=True)
        self.engine_cpu = ComputeEngine(use_gpu=False)
    
    def test_gpu_is_actually_used(self):
        """Verifica que GPU realmente se está usando"""
        self.assertTrue(self.engine_gpu.use_gpu)
        self.assertEqual(self.engine_gpu.xp.__name__, 'cupy')
        
        # Crear array en GPU
        arr = self.engine_gpu.xp.array([1, 2, 3, 4, 5])
        
        # Verificar que es array de CuPy
        self.assertTrue(type(arr).__module__.startswith('cupy'))
    
    def test_cpu_vs_gpu_performance(self):
        """Compara performance CPU vs GPU (GPU debe ser más rápido para grids grandes)"""
        import time
        
        # Grid grande
        size = 500
        distances = np.random.rand(size, size) * 10000  # 0-10km
        frequency = 2400
        
        # Test CPU
        model_cpu = FreeSpacePathLossModel(compute_module=np)
        t0 = time.time()
        pl_cpu = model_cpu.calculate_path_loss(distances, frequency)
        time_cpu = time.time() - t0
        
        # Test GPU
        model_gpu = FreeSpacePathLossModel(compute_module=self.engine_gpu.xp)
        distances_gpu = self.engine_gpu.xp.asarray(distances)
        t0 = time.time()
        pl_gpu = model_gpu.calculate_path_loss(distances_gpu, frequency)
        time_gpu = time.time() - t0
        
        print(f"\n  CPU time: {time_cpu:.4f}s")
        print(f"  GPU time: {time_gpu:.4f}s")
        print(f"  Speedup: {time_cpu/time_gpu:.2f}x")
        
        # Verificar que resultados son iguales
        pl_gpu_cpu = self.engine_gpu.xp.asnumpy(pl_gpu)
        np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=5)
    
    def test_coverage_calculator_uses_gpu(self):
        """Verifica que CoverageCalculator use GPU cuando está disponible"""
        calc = CoverageCalculator(self.engine_gpu)
        
        # xp debe ser cupy
        self.assertEqual(calc.xp.__name__, 'cupy')
        
        # Crear antena de prueba
        antenna = Antenna(
            id="gpu_test",
            name="GPU Test Antenna",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=30,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800
        )
        
        model = FreeSpacePathLossModel(compute_module=calc.xp)
        
        # Calcular cobertura (internamente debe usar GPU)
        result = calc.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=2.0,
            resolution=100,
            model=model
        )
        
        # Resultado debe estar en CPU (numpy) por el asnumpy() final
        self.assertIsInstance(result['rsrp'], np.ndarray)
        self.assertEqual(result['rsrp'].shape, (100, 100))
    
    def test_dynamic_gpu_cpu_switch(self):
        """Verifica cambio dinámico entre GPU y CPU"""
        calc = CoverageCalculator(self.engine_gpu)
        
        # Debe empezar en GPU
        self.assertEqual(calc.xp.__name__, 'cupy')
        
        # Cambiar a CPU
        self.engine_gpu.switch_compute_mode(False)
        self.assertEqual(calc.xp.__name__, 'numpy')
        
        # Cambiar de vuelta a GPU
        self.engine_gpu.switch_compute_mode(True)
        self.assertEqual(calc.xp.__name__, 'cupy')
    
    def test_multiple_antennas_gpu(self):
        """Verifica cálculo de múltiples antenas en GPU"""
        calc = CoverageCalculator(self.engine_gpu)
        model = FreeSpacePathLossModel(compute_module=calc.xp)
        
        # Crear varias antenas
        antennas = []
        for i in range(3):
            antenna = Antenna(
                id=f"ant_{i}",
                name=f"Antenna {i}",
                latitude=-2.9 + i * 0.01,
                longitude=-79.0 + i * 0.01,
                height_agl=30,
                frequency_mhz=2400,
                tx_power_dbm=43,
                bandwidth_mhz=20,
                technology=Technology.LTE_1800,
                azimuth=i * 120  # Sectores a 120°
            )
            antennas.append(antenna)
        
        # Calcular para cada antena
        results = []
        for antenna in antennas:
            result = calc.calculate_single_antenna_quick(
                antenna=antenna,
                center_lat=-2.9,
                center_lon=-79.0,
                radius_km=1.0,
                resolution=50,
                model=model
            )
            results.append(result)
        
        # Verificar que todos tienen resultados válidos
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIn('rsrp', result)
            self.assertEqual(result['rsrp'].shape, (50, 50))


class TestCPUGPUConsistency(unittest.TestCase):
    """Tests que verifican consistencia entre CPU y GPU"""
    
    @classmethod
    def setUpClass(cls):
        """Verificar si GPU está disponible"""
        detector = GPUDetector()
        if not detector.cupy_available:
            raise unittest.SkipTest("GPU not available - skipping consistency tests")
    
    def test_free_space_consistency(self):
        """Verifica que Free Space da mismos resultados en CPU y GPU"""
        # Datos de prueba
        distances = np.array([1000, 2000, 5000, 10000, 20000]).astype(np.float64)
        frequency = 2400
        
        # CPU
        model_cpu = FreeSpacePathLossModel(compute_module=np)
        pl_cpu = model_cpu.calculate_path_loss(distances, frequency)
        
        # GPU
        import cupy as cp
        model_gpu = FreeSpacePathLossModel(compute_module=cp)
        distances_gpu = cp.asarray(distances)
        pl_gpu = model_gpu.calculate_path_loss(distances_gpu, frequency)
        pl_gpu_numpy = cp.asnumpy(pl_gpu)
        
        # Deben ser idénticos
        np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_numpy, decimal=10)
        print(f"\n  CPU: {pl_cpu}")
        print(f"  GPU: {pl_gpu_numpy}")
        print(f"  Max diff: {np.max(np.abs(pl_cpu - pl_gpu_numpy)):.2e} dB")
    
    def test_coverage_map_consistency(self):
        """Verifica que mapas de cobertura sean iguales en CPU y GPU"""
        antenna = Antenna(
            id="consistency_test",
            name="Test Antenna",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=30,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800,
            antenna_type=AntennaType.OMNIDIRECTIONAL
        )
        
        # Calcular con CPU
        engine_cpu = ComputeEngine(use_gpu=False)
        calc_cpu = CoverageCalculator(engine_cpu)
        model_cpu = FreeSpacePathLossModel(compute_module=np)
        
        result_cpu = calc_cpu.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=1.0,
            resolution=50,
            model=model_cpu
        )
        
        # Calcular con GPU
        engine_gpu = ComputeEngine(use_gpu=True)
        calc_gpu = CoverageCalculator(engine_gpu)
        model_gpu = FreeSpacePathLossModel(compute_module=calc_gpu.xp)
        
        result_gpu = calc_gpu.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=1.0,
            resolution=50,
            model=model_gpu
        )
        
        # Comparar resultados
        np.testing.assert_array_almost_equal(
            result_cpu['rsrp'], 
            result_gpu['rsrp'], 
            decimal=6,
            err_msg="CPU and GPU coverage maps differ"
        )
        
        print(f"\n  CPU RSRP range: [{result_cpu['rsrp'].min():.2f}, {result_cpu['rsrp'].max():.2f}] dBm")
        print(f"  GPU RSRP range: [{result_gpu['rsrp'].min():.2f}, {result_gpu['rsrp'].max():.2f}] dBm")
        print(f"  Max difference: {np.max(np.abs(result_cpu['rsrp'] - result_gpu['rsrp'])):.2e} dB")


if __name__ == '__main__':
    unittest.main(verbosity=2)
