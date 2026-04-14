"""
Test Suite para Integración de COST-231 en Sistema Principal

Tests de modelo integración:
- COST-231 Model instantiation
- Parámetros pasan correctamente
- No rompe otros modelos
- Cálculos producen resultados razonables

Universidad de Cuenca, 2025
"""

import unittest
import sys
from pathlib import Path

# Agregar directorio raiz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from src.core.models.traditional.cost231 import COST231WalfischIkegamiModel
from src.core.models.traditional.okumura_hata import OkumuraHataModel
from src.core.models.traditional.free_space import FreeSpacePathLossModel


class TestCOST231ModelInstantiation(unittest.TestCase):
    """Tests: Instanciación del modelo COST-231"""

    def test_instantiate_with_defaults(self):
        """Test: COST-231 se instancia con valores por defecto"""
        model = COST231WalfischIkegamiModel()

        self.assertIsNotNone(model)
        self.assertEqual(model.defaults['building_height'], 15.0)
        self.assertEqual(model.defaults['street_width'], 12.0)
        self.assertEqual(model.defaults['street_orientation'], 0.0)

    def test_instantiate_with_custom_config(self):
        """Test: COST-231 se instancia con config personalizada"""
        config = {
            'building_height': 20.0,
            'street_width': 15.0,
            'street_orientation': 45.0
        }
        model = COST231WalfischIkegamiModel(config=config)

        self.assertEqual(model.defaults['building_height'], 20.0)
        self.assertEqual(model.defaults['street_width'], 15.0)
        self.assertEqual(model.defaults['street_orientation'], 45.0)

    def test_instantiate_with_numpy_module(self):
        """Test: COST-231 se instancia con NumPy"""
        model = COST231WalfischIkegamiModel(compute_module=np)

        self.assertEqual(model.xp, np)

    def test_model_name_is_correct(self):
        """Test: Nombre del modelo es correcto"""
        model = COST231WalfischIkegamiModel()

        self.assertEqual(model.name, 'COST-231 Walfisch-Ikegami')


class TestCOST231ParameterPassing(unittest.TestCase):
    """Tests: Parámetros se pasan correctamente a método calculate_path_loss"""

    def setUp(self):
        """Setup"""
        self.distances = np.array([1000.0])
        self.terrain = np.array([2500.0])

    def test_building_height_parameter_accepted(self):
        """Test: Parámetro building_height se acepta en método"""
        model = COST231WalfischIkegamiModel()

        # No debe lanzar excepción
        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            building_height=20.0
        )

        self.assertTrue(np.all(pl > 0))

    def test_street_width_parameter_accepted(self):
        """Test: Parámetro street_width se acepta en método"""
        model = COST231WalfischIkegamiModel()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            street_width=15.0
        )

        self.assertTrue(np.all(pl > 0))

    def test_street_orientation_parameter_accepted(self):
        """Test: Parámetro street_orientation se acepta en método"""
        model = COST231WalfischIkegamiModel()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            street_orientation=45.0
        )

        self.assertTrue(np.all(pl > 0))

    def test_tx_elevation_parameter_accepted(self):
        """Test: Parámetro tx_elevation se acepta en método"""
        model = COST231WalfischIkegamiModel()

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
        model = COST231WalfischIkegamiModel()

        pl = model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            tx_elevation=2500.0,
            environment='Urban',
            mobile_height=1.5,
            building_height=15.0,
            street_width=12.0,
            street_orientation=0.0
        )

        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(pl < 200))


class TestCOST231OutputReasonable(unittest.TestCase):
    """Tests: Salidas de COST-231 son razonables"""

    def setUp(self):
        """Setup"""
        self.model = COST231WalfischIkegamiModel()
        self.antenna_params = {
            'frequency': 900.0,
            'tx_height': 50.0,
            'tx_elevation': 2530.0,
            'building_height': 15.0,
            'street_width': 12.0,
            'street_orientation': 0.0
        }

    def test_path_loss_positive(self):
        """Test: Path loss es positivo"""
        distances = np.array([100.0, 1000.0, 5000.0])
        terrain = np.array([2500.0, 2500.0, 2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            **self.antenna_params
        )

        self.assertTrue(np.all(pl > 0), "Path loss debe ser positivo")

    def test_path_loss_in_reasonable_range(self):
        """Test: Path loss en rango razonable (80-150 dB)"""
        distances = np.array([1000.0])
        terrain = np.array([2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            **self.antenna_params
        )

        self.assertTrue(np.all(pl > 80), f"Path loss {pl} debe ser > 80 dB")
        self.assertTrue(np.all(pl < 150), f"Path loss {pl} debe ser < 150 dB")

    def test_path_loss_increases_with_distance(self):
        """Test: Path loss aumenta con distancia"""
        distances = np.array([100.0, 500.0, 1000.0, 5000.0])
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
        distances = np.array([1000.0])
        terrain = np.array([2500.0])

        pl_900 = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2530.0,
            building_height=15.0,
            street_width=12.0
        )[0]

        pl_1800 = self.model.calculate_path_loss(
            distances=distances,
            terrain_heights=terrain,
            frequency=1800.0,
            tx_height=50.0,
            tx_elevation=2530.0,
            building_height=15.0,
            street_width=12.0
        )[0]

        self.assertLess(pl_900, pl_1800, "PL debe aumentar con frecuencia")


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

    def test_all_models_produce_different_results(self):
        """Test: Diferentes modelos producen resultados diferentes"""
        free_space = FreeSpacePathLossModel()
        okumura = OkumuraHataModel()
        cost231 = COST231WalfischIkegamiModel()

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

        params['building_height'] = 15.0
        params['street_width'] = 12.0

        pl_c231 = cost231.calculate_path_loss(**params)[0]

        # Todos deben ser diferentes
        self.assertNotAlmostEqual(pl_fs, pl_oh, places=1)
        self.assertNotAlmostEqual(pl_oh, pl_c231, places=1)
        self.assertNotAlmostEqual(pl_fs, pl_c231, places=1)


class TestCOST231Configuration(unittest.TestCase):
    """Tests: Configuración de COST-231 funciona correctamente"""

    def test_get_model_info(self):
        """Test: get_model_info() retorna información correcta"""
        model = COST231WalfischIkegamiModel()
        info = model.get_model_info()

        self.assertIn('name', info)
        self.assertIn('frequency_range', info)
        self.assertIn('distance_range', info)
        self.assertIn('environments', info)
        self.assertTrue(info['has_terrain_awareness'])

    def test_model_handles_extreme_parameters(self):
        """Test: Modelo maneja parámetros extremos sin crashing"""
        model = COST231WalfischIkegamiModel()

        # Parámetros extremos
        distances = np.array([20.0, 5000.0])  # Min y max del rango
        terrain = np.array([2000.0, 3000.0])

        try:
            pl = model.calculate_path_loss(
                distances=distances,
                frequency=800.0,  # Min frecuencia
                tx_height=30.0,  # Min altura
                terrain_heights=terrain,
                tx_elevation=2000.0,
                building_height=5.0,  # Min building
                street_width=5.0  # Min street
            )

            self.assertIsNotNone(pl)
            self.assertEqual(len(pl), 2)
        except Exception as e:
            self.fail(f"Modelo no debe fallar con parámetros extremos: {e}")

    def test_model_handles_array_inputs(self):
        """Test: Modelo maneja arrays de entrada correctamente"""
        model = COST231WalfischIkegamiModel()

        # Array 2D para grid
        distances = np.random.uniform(100, 5000, (10, 10))
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
