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

    def test_azimuth_cardinal_directions(self):
        """Verifica azimuth correcto para direcciones cardinales básicas."""
        ant_lat, ant_lon = 0.0, 0.0
        lats = np.array([[1.0, 0.0, -1.0, 0.0]])
        lons = np.array([[0.0, 1.0, 0.0, -1.0]])

        azimuths = self.calculator._calculate_azimuths(ant_lat, ant_lon, lats, lons)

        expected = np.array([[0.0, 90.0, 180.0, 270.0]])
        np.testing.assert_allclose(azimuths, expected, atol=1.0)
    
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

    def test_antenna_pattern_horizontal_sectorial(self):
        """Fórmula horizontal 3GPP TR 38.901: -3 dB exacto en el borde del beamwidth."""
        import math
        antenna = self.test_antenna
        antenna.antenna_type = AntennaType.DIRECTIONAL
        antenna.azimuth = 0.0          # boresight al Norte
        antenna.horizontal_beamwidth = 60.0
        antenna.gain_dbi = 18.0

        d_deg = 0.1  # desplazamiento pequeño en grados

        # Receptor exactamente en boresight (0° de desvío) → sin atenuación
        lats_bore = np.array([[antenna.latitude + d_deg]])
        lons_bore = np.array([[antenna.longitude]])
        gain_bore = self.calculator._apply_antenna_pattern(antenna, lats_bore, lons_bore)
        self.assertAlmostEqual(float(gain_bore[0, 0]), 18.0, delta=0.1)

        # Receptor a 30° del boresight (= bw/2) → -3 dB según 3GPP §7.3.2
        lats_30 = np.array([[antenna.latitude + d_deg * math.cos(math.radians(30))]])
        lons_30 = np.array([[antenna.longitude + d_deg * math.sin(math.radians(30))]])
        gain_30 = self.calculator._apply_antenna_pattern(antenna, lats_30, lons_30)
        self.assertAlmostEqual(float(gain_30[0, 0]), 15.0, delta=0.3)  # 18 - 3 = 15 dBi

    def test_antenna_pattern_vertical_downtilt(self):
        """Patrón vertical: máxima ganancia cuando el receptor está en la dirección del tilt."""
        import math
        antenna = self.test_antenna
        antenna.antenna_type = AntennaType.DIRECTIONAL
        antenna.azimuth = 0.0
        antenna.horizontal_beamwidth = 360.0  # desactivar variación horizontal
        antenna.vertical_beamwidth = 10.0
        antenna.mechanical_tilt = 6.0
        antenna.electrical_tilt = 0.0
        antenna.gain_dbi = 18.0
        antenna.height_agl = 100.0

        tx_elevation = 0.0
        # Geometría: TX a 100m, receptor a terrain_height=0
        # Para elevation_angle = 6° → d = 100/tan(6°) ≈ 951.4 m
        d_m = 100.0 / math.tan(math.radians(6.0))
        d_deg = d_m / 111000.0
        lats = np.array([[antenna.latitude + d_deg]])
        lons = np.array([[antenna.longitude]])
        distances = np.array([[d_m]])
        terrain_heights = np.array([[0.0]])

        gain = self.calculator._apply_antenna_pattern(
            antenna, lats, lons,
            distances=distances,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation
        )
        # elevation_angle ≈ 6° = effective_tilt → v_atten = 0, h_atten = 0 → gain = 18
        self.assertAlmostEqual(float(gain[0, 0]), 18.0, delta=0.3)

        # Receptor al mismo nivel que TX (elevation_angle = 0°) → theta_diff = -6°
        terrain_heights_high = np.array([[100.0]])  # misma altura que TX
        distances_far = np.array([[10000.0]])
        lats_far = np.array([[antenna.latitude + 10000.0 / 111000.0]])
        gain_flat = self.calculator._apply_antenna_pattern(
            antenna, lats_far, lons,
            distances=distances_far,
            terrain_heights=terrain_heights_high,
            tx_elevation=tx_elevation
        )
        # elevation_angle ≈ 0°, theta_diff = -6°, v_atten = -12*(6/10)² = -4.32 dB
        expected_v_atten = -12 * (6.0 / 10.0) ** 2
        self.assertAlmostEqual(float(gain_flat[0, 0]), 18.0 + expected_v_atten, delta=0.3)

    def test_antenna_pattern_3d_combined(self):
        """Patrón 3D combinado: H+V ambos en máximo → resultado capeado a -30 dB."""
        antenna = self.test_antenna
        antenna.antenna_type = AntennaType.DIRECTIONAL
        antenna.azimuth = 0.0             # boresight al Norte
        antenna.horizontal_beamwidth = 60.0
        antenna.vertical_beamwidth = 10.0
        antenna.mechanical_tilt = 0.0
        antenna.electrical_tilt = 0.0
        antenna.gain_dbi = 18.0
        antenna.height_agl = 0.0

        # Receptor al Sur → 180° off boresight → h_atten = -30 dB (capeado)
        # Receptor 500m por debajo del TX → elevation_angle ≈ 26.6° → v_atten = -30 dB (capeado)
        d_m = 1000.0
        d_deg = d_m / 111000.0
        lats = np.array([[antenna.latitude - d_deg]])   # Sur = 180° off boresight
        lons = np.array([[antenna.longitude]])
        distances = np.array([[d_m]])
        terrain_heights = np.array([[-500.0]])  # 500m por debajo del TX

        gain = self.calculator._apply_antenna_pattern(
            antenna, lats, lons,
            distances=distances,
            terrain_heights=terrain_heights,
            tx_elevation=0.0
        )
        # combined = -min(-(-30 + -30), 30) = -30 dB → gain = 18 - 30 = -12 dBi
        self.assertAlmostEqual(float(gain[0, 0]), -12.0, delta=0.1)

    def test_antenna_pattern_no_terrain(self):
        """Sin datos de terreno → sólo patrón horizontal (retrocompatibilidad)."""
        import math
        antenna = self.test_antenna
        antenna.antenna_type = AntennaType.DIRECTIONAL
        antenna.azimuth = 0.0
        antenna.horizontal_beamwidth = 60.0
        antenna.gain_dbi = 18.0

        # Receptor a 30° del boresight = borde del haz → -3 dB
        d_deg = 0.1
        lats = np.array([[antenna.latitude + d_deg * math.cos(math.radians(30))]])
        lons = np.array([[antenna.longitude + d_deg * math.sin(math.radians(30))]])

        # Llamada sin distances/terrain_heights → retrocompatible
        gain = self.calculator._apply_antenna_pattern(antenna, lats, lons)
        self.assertTrue(np.isfinite(float(gain[0, 0])))
        self.assertAlmostEqual(float(gain[0, 0]), 15.0, delta=0.3)  # 18 - 3 = 15 dBi

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

    def test_detailed_single_coverage(self):
        """Verifica que el cálculo detallado preserve rsrp, path loss y ganancia."""
        model = FreeSpacePathLossModel(compute_module=self.calculator.xp)

        lats = np.linspace(self.test_antenna.latitude - 0.01, self.test_antenna.latitude + 0.01, 20)
        lons = np.linspace(self.test_antenna.longitude - 0.01, self.test_antenna.longitude + 0.01, 20)
        grid_lats, grid_lons = np.meshgrid(lats, lons)
        terrain_heights = np.zeros_like(grid_lats)

        result = self.calculator.calculate_single_antenna_coverage(
            antenna=self.test_antenna,
            grid_lats=grid_lats,
            grid_lons=grid_lons,
            terrain_heights=terrain_heights,
            model=model,
            return_details=True,
        )

        self.assertIn('rsrp', result)
        self.assertIn('path_loss', result)
        self.assertIn('antenna_gain', result)
        self.assertEqual(result['rsrp'].shape, grid_lats.shape)
        self.assertEqual(result['path_loss'].shape, grid_lats.shape)
        self.assertEqual(result['antenna_gain'].shape, grid_lats.shape)
    
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
