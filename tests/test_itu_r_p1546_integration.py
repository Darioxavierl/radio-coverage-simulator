"""
Test Suite para Integración de ITU-R P.1546 en Sistema Principal

Tests de integración:
- GUI + Model Selection
- Worker + Model Instantiation
- Coverage Calculation
- Sistema completo sin romper otros modelos

Universidad de Cuenca, 2025
"""

import unittest
import sys
import numpy as np
from pathlib import Path

# Agregar directorio raiz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models.traditional.itu_r_p1546 import ITUR_P1546Model
from src.core.models.traditional.okumura_hata import OkumuraHataModel
from src.core.models.traditional.free_space import FreeSpacePathLossModel


class TestITUR_P1546ModelInstantiation(unittest.TestCase):
    """Tests: Instanciación del modelo ITU-R P.1546"""

    def test_instantiate_with_defaults(self):
        """Test: ITU-R P.1546 se instancia con valores por defecto"""
        model = ITUR_P1546Model()

        self.assertIsNotNone(model)
        self.assertEqual(model.defaults['environment'], 'Urban')
        self.assertEqual(model.defaults['terrain_type'], 'mixed')

    def test_instantiate_with_custom_config(self):
        """Test: ITU-R P.1546 se instancia con config personalizada"""
        config = {
            'environment': 'Rural',
            'terrain_type': 'irregular'
        }
        model = ITUR_P1546Model(config=config)

        self.assertEqual(model.defaults['environment'], 'Rural')
        self.assertEqual(model.defaults['terrain_type'], 'irregular')

    def test_instantiate_with_numpy_module(self):
        """Test: ITU-R P.1546 se instancia con NumPy"""
        model = ITUR_P1546Model(compute_module=np)
        self.assertEqual(model.xp, np)

    def test_model_name_is_correct(self):
        """Test: Nombre del modelo es correcto"""
        model = ITUR_P1546Model()
        self.assertEqual(model.name, "ITU-R P.1546")


class TestITUR_P1546ParameterPassing(unittest.TestCase):
    """Tests: Parámetros se pasan correctamente a método calculate_path_loss"""

    def setUp(self):
        """Setup"""
        self.distances = np.array([1000.0])
        self.terrain = np.array([2500.0])

    def test_environment_parameter_accepted(self):
        """Test: Parámetro environment se acepta en método"""
        model = ITUR_P1546Model()

        # No debe lanzar excepción
        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )

        self.assertTrue(np.all(pl > 0))

    def test_terrain_type_parameter_accepted(self):
        """Test: Parámetro terrain_type se acepta en método"""
        model = ITUR_P1546Model()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            terrain_type='smooth'
        )

        self.assertTrue(np.all(pl > 0))

    def test_tx_elevation_parameter_accepted(self):
        """Test: Parámetro tx_elevation se acepta en método"""
        model = ITUR_P1546Model()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0
        )

        self.assertTrue(np.all(pl > 0))

    def test_all_parameters_together(self):
        """Test: Todos los parámetros juntos funcionan"""
        model = ITUR_P1546Model()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            environment='Urban',
            terrain_type='mixed',
            mobile_height=1.5
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(pl < 200))


class TestITUR_P1546OutputReasonable(unittest.TestCase):
    """Tests: Salidas de ITU-R P.1546 son razonables"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.antenna_params = {
            'frequency': 900.0,
            'tx_height': 50.0,
            'tx_elevation': 2530.0
        }

    def test_path_loss_positive(self):
        """Test: Path loss es positivo"""
        distances = np.array([1000.0, 10000.0, 50000.0])
        terrain = np.array([2500.0, 2500.0, 2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            **self.antenna_params
        )

        self.assertTrue(np.all(pl > 0), "Path loss debe ser positivo")

    def test_path_loss_in_reasonable_range(self):
        """Test: Path loss en rango razonable (90-160 dB)"""
        distances = np.array([10000.0])
        terrain = np.array([2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            **self.antenna_params
        )

        self.assertTrue(np.all(pl > 90), f"Path loss {pl} debe ser > 90 dB")
        self.assertTrue(np.all(pl < 160), f"Path loss {pl} debe ser < 160 dB")

    def test_path_loss_increases_with_distance(self):
        """Test: Path loss aumenta con distancia"""
        distances = np.array([1000.0, 5000.0, 10000.0, 50000.0])
        terrain = np.array([2500.0, 2500.0, 2500.0, 2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            **self.antenna_params
        )

        diffs = np.diff(pl)
        self.assertTrue(np.all(diffs > 0), "Path loss debe aumentar con distancia")

    def test_path_loss_increases_with_frequency(self):
        """Test: Path loss aumenta con frecuencia"""
        distances = np.array([10000.0])
        terrain = np.array([2500.0])

        pl_30 = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            frequency=30.0,
            tx_height=50.0,
            tx_elevation=2530.0
        )[0]

        pl_900 = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2530.0
        )[0]

        pl_4000 = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            frequency=4000.0,
            tx_height=50.0,
            tx_elevation=2530.0
        )[0]

        self.assertLess(pl_30, pl_900, "PL(30 MHz) < PL(900 MHz)")
        self.assertLess(pl_900, pl_4000, "PL(900 MHz) < PL(4000 MHz)")


class TestModelsNotBroken(unittest.TestCase):
    """Tests: Los otros modelos siguen funcionando"""

    def setUp(self):
        """Setup"""
        self.distances = np.array([100.0, 1000.0, 5000.0])
        self.terrain = np.array([2500.0, 2500.0, 2500.0])

    def test_free_space_still_works(self):
        """Test: Free Space Model sigue funcionando"""
        model = FreeSpacePathLossModel()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )

        self.assertEqual(len(pl), len(self.distances))
        self.assertTrue(np.all(pl > 0))

    def test_okumura_hata_still_works(self):
        """Test: Okumura-Hata Model sigue funcionando"""
        model = OkumuraHataModel()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            environment='Urban',
            city_type='medium',
            mobile_height=1.5
        )

        self.assertEqual(len(pl), len(self.distances))
        self.assertTrue(np.all(pl > 0))

    def test_itu_p1546_works(self):
        """Test: ITU-R P.1546 funciona"""
        model = ITUR_P1546Model()

        pl = model.calculate_path_loss(
            distances=self.distances * 1000,  # Convertir a metros
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            environment='Urban',
            terrain_type='mixed'
        )

        self.assertEqual(len(pl), len(self.distances))
        self.assertTrue(np.all(pl > 0))

    def test_all_models_produce_different_results(self):
        """Test: Diferentes modelos producen resultados diferentes"""
        free_space = FreeSpacePathLossModel()
        okumura = OkumuraHataModel()
        itu = ITUR_P1546Model()

        params = {
            'distances': np.array([1000.0]),
            'frequency': 900.0,
            'tx_height': 50.0,
            'terrain_heights': np.array([2500.0])
        }

        pl_fs = free_space.calculate_path_loss(**params)[0]

        params['tx_elevation'] = 2500.0
        params['environment'] = 'Urban'
        params['city_type'] = 'medium'
        params['mobile_height'] = 1.5

        pl_oh = okumura.calculate_path_loss(**params)[0]

        params['terrain_type'] = 'mixed'
        params['distances'] = np.array([1000000.0])  # 1000 km para ITU

        pl_itu = itu.calculate_path_loss(**params)[0]

        # Todos deben ser diferentes
        self.assertNotAlmostEqual(pl_fs, pl_oh, places=1)
        self.assertNotAlmostEqual(pl_fs, pl_itu, places=1)


class TestITUR_P1546Configuration(unittest.TestCase):
    """Tests: Configuración de ITU-R P.1546 funciona correctamente"""

    def test_get_model_info(self):
        """Test: get_model_info() retorna información correcta"""
        model = ITUR_P1546Model()
        info = model.get_model_info()

        self.assertIn('name', info)
        self.assertIn('frequency_range', info)
        self.assertIn('distance_range', info)
        self.assertIn('environments', info)
        self.assertTrue(info['has_terrain_awareness'])
        self.assertTrue(info['has_los_nlos'])

    def test_model_handles_extreme_parameters(self):
        """Test: Modelo maneja parámetros extremos sin crashing"""
        model = ITUR_P1546Model()

        # Parámetros extremos
        distances = np.array([1000, 1000000000])  # 1km, 1000km
        terrain = np.array([0, 5000])

        try:
            pl = model.calculate_path_loss(
                distances=distances,
                frequency=30.0,  # Mínimo frecuencia
                tx_height=10.0,  # Mínimo altura
                terrain_heights=terrain,
                tx_elevation=0.0,
                environment='Rural',
                terrain_type='irregular'
            )

            self.assertIsNotNone(pl)
            self.assertEqual(len(pl), 2)
        except Exception as e:
            self.fail(f"Modelo no debe fallar con parámetros extremos: {e}")

    def test_model_handles_array_inputs(self):
        """Test: Modelo maneja arrays de entrada correctamente"""
        model = ITUR_P1546Model()

        # Array 2D para grid
        distances = np.random.uniform(1000, 100000, (10, 10))
        terrain = np.random.uniform(2400, 2600, (10, 10))

        pl = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain,
            tx_elevation=2530.0
        )

        # Output debe tener mismo shape que input
        self.assertEqual(pl.shape, distances.shape)
        self.assertTrue(np.all(pl > 0))


class TestITUR_P1546FrequencyRangeValidation(unittest.TestCase):
    """Tests: Rango de frecuencias (30-4000 MHz)"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([10000.0])
        self.terrain = np.array([2500.0])

    def test_frequency_30mhz(self):
        """Test: Frecuencia 30 MHz funciona"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=30.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_frequency_4000mhz(self):
        """Test: Frecuencia 4000 MHz funciona"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=4000.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )
        self.assertTrue(np.all(np.isfinite(pl)))

    def test_frequency_monotonic_increase(self):
        """Test: Path loss aumenta monotónicamente con frecuencia"""
        freqs = [30, 100, 300, 900, 1800, 4000]
        path_losses = []

        for freq in freqs:
            pl = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=float(freq),
                tx_height=50.0,
                terrain_heights=self.terrain
            )[0]
            path_losses.append(pl)

        diffs = np.diff(path_losses)
        self.assertTrue(np.all(diffs > 0), "Path loss debe crecer con frecuencia")


class TestITUR_P1546EnvironmentEffect(unittest.TestCase):
    """Tests: Efectos de ambiente y terreno"""

    def setUp(self):
        """Setup"""
        self.model = ITUR_P1546Model()
        self.distances = np.array([10000.0])
        self.terrain = np.array([2500.0])

    def test_urban_vs_rural_attenuation(self):
        """Test: Urban tiene más atenuación que Rural"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )[0]

        pl_rural = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Rural'
        )[0]

        self.assertGreater(pl_urban, pl_rural)

    def test_smooth_terrain_better_propagation(self):
        """Test: Terreno suave tiene mejor propagación"""
        pl_smooth = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            terrain_type='smooth'
        )[0]

        pl_irregular = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            terrain_type='irregular'
        )[0]

        self.assertLess(pl_smooth, pl_irregular)


if __name__ == '__main__':
    unittest.main(verbosity=2)
