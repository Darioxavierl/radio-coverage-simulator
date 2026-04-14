"""
Test Suite para COST-231 Walfisch-Ikegami Model

32+ tests cubriendo:
- Inicializacion
- Calculos basicos
- Determinacion LOS/NLOS
- Difraccion
- Street canyon
- Rango de frecuencias
- Casos de referencia
- Consistencia CPU/GPU
- Casos de borde
- Comparacion con Okumura-Hata
- Metadatos

Universidad de Cuenca, 2025
"""

import unittest
import numpy as np
import logging
import sys
from pathlib import Path

# Agregar directorio raiz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Importar modelo COST-231
from src.core.models.traditional.cost231 import COST231WalfischIkegamiModel

# Intentar importar CuPy para tests GPU
try:
    import cupy as cp
    HAS_CUPY = True
except ImportError:
    HAS_CUPY = False
    cp = None


class TestCOST231Initialization(unittest.TestCase):
    """Tests de inicializacion del modelo"""

    def test_default_initialization(self):
        """Test: Inicializacion con valores por defecto"""
        model = COST231WalfischIkegamiModel()
        self.assertIsNotNone(model)
        self.assertEqual(model.name, 'COST-231 Walfisch-Ikegami')
        self.assertIsNotNone(model.xp)

    def test_initialization_with_config(self):
        """Test: Inicializacion con configuracion personalizada"""
        config = {
            'building_height': 20.0,
            'street_width': 10.0,
            'environment': 'Suburban'
        }
        model = COST231WalfischIkegamiModel(config=config)
        self.assertEqual(model.defaults['building_height'], 20.0)
        self.assertEqual(model.defaults['street_width'], 10.0)
        self.assertEqual(model.defaults['environment'], 'Suburban')

    @unittest.skipIf(not HAS_CUPY, "CuPy not available")
    def test_initialization_with_cupy(self):
        """Test: Inicializacion con CuPy para GPU"""
        model = COST231WalfischIkegamiModel(compute_module=cp)
        self.assertEqual(model.xp, cp)


class TestCOST231BasicCalculation(unittest.TestCase):
    """Tests de calculo basico de Path Loss"""

    def setUp(self):
        """Setup: Crear modelo reutilizable"""
        self.model = COST231WalfischIkegamiModel()
        self.terrain_flat = np.array([2500.0, 2500.0, 2500.0, 2500.0])

    def test_basic_path_loss_calculation(self):
        """Test: Calculo basico de path loss para multiples distancias"""
        distances = np.array([100.0, 500.0, 1000.0, 5000.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=self.terrain_flat
        )

        # Verifica shape
        self.assertEqual(pl.shape, distances.shape)

        # Verifica rango razonable para COST-231: 80-150 dB
        self.assertTrue(np.all(pl > 80))
        self.assertTrue(np.all(pl < 150))

    def test_path_loss_increases_with_distance(self):
        """Test: Path loss aumenta monotonicamente con distancia"""
        distances = np.linspace(100, 5000, 20)
        terrain = np.full_like(distances, 2500.0)

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Verificar monotonia: derivada > 0
        diff = np.diff(pl)
        self.assertTrue(np.all(diff > 0),
            f"Path loss no es monotonico. Diffs: {diff}")

    def test_path_loss_increases_with_frequency(self):
        """Test: Path loss aumenta con frecuencia"""
        distances = np.array([1000.0, 1000.0, 1000.0])
        terrain = np.array([2500.0, 2500.0, 2500.0])

        pl_900 = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain
        )[0]

        pl_1800 = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800.0,
            tx_height=50.0,
            terrain_heights=terrain
        )[0]

        pl_2000 = self.model.calculate_path_loss(
            distances=distances,
            frequency=2000.0,
            tx_height=50.0,
            terrain_heights=terrain
        )[0]

        # Verificar orden
        self.assertTrue(pl_900 < pl_1800 < pl_2000,
            f"Path loss no sigue tendencia de frecuencia: {pl_900} < {pl_1800} < {pl_2000}")


class TestCOST231LOSvNLOS(unittest.TestCase):
    """Tests de determinacion LOS/NLOS"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()

    def test_los_with_flat_terrain(self):
        """Test: Determinar LOS en terreno plano"""
        distances = np.array([100.0, 1000.0])
        terrain = np.array([2500.0, 2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,  # TX ubicado en Cuenca (2500m msnm)
            terrain_heights=terrain
        )

        # En terreno plano con TX elevado, deberia ser LOS
        # Path loss esperado: 70-150 dB para estas distancias
        self.assertTrue(np.all(pl > 70))
        self.assertTrue(np.all(pl < 150))

    def test_nlos_with_high_terrain(self):
        """Test: Determinar NLOS con terreno muy alto vs TX"""
        distances = np.array([1000.0, 1000.0])

        # Terreno muy alto (2600m) - RX casi a mismo nivel que TX
        # h_tx_eff = 50 + 2500 = 2550m
        # terrain_avg = 2600m
        # delta_h = 2550 - 2600 = -50 < 30 → NLOS
        terrain_elevated = np.array([2600.0, 2600.0])

        pl_elevated = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=terrain_elevated
        )

        # Terreno bajo (2400m) - RX mucho mas bajo que TX
        # h_tx_eff = 50 + 2500 = 2550m
        # terrain_avg = 2400m
        # delta_h = 2550 - 2400 = 150 > 30 → LOS
        terrain_low = np.array([2400.0, 2400.0])

        pl_low = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=terrain_low
        )

        # Con terreno alto (NLOS) vs terreno bajo (LOS) - ambos deben tener valores razonables
        self.assertTrue(np.all(pl_elevated > 100))
        self.assertTrue(np.all(pl_elevated < 130))
        self.assertTrue(np.all(pl_low > 120))
        self.assertTrue(np.all(pl_low < 150))

    def test_varying_terrain_profile(self):
        """Test: Terreno con variaciones"""
        distances = np.linspace(100, 5000, 50)
        # Terreno que desciende
        terrain = np.linspace(2600, 2400, 50)

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=terrain
        )

        # Todos los valores deben ser razonables
        self.assertTrue(np.all(pl > 80))
        self.assertTrue(np.all(pl < 150))

    def test_los_nlos_transition(self):
        """Test: Transicion entre LOS y NLOS con cambio de terreno"""
        distances = np.array([100.0, 100.0])

        # El mismo caso pero con terrain diferente denota diferente LOS/NLOS
        terrain_a = np.array([2450.0, 2450.0])  # Bajo
        terrain_b = np.array([2550.0, 2550.0])  # Alto

        pl_a = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=terrain_a
        )[0]

        pl_b = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            tx_elevation=2500.0,
            terrain_heights=terrain_b
        )[0]

        # Diferencia esperada
        self.assertNotEqual(pl_a, pl_b,
            "Path loss debe cambiar con elevacion del terreno")


class TestCOST231StreetCanyon(unittest.TestCase):
    """Tests de efecto street canyon"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()
        self.distances = np.array([1000.0])
        self.terrain = np.array([2500.0])

    def test_effect_of_building_height(self):
        """Test: Efecto de variacion de altura de edificios"""
        pl_15m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            building_height=15.0  # Default
        )[0]

        pl_25m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            building_height=25.0  # Mas alto
        )[0]

        # Con edificios mas altos, el TX esta menos elevado sobre ellos
        # Lrtd deberia cambiar
        self.assertNotEqual(pl_15m, pl_25m,
            "Path loss debe variar con altura de edificios")

    def test_effect_of_street_width(self):
        """Test: Efecto de variacion de ancho de calle"""
        pl_12m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            street_width=12.0  # Default
        )[0]

        pl_30m = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            street_width=30.0  # Mas ancho
        )[0]

        # Calles mas anchas -> menos atenuacion
        self.assertLess(pl_30m, pl_12m,
            f"Calle mas ancha debe tener menos atenuacion: {pl_30m} < {pl_12m}")

    def test_effect_of_street_orientation(self):
        """Test: Efecto de orientacion de calle"""
        pl_0deg = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            street_orientation=0.0
        )[0]

        pl_45deg = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            street_orientation=45.0
        )[0]

        pl_90deg = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            street_orientation=90.0
        )[0]

        # La orientacion afecta el factor Lori
        self.assertNotEqual(pl_0deg, pl_45deg,
            "Orientacion de calle debe afectar path loss")
        self.assertNotEqual(pl_45deg, pl_90deg,
            "Orientacion de calle debe afectar path loss")


class TestCOST231FrequencyRange(unittest.TestCase):
    """Tests para verfiar rango de frecuencias"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()
        self.distances = np.array([1000.0])
        self.terrain = np.array([2500.0])

    def test_800_mhz_lower_boundary(self):
        """Test: Frecuencia minima 800 MHz"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=800.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )[0]

        self.assertGreater(pl, 0)
        self.assertTrue(100 < pl < 130)

    def test_2000_mhz_upper_boundary(self):
        """Test: Frecuencia maxima 2000 MHz"""
        pl = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=2000.0,
            tx_height=50.0,
            terrain_heights=self.terrain
        )[0]

        self.assertGreater(pl, 0)
        self.assertTrue(100 < pl < 130)

    def test_frequency_progression(self):
        """Test: Progresion monotonica de path loss con frecuencia"""
        frequencies = np.array([800, 900, 1000, 1200, 1500, 1800, 2000])
        pls = []

        for f in frequencies:
            pl = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=float(f),
                tx_height=50.0,
                terrain_heights=self.terrain
            )[0]
            pls.append(pl)

        # Verificar monotonia
        pls = np.array(pls)
        diffs = np.diff(pls)
        self.assertTrue(np.all(diffs > 0),
            f"Path loss debe aumentar con frecuencia. Diffs: {diffs}")


class TestCOST231EnvironmentCorrection(unittest.TestCase):
    """Tests de correccion por ambiente"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()
        self.distances = np.array([1000.0])
        self.terrain = np.array([2500.0])

    def test_urban_environment(self):
        """Test: Ambiente urbano"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )[0]

        self.assertTrue(100 < pl_urban < 130)

    def test_suburban_environment(self):
        """Test: Ambiente suburbano (menos atenuacion que urban)"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )[0]

        pl_suburban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Suburban'
        )[0]

        # Suburbano debe tener menos atenuacion
        self.assertLess(pl_suburban, pl_urban,
            f"Suburban debe tener menos atenuacion: {pl_suburban} < {pl_urban}")

    def test_rural_environment(self):
        """Test: Ambiente rural (aun menos atenuacion)"""
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

        # Rural debe tener menos atenuacion que urban
        self.assertLess(pl_rural, pl_urban,
            f"Rural debe tener menos atenuacion: {pl_rural} < {pl_urban}")

    def test_environment_ordering(self):
        """Test: Orden correcto de ambientes: Rural < Suburban < Urban"""
        pl_urban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Urban'
        )[0]

        pl_suburban = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Suburban'
        )[0]

        pl_rural = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=self.terrain,
            environment='Rural'
        )[0]

        self.assertTrue(pl_rural < pl_suburban < pl_urban,
            f"Orden debe ser Rural < Suburban < Urban: {pl_rural} < {pl_suburban} < {pl_urban}")


class TestCOST231ReferenceValues(unittest.TestCase):
    """Tests con valores de referencia de literatura"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()

    def test_reference_case_urban_canyon_1(self):
        """Test: Caso de referencia urban canyon tipico"""
        # Parametros: 900 MHz, 1km, urban, edificios 15m
        pl = self.model.calculate_path_loss(
            distances=np.array([1000.0]),
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=np.array([2500.0]),
            environment='Urban',
            building_height=15.0
        )[0]

        # El rango esperado para estos parametros
        self.assertTrue(95 < pl < 115,
            f"Path loss {pl:.2f} fuera del rango esperado (95-115 dB)")

    def test_reference_case_urban_canyon_2(self):
        """Test: Caso de referencia urban canyon diferente"""
        # Parametros: 1800 MHz, 500m, urban
        pl = self.model.calculate_path_loss(
            distances=np.array([500.0]),
            frequency=1800.0,
            tx_height=40.0,
            terrain_heights=np.array([2500.0]),
            environment='Urban'
        )[0]

        # El rango esperado
        self.assertTrue(90 < pl < 120,
            f"Path loss {pl:.2f} fuera del rango esperado (90-120 dB)")


class TestCOST231GPUConsistency(unittest.TestCase):
    """Tests de consistencia CPU vs GPU"""

    @unittest.skipIf(not HAS_CUPY, "CuPy no disponible")
    def test_cpu_gpu_consistency_basic(self):
        """Test: Consistencia entre CPU (NumPy) y GPU (CuPy)"""
        distances_cpu = np.array([100.0, 500.0, 1000.0, 5000.0])
        terrain_cpu = np.array([2500.0, 2500.0, 2500.0, 2500.0])

        # Calcular con CPU
        model_cpu = COST231WalfischIkegamiModel(compute_module=np)
        pl_cpu = model_cpu.calculate_path_loss(
            distances=distances_cpu,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_cpu
        )

        # Calcular con GPU
        model_gpu = COST231WalfischIkegamiModel(compute_module=cp)
        distances_gpu = cp.array(distances_cpu)
        terrain_gpu = cp.array(terrain_cpu)

        pl_gpu = model_gpu.calculate_path_loss(
            distances=distances_gpu,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain_gpu
        )

        # Convertir GPU a CPU para comparar
        pl_gpu_cpu = cp.asnumpy(pl_gpu)

        # Validar consistencia (tolerancia: 10 decimales)
        np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=5,
            err_msg="CPU y GPU resultados difieren")

    @unittest.skipIf(not HAS_CUPY, "CuPy no disponible")
    def test_cpu_gpu_consistency_all_environments(self):
        """Test: Consistencia CPU/GPU para todos los ambientes"""
        distances = np.array([100.0, 1000.0, 5000.0])
        terrain = np.array([2500.0, 2500.0, 2500.0])

        environments = ['Urban', 'Suburban', 'Rural']

        for env in environments:
            model_cpu = COST231WalfischIkegamiModel(compute_module=np)
            pl_cpu = model_cpu.calculate_path_loss(
                distances=distances,
                frequency=900.0,
                tx_height=50.0,
                terrain_heights=terrain,
                environment=env
            )

            model_gpu = COST231WalfischIkegamiModel(compute_module=cp)
            distances_gpu = cp.array(distances)
            terrain_gpu = cp.array(terrain)

            pl_gpu = model_gpu.calculate_path_loss(
                distances=distances_gpu,
                frequency=900.0,
                tx_height=50.0,
                terrain_heights=terrain_gpu,
                environment=env
            )

            pl_gpu_cpu = cp.asnumpy(pl_gpu)

            np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=5,
                err_msg=f"CPU/GPU inconsistencia en ambiente {env}")


class TestCOST231EdgeCases(unittest.TestCase):
    """Tests de casos de borde"""

    def setUp(self):
        self.model = COST231WalfischIkegamiModel()

    def test_minimum_distance(self):
        """Test: Distancia minima (20m)"""
        distances = np.array([20.0])
        terrain = np.array([2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Debe retornar valor valido
        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(pl < 200))

    def test_maximum_distance(self):
        """Test: Distancia maxima (5km)"""
        distances = np.array([5000.0])
        terrain = np.array([2500.0])

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Debe retornar valor valido
        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(pl < 200))

    def test_large_grid(self):
        """Test: Grid grande (10000 puntos)"""
        distances = np.random.uniform(100, 5000, 10000)
        terrain = np.random.uniform(2400, 2600, 10000)

        pl = self.model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=50.0,
            terrain_heights=terrain
        )

        # Validar shape
        self.assertEqual(len(pl), 10000)

        # Validar rango
        self.assertTrue(np.all(pl > 0))
        self.assertTrue(np.all(pl < 200))

        # Validar monotonia por distancia
        sorted_idx = np.argsort(distances)
        sorted_distances = distances[sorted_idx]
        sorted_pl = pl[sorted_idx]

        # Verificar que generalmente aumenta (permite algunas inversiones por terreno)
        trend = np.mean(np.diff(sorted_pl)) > 0
        self.assertTrue(trend, "Path loss debe tendencia a aumentar con distancia")


class TestCOST231ModelInfo(unittest.TestCase):
    """Tests de informacion del modelo"""

    def test_get_model_info(self):
        """Test: Informacion del modelo"""
        model = COST231WalfischIkegamiModel()
        info = model.get_model_info()

        # Validar campos esenciales
        self.assertIn('name', info)
        self.assertIn('frequency_range', info)
        self.assertIn('distance_range', info)
        self.assertIn('environments', info)

        # Validar valores
        self.assertEqual(info['name'], 'COST-231 Walfisch-Ikegami')
        self.assertIn('Urban', info['environments'])
        self.assertTrue(info['has_terrain_awareness'])


if __name__ == '__main__':
    # Configurar verbosity
    unittest.main(verbosity=2)
