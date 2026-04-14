"""
Test Suite para ITU-R P.1546 Propagation Model

Tests de modelo para:
- Inicialización
- Cálculos básicos
- Radio horizon y LOS/NLOS
- Correcciones ambientales y de terreno
- Rango de frecuencias (30-4000 MHz)
- Rango de distancias (1-1000 km)
- Correcciones de altura
- Validaciones y edge cases
- Consistencia CPU/GPU

Universidad de Cuenca, 2025
"""

import unittest
import sys
import numpy as np
from pathlib import Path

# Agregar directorio raiz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models.traditional.itu_r_p1546 import ITUR_P1546Model

# Try GPU support
try:
    import cupy as cp
    HAS_CUPY = True
except ImportError:
    HAS_CUPY = False
    cp = None


class TestITUR_P1546Initialization(unittest.TestCase):
    """Tests: Instanciación del modelo ITU-R P.1546"""

    def test_instantiate_with_defaults(self):
        """Test: ITU-R P.1546 se instancia con valores por defecto"""
        model = ITUR_P1546Model()

        self.assertIsNotNone(model)
        self.assertEqual(model.name, "ITU-R P.1546")
        self.assertEqual(model.defaults['environment'], 'Urban')
        self.assertEqual(model.defaults['terrain_type'], 'mixed')

    def test_instantiate_with_custom_config(self):
        """Test: ITU-R P.1546 se instancia con config personalizada"""
        config = {
            'environment': 'Rural',
            'terrain_type': 'irregular',
            'mobile_height': 2.0
        }
        model = ITUR_P1546Model(config=config)

        self.assertEqual(model.defaults['environment'], 'Rural')
        self.assertEqual(model.defaults['terrain_type'], 'irregular')
        self.assertEqual(model.defaults['mobile_height'], 2.0)

    def test_instantiate_with_numpy_module(self):
        """Test: ITU-R P.1546 se instancia con NumPy"""
        model = ITUR_P1546Model(compute_module=np)
        self.assertEqual(model.xp, np)

    @unittest.skipIf(not HAS_CUPY, "CuPy not available")
    def test_instantiate_with_cupy(self):
        """Test: ITU-R P.1546 se instancia con CuPy"""
        model = ITUR_P1546Model(compute_module=cp)
        self.assertEqual(model.xp, cp)

    def test_model_metadata(self):
        """Test: Metadatos del modelo son correctos"""
        model = ITUR_P1546Model()
        info = model.get_model_info()

        self.assertIn('name', info)
        self.assertIn('frequency_range', info)
        self.assertIn('distance_range', info)
        self.assertIn('environments', info)
        self.assertTrue(info['has_terrain_awareness'])
        self.assertTrue(info['has_los_nlos'])


class TestITUR_P1546BasicCalculation(unittest.TestCase):
    """Tests: Cálculos básicos funcionan"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([1000.0, 5000.0, 10000.0])  # metros
        self.terrain = np.array([2500.0, 2500.0, 2500.0])

    def test_basic_path_loss_calculation(self):
        """Test: Cálculo básico de path loss funciona"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        self.assertEqual(pl.shape, self.distances.shape)
        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_path_loss_increases_with_distance(self):
        """Test: Path loss aumenta con distancia"""
        distances_test = np.array([1000.0, 2000.0, 5000.0, 10000.0])
        terrain_test = np.zeros(len(distances_test))

        pl = self.model.calculate_path_loss(
            distances=distances_test,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_test
        )

        diffs = np.diff(pl)
        self.assertTrue(np.all(diffs > 0), "Path loss debe aumentar con distancia")

    def test_path_loss_increases_with_frequency(self):
        """Test: Path loss aumenta con frecuencia"""
        pl_30 = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=30.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )[0]

        pl_900 = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )[0]

        pl_4000 = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=4000.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )[0]

        self.assertLess(pl_30, pl_900, "PL(30 MHz) < PL(900 MHz)")
        self.assertLess(pl_900, pl_4000, "PL(900 MHz) < PL(4000 MHz)")

    def test_output_shape_preserved(self):
        """Test: Shape de salida = shape entrada"""
        # 1D
        distances_1d = np.linspace(1000, 50000, 10)
        pl_1d = self.model.calculate_path_loss(
            distances=distances_1d,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=np.zeros_like(distances_1d)
        )
        self.assertEqual(pl_1d.shape, distances_1d.shape)

        # 2D
        distances_2d = np.random.uniform(1000, 50000, (10, 10))
        pl_2d = self.model.calculate_path_loss(
            distances=distances_2d,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=np.zeros_like(distances_2d)
        )
        self.assertEqual(pl_2d.shape, distances_2d.shape)


class TestITUR_P1546RadioHorizon(unittest.TestCase):
    """Tests: Radio horizon y determinación LOS/NLOS"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()

    def test_radio_horizon_calculation(self):
        """Test: Radio horizon calcula correctamente"""
        # Para tx_height=50m, rx_height=1.5m:
        # d_ho = 4.12 * sqrt(50 * 1.5) / 1000 ≈ 0.36 km
        d_ho = self.model._calculate_radio_horizon(tx_height=50.0, rx_height=1.5)

        self.assertGreater(d_ho, 0.0)
        self.assertLess(d_ho, 1.0)  # Debe ser < 1 km para alturas pequeñas
        self.assertAlmostEqual(d_ho, 0.358, places=2)  # Valor esperado

    def test_los_nlos_transition(self):
        """Test: Transición LOS/NLOS es suave"""
        # Distancias alrededor del radio horizon
        distances = np.array([100, 300, 360, 400, 600])  # metros
        terrain = np.zeros_like(distances)

        # Frecuencia baja (menos sensible a difracción)
        pl_30mhz = self.model.calculate_path_loss(
            distances=distances * 1000,  # Convertir a metros
            frequency=30.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Frecuencia alta (mas difracción en NLOS)
        pl_4000mhz = self.model.calculate_path_loss(
            distances=distances * 1000,
            frequency=4000.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Ambos deben ser continuos, sin saltos bruscos
        diffs_30 = np.diff(pl_30mhz)
        diffs_4000 = np.diff(pl_4000mhz)

        self.assertTrue(np.all(diffs_30 > 0), "30 MHz debe ser monotónico")
        self.assertTrue(np.all(diffs_4000 > 0), "4000 MHz debe ser monotónico")

    def test_radio_horizon_increases_with_height(self):
        """Test: Radio horizon aumenta con altura"""
        d_ho_50 = self.model._calculate_radio_horizon(tx_height=50.0, rx_height=1.5)
        d_ho_100 = self.model._calculate_radio_horizon(tx_height=100.0, rx_height=1.5)
        d_ho_200 = self.model._calculate_radio_horizon(tx_height=200.0, rx_height=1.5)

        self.assertLess(d_ho_50, d_ho_100, "Mayor altura → mayor radio horizon")
        self.assertLess(d_ho_100, d_ho_200)


class TestITUR_P1546EnvironmentCorrections(unittest.TestCase):
    """Tests: Correcciones por ambiente y terreno"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([1000.0, 5000.0, 10000.0])
        self.terrain = np.array([2500.0, 2500.0, 2500.0])

    def test_urban_vs_suburban(self):
        """Test: Urban atenuación > Suburban"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )

        pl_suburban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Suburban'
        )

        # Urban tiene mas atenuacion (valores mas altos)
        self.assertTrue(np.all(pl_urban > pl_suburban),
                       "Urban debe tener mayor atenuacion que Suburban")

    def test_urban_vs_rural(self):
        """Test: Urban > Suburban > Rural"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )

        pl_rural = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Rural'
        )

        self.assertTrue(np.all(pl_urban > pl_rural),
                       "Urban > Rural (atenuacion)")

    def test_smooth_vs_irregular_terrain(self):
        """Test: Terreno suave < terreno irregular"""
        pl_smooth = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            terrain_type='smooth'
        )

        pl_irregular = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            terrain_type='irregular'
        )

        self.assertTrue(np.all(pl_smooth < pl_irregular),
                       "Smooth < Irregular (atenuacion)")


class TestITUR_P1546FrequencyRange(unittest.TestCase):
    """Tests: Rango de frecuencias (30-4000 MHz)"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([10000.0])  # 10 km
        self.terrain = np.array([2500.0])

    def test_frequency_30mhz_minimum(self):
        """Test: Frecuencia 30 MHz (mínimo)"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=30.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_frequency_4000mhz_maximum(self):
        """Test: Frecuencia 4000 MHz (máximo)"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=4000.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_frequency_range_linear_increase(self):
        """Test: Path loss aumenta monotónicamente 30-4000 MHz"""
        frequencies = np.array([30, 100, 300, 900, 1800, 4000])
        path_losses = []

        for f in frequencies:
            pl = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=float(f),
                tx_height=50.0,
                terrain_heights=self.terrain
            )
            path_losses.append(pl[0])

        diffs = np.diff(path_losses)
        self.assertTrue(np.all(diffs > 0),
                       "Path loss debe aumentar con frecuencia")


class TestITUR_P1546DistanceRange(unittest.TestCase):
    """Tests: Rango de distancias (1-1000 km)"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.terrain_height = 2500.0

    def test_distance_1km_minimum(self):
        """Test: Distancia 1 km (mínimo)"""
        pl = self.model.calculate_path_loss(
            distances=np.array([1000.0]),  # 1 km en metros
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=np.array([self.terrain_height])
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_distance_1000km_maximum(self):
        """Test: Distancia 1000 km (máximo)"""
        pl = self.model.calculate_path_loss(
            distances=np.array([1000000.0]),  # 1000 km en metros
            frequency=900.0,
            tx_height=100.0,  # Altura más realista para largas distancias
            terrain_heights=np.array([self.terrain_height])
        )

        self.assertTrue(np.all(pl > 100))  # Atenuacion significativa
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_logarithmic_distance_behavior(self):
        """Test: Comportamiento logaritmico con distancia"""
        distances = np.array([1.0, 10.0, 100.0, 1000.0]) * 1000  # 1,10,100,1000 km
        terrains = np.full(len(distances), 2500.0)

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrains
        )

        # Cada 10x distancia debe aumentar ~20dB (log behavior)
        diff_1_10km = pl[1] - pl[0]  # 10km vs 1km
        diff_10_100km = pl[2] - pl[1]  # 100km vs 10km
        diff_100_1000km = pl[3] - pl[2]  # 1000km vs 100km

        # Todos deben ser aprox 20dB (±3dB tolerancia por correcciones)
        self.assertGreater(diff_1_10km, 15)
        self.assertLess(diff_1_10km, 25)
        self.assertGreater(diff_10_100km, 15)
        self.assertLess(diff_10_100km, 25)
        self.assertGreater(diff_100_1000km, 15)
        self.assertLess(diff_100_1000km, 25)


class TestITUR_P1546HeightCorrection(unittest.TestCase):
    """Tests: Correcciones por altura"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([10000.0])  # 10 km
        self.terrain = np.array([2500.0])

    def test_tx_height_valid_range(self):
        """Test: Altura TX válida (10-3000m)"""
        # Mínimo
        pl_10m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=10.0,
            terrain_heights=self.terrain
        )

        # Máximo
        pl_3000m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=3000.0,
            terrain_heights=self.terrain
        )

        # Mayor altura → menor atenuacion
        self.assertGreater(pl_10m[0], pl_3000m[0],
                          "Mayor altura TX → menor path loss")

    def test_rx_height_valid_range(self):
        """Test: Altura RX válida (1-20m)"""
        # Mínimo
        pl_1m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            mobile_height=1.0
        )

        # Máximo
        pl_20m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            mobile_height=20.0
        )

        # Mayor altura RX → menor atenuacion
        self.assertGreater(pl_1m[0], pl_20m[0],
                          "Mayor altura RX → menor path loss")


class TestITUR_P1546TerrainHandling(unittest.TestCase):
    """Tests: Manejo de datos de terreno"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([5000.0, 10000.0, 20000.0])

    def test_flat_terrain(self):
        """Test: Terreno plano (elevacion constante)"""
        terrain_flat = np.full(len(self.distances), 2500.0)

        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_flat
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_variable_terrain(self):
        """Test: Terreno variable"""
        terrain_variable = np.array([2400.0, 2500.0, 2600.0])

        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_variable
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_2d_terrain_grid(self):
        """Test: Grid 2D de terreno"""
        distances_2d = np.random.uniform(5000, 50000, (10, 10))
        terrain_2d = np.random.uniform(2400, 2600, (10, 10))

        pl_2d = self.model.calculate_path_loss(
            distances=distances_2d,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_2d
        )

        self.assertEqual(pl_2d.shape, distances_2d.shape)
        self.assertTrue(np.all(np.isfinite(pl_2d)))


@unittest.skipIf(not HAS_CUPY, "CuPy not available")
class TestITUR_P1546GPUConsistency(unittest.TestCase):
    """Tests: Consistencia NumPy vs CuPy"""

    def setUp(self):
        """Setup"""
        self.model_cpu = ITUR_P1546Model(compute_module=np)
        self.model_gpu = ITUR_P1546Model(compute_module=cp)
        self.distances = np.array([1000.0, 5000.0, 10000.0, 50000.0])
        self.terrain = np.array([2500.0, 2500.0, 2500.0, 2500.0])

    def test_cpu_gpu_consistency_basic(self):
        """Test: NumPy vs CuPy producen resultados idénticos"""
        pl_cpu = self.model_cpu.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        pl_gpu = self.model_gpu.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        # Convertir GPU a numpy para comparacion
        if hasattr(pl_gpu, 'get'):
            pl_gpu = pl_gpu.get()

        np.testing.assert_array_almost_equal(pl_cpu, pl_gpu, decimal=5)

    def test_cpu_gpu_consistency_all_frequencies(self):
        """Test: Consistencia en todo rango de frecuencias"""
        for freq in [30, 300, 900, 1800, 4000]:
            pl_cpu = self.model_cpu.calculate_path_loss(
                distances=self.distances,
                frequency=float(freq),
                tx_height=50.0,
                terrain_heights=self.terrain
            )

            pl_gpu = self.model_gpu.calculate_path_loss(
                distances=self.distances,
                frequency=float(freq),
                tx_height=50.0,
                terrain_heights=self.terrain
            )

            if hasattr(pl_gpu, 'get'):
                pl_gpu = pl_gpu.get()

            np.testing.assert_array_almost_equal(pl_cpu, pl_gpu, decimal=5,
                                              err_msg=f"Mismatch at {freq} MHz")


class TestITUR_P1546EdgeCases(unittest.TestCase):
    """Tests: Edge cases y parámetros extremos"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()

    def test_extreme_parameters_no_crash(self):
        """Test: Parámetros extremos no causan crash"""
        try:
            pl = self.model.calculate_path_loss(
                distances=np.array([1000, 1000000]),  # 1km, 1000km
                frequency=30.0,   # Mínimo
                tx_height=10.0,   # Mínimo
                terrain_heights=np.array([0, 5000])
            )
            self.assertTrue(np.all(np.isfinite(pl)))
        except Exception as e:
            self.fail(f"Modelo no debe fallar con parámetros extremos: {e}")

    def test_large_grid(self):
        """Test: Grid grande (10,000+ puntos)"""
        distances_large = np.random.uniform(1000, 100000, (100, 100))
        terrain_large = np.random.uniform(2400, 2600, (100, 100))

        pl_large = self.model.calculate_path_loss(
            distances=distances_large,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_large
        )

        self.assertEqual(pl_large.shape, distances_large.shape)
        self.assertTrue(np.all(np.isfinite(pl_large)))

    def test_single_point_calculation(self):
        """Test: Cálculo para punto único"""
        pl_single = self.model.calculate_path_loss(
            distances=np.array([5000]),
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=np.array([2500])
        )

        self.assertEqual(len(pl_single), 1)
        self.assertTrue(np.isfinite(pl_single[0]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
