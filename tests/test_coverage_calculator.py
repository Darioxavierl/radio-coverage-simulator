"""
Tests para CoverageCalculator
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from models.antenna import Antenna, AntennaType, Technology
from core.compute_engine import ComputeEngine
from core.coverage_calculator import CoverageCalculator
from core.models.traditional.free_space import FreeSpacePathLossModel


class TestCoverageCalculator(unittest.TestCase):
    """Test suite para CoverageCalculator"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.engine = ComputeEngine(use_gpu=False)
        self.calculator = CoverageCalculator(self.engine)
        
        #Antena de prueba
        self.test_antenna = Antenna(
            id="test_001",
            name="Test Antenna",
            latitude=-2.9001,
            longitude=-79.0059,
            height_agl=30.0,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800,
            antenna_type=AntennaType.DIRECTIONAL,
            azimuth=45,
            mechanical_tilt=0,
            electrical_tilt=0,
            gain_dbi=18,
            horizontal_beamwidth=65,
            vertical_beamwidth=6.5,
            enabled=True,
            show_coverage=True
        )
    
    def test_initialization(self):
        """Verifica inicialización correcta"""
        self.assertIsNotNone(self.calculator)
        self.assertEqual(self.calculator.engine, self.engine)
    
    def test_haversine_distance(self):
        """Verifica cálculo de distancias Haversine"""
        # Distancia entre dos puntos conocidos
        lat1, lon1 = 0, 0
        lat2, lon2 = 0, 1  # 1 grado de longitud en el ecuador
        
        lats = np.array([[lat2]])
        lons = np.array([[lon2]])
        
        distances = self.calculator._calculate_distances(lat1, lon1, lats, lons)
        
        # En el ecuador, 1 grado ≈ 111 km = 111,000 m
        expected = 111000  # metros (aproximado)
        
        # Tolerancia de 5%
        self.assertAlmostEqual(distances[0, 0], expected, delta=expected * 0.05)
    
    def test_antenna_pattern_omnidirectional(self):
        """Verifica patrón omnidireccional"""
        omni_antenna = self.test_antenna
        omni_antenna.antenna_type = AntennaType.OMNIDIRECTIONAL
        
        # Grid simple
        lats = np.array([[-2.90, -2.90], [-2.91, -2.91]])
        lons = np.array([[-79.00, -79.01], [-79.00, -79.01]])
        
        gain = self.calculator._apply_antenna_pattern(omni_antenna, lats, lons)
        
        # Para omnidireccional, todos los puntos deben tener ganancia similar (± tolerancia)
        # Ganancia = gain_dbi + horizontal_gain (que es 0 para omni)
        np.testing.assert_array_almost_equal(gain, omni_antenna.gain_dbi, decimal=1)
    
    def test_quick_coverage_calculation(self):
        """Verifica cálculo rápido de cobertura"""
        model = FreeSpacePathLossModel(compute_module=self.calculator.xp)
        
        result = self.calculator.calculate_single_antenna_quick(
            antenna=self.test_antenna,
            center_lat=self.test_antenna.latitude,
            center_lon=self.test_antenna.longitude,
            radius_km=2.0,
            resolution=50,  # Grid pequeño para test rápido
            model=model
        )
        
        # Verificar estructura del resultado
        self.assertIn('lats', result)
        self.assertIn('lons', result)
        self.assertIn('rsrp', result)
        self.assertIn('antenna_id', result)
        
        # Verificar dimensiones
        self.assertEqual(result['lats'].shape, (50, 50))
        self.assertEqual(result['lons'].shape, (50, 50))
        self.assertEqual(result['rsrp'].shape, (50, 50))
        
        # Verificar valores razonables de RSRP
        # En el centro debe haber mejor señal
        center_rsrp = result['rsrp'][25, 25]
        edge_rsrp = result['rsrp'][0, 0]
        
        # Centro debe tener RSRP mayor (menos path loss)
        self.assertGreater(center_rsrp, edge_rsrp)
        
        # RSRP típico entre -120 y -40 dBm
        self.assertTrue(np.all(result['rsrp'] > -150))
        self.assertTrue(np.all(result['rsrp'] < 50))
    
    def test_dynamic_xp_property(self):
        """Verifica que xp es dinámico y se actualiza con engine"""
        # xp inicial debe ser numpy
        self.assertEqual(self.calculator.xp.__name__, 'numpy')
        
        # Cambiar engine a GPU (si disponible)
        success = self.engine.switch_compute_mode(True)
        
        if success and self.engine.use_gpu:
            # xp debe actualizarse automáticamente
            self.assertEqual(self.calculator.xp.__name__, 'cupy')
        
        # Cambiar de vuelta a CPU
        self.engine.switch_compute_mode(False)
        self.assertEqual(self.calculator.xp.__name__, 'numpy')


class TestCoverageCalculatorGPU(unittest.TestCase):
    """Tests específicos para GPU"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.engine = ComputeEngine(use_gpu=True)
        
        # Skip si GPU no disponible
        if not self.engine.use_gpu:
            self.skipTest("GPU not available")
        
        self.calculator = CoverageCalculator(self.engine)
        
        self.test_antenna = Antenna(
            id="test_gpu",
            name="Test GPU Antenna",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=30.0,
            frequency_mhz=2400,
            tx_power_dbm=43,
            bandwidth_mhz=20,
            technology=Technology.LTE_1800,
            antenna_type=AntennaType.OMNIDIRECTIONAL,
            azimuth=0,
            mechanical_tilt=0,
            electrical_tilt=0,
            gain_dbi=15,
            horizontal_beamwidth=360,
            vertical_beamwidth=20
        )
    
    def test_gpu_calculation(self):
        """Verifica cálculo en GPU"""
        model = FreeSpacePathLossModel(compute_module=self.calculator.xp)
        
        result = self.calculator.calculate_single_antenna_quick(
            antenna=self.test_antenna,
            center_lat=self.test_antenna.latitude,
            center_lon=self.test_antenna.longitude,
            radius_km=1.0,
            resolution=30,
            model=model
        )
        
        # Resultado debe estar en CPU (numpy)
        self.assertIsInstance(result['rsrp'], np.ndarray)
        
        # Verificar valores
        self.assertEqual(result['rsrp'].shape, (30, 30))


if __name__ == '__main__':
    unittest.main()
