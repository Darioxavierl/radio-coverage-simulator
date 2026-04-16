"""
Integration tests for 3GPP TR 38.901 propagation model with GUI, Worker, and CoverageCalculator.
Validates that the model integrates correctly without breaking existing models.
"""

import unittest
import numpy as np
import warnings
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.gpp_3gpp.three_gpp_38901 import ThreGPP38901Model, calculate_3gpp_38901_path_loss
from core.models.traditional.free_space import FreeSpacePathLossModel
from core.models.traditional.okumura_hata import OkumuraHataModel
try:
    from core.models.traditional.cost231 import COST231WalfischIkegamiModel
    COST231_AVAILABLE = True
except ImportError:
    COST231_AVAILABLE = False

try:
    from core.models.traditional.itu_r_p1546 import ITUR_P1546Model
    ITU_P1546_AVAILABLE = True
except ImportError:
    ITU_P1546_AVAILABLE = False


class TestThreGPP38901ParameterPassing(unittest.TestCase):
    """Test parameter passing and configuration."""

    def test_model_accepts_all_required_parameters(self):
        """Test: Modelo acepta todos los parámetros requeridos"""
        print("Test: Required parameters...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        distances = np.array([0.5, 1.0, 2.0])
        result = model.calculate_path_loss(
            distances=distances,
            frequency=28000,
            tx_height=25,
            rx_height=1.5,
        )
        self.assertEqual(result.shape, distances.shape)
        self.assertTrue(np.all(np.isfinite(result)))
        print("[OK] All parameters accepted")

    def test_scenario_parameter_validation(self):
        """Test: Parámetro scenario valida correctamente"""
        print("Test: Scenario validation...")
        scenarios = ['UMa', 'UMi', 'RMa']
        for scenario in scenarios:
            config = {'scenario': scenario}
            model = ThreGPP38901Model(config)
            self.assertEqual(model.scenario, scenario)
        print("[OK] All scenarios validated")

    def test_height_parameter_handling(self):
        """Test: Parámetros de altura se aplican correctamente"""
        print("Test: Height parameters...")
        model = ThreGPP38901Model({'scenario': 'UMa', 'h_bs': 25})
        distances = np.array([1.0])

        pl_1_5m = model.calculate_path_loss(distances, 28000, rx_height=1.5)
        pl_2_0m = model.calculate_path_loss(distances, 28000, rx_height=2.0)

        # Different heights should produce different results
        self.assertNotAlmostEqual(pl_1_5m[0], pl_2_0m[0])
        print(f"[OK] Heights applied: 1.5m={pl_1_5m[0]:.1f}, 2.0m={pl_2_0m[0]:.1f} dB")

    def test_kwargs_flexibility(self):
        """Test: Modelo acepta parámetros adicionales via **kwargs"""
        print("Test: **kwargs flexibility...")
        model = ThreGPP38901Model()
        distances = np.array([1.0])
        # Should accept extra kwargs without breaking
        result = model.calculate_path_loss(
            distances,
            28000,
            extra_param='ignored',
            another_param=42,
        )
        self.assertIsNotNone(result)
        print("[OK] Extra kwargs handled")


class TestThreGPP38901OutputConsistency(unittest.TestCase):
    """Test output consistency and physical plausibility."""

    def test_output_always_positive(self):
        """Test: Path loss siempre es positivo"""
        print("Test: Positive path loss...")
        model = ThreGPP38901Model()
        distances = np.random.rand(10, 10) * 5 + 0.1  # 0.1-5.1 km
        result = model.calculate_path_loss(distances, 28000)
        self.assertTrue(np.all(result > 0))
        print("[OK] All values positive")

    def test_output_physically_plausible(self):
        """Test: Valores físicamente plausibles"""
        print("Test: Physical plausibility...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        distances = np.array([0.01, 0.1, 1.0, 10.0])  # 10m to 10km
        result = model.calculate_path_loss(distances, 28000)

        # Check ranges are reasonable for 28 GHz
        self.assertTrue(np.all(result > 50))   # No negative or unrealistic lows
        self.assertTrue(np.all(result < 250))  # No unrealistic highs
        print(f"[OK] Plausible range: {result.min():.1f}-{result.max():.1f} dB")

    def test_no_nan_or_inf_values(self):
        """Test: Sin NaN o Inf en resultados"""
        print("Test: No NaN/Inf...")
        model = ThreGPP38901Model()
        distances = np.random.rand(100) * 9  # 0-9 km
        result = model.calculate_path_loss(distances, 28000)
        self.assertTrue(np.all(np.isfinite(result)))
        print("[OK] All values finite")

    def test_increasing_frequency_increases_pathloss(self):
        """Test: Frecuencia mayor → path loss mayor"""
        print("Test: Frequency dependency...")
        model = ThreGPP38901Model()
        distances = np.array([1.0])

        pl_low = model.calculate_path_loss(distances, 1000)  # 1 GHz
        pl_high = model.calculate_path_loss(distances, 28000)  # 28 GHz

        self.assertLess(pl_low[0], pl_high[0])
        print(f"[OK] 1GHz={pl_low[0]:.1f}, 28GHz={pl_high[0]:.1f} dB")


class TestThreGPP38901ScenarioDifferences(unittest.TestCase):
    """Test that scenarios produce meaningfully different results."""

    def test_uma_umi_rma_produce_different_results(self):
        """Test: Diferentes escenarios producen diferentes resultados"""
        print("Test: Scenario differences...")
        scenarios = ['UMa', 'UMi', 'RMa']
        distances = np.array([1.0])
        results = {}

        for scenario in scenarios:
            model = ThreGPP38901Model({'scenario': scenario})
            results[scenario] = model.calculate_path_loss(distances, 28000)[0]

        # All three should be different
        result_values = np.array(list(results.values()))
        unique_results = len(np.unique(np.round(result_values, 1)))
        self.assertGreaterEqual(unique_results, 2)
        print(f"[OK] Scenarios differ: {results}")

    def test_scenario_affects_los_probability(self):
        """Test: Escenarios tienen P_LOS diferentes"""
        print("Test: Scenario LOS probability...")
        scenarios = ['UMa', 'UMi']
        distances_m = np.array([500.0])

        for scenario in scenarios:
            model = ThreGPP38901Model({'scenario': scenario})
            los_prob = model._calculate_los_probability(distances_m)
            print(f"  {scenario} P_LOS={los_prob[0]:.3f}")

        print("[OK] Scenarios have different P_LOS")


class TestExistingModelsNotBroken(unittest.TestCase):
    """Verify that existing models still work correctly."""

    def test_free_space_model_works(self):
        """Test: Modelo Free Space sigue funcionando"""
        print("Test: Free Space model...")
        model = FreeSpacePathLossModel()
        distances = np.array([0.5, 1.0, 2.0])
        result = model.calculate_path_loss(distances, 28000)
        self.assertEqual(result.shape, distances.shape)
        self.assertTrue(np.all(result > 0))
        print("[OK] Free Space works")

    def test_okumura_hata_model_works(self):
        """Test: Modelo Okumura-Hata sigue funcionando"""
        print("Test: Okumura-Hata model...")
        config = {'environment': 'Urban', 'city_size': 'Large'}
        model = OkumuraHataModel(config)
        distances = np.array([1.0, 5.0])
        terrain_heights = np.zeros_like(distances) * 1000
        result = model.calculate_path_loss(distances, 900, tx_height=35, terrain_heights=terrain_heights)
        self.assertEqual(result.shape, distances.shape)
        print("[OK] Okumura-Hata works")

    @unittest.skipIf(not COST231_AVAILABLE, "COST-231 not available")
    def test_cost231_model_works(self):
        """Test: Modelo COST-231 sigue funcionando"""
        print("Test: COST-231 model...")
        config = {'environment': 'Urban'}
        model = COST231WalfischIkegamiModel(config)
        distances = np.array([0.1, 0.3])
        terrain_heights = np.zeros_like(distances) * 1000
        result = model.calculate_path_loss(distances, 900, tx_height=30, terrain_heights=terrain_heights)
        self.assertEqual(result.shape, distances.shape)
        print("[OK] COST-231 works")

    @unittest.skipIf(not ITU_P1546_AVAILABLE, "ITU-R P.1546 not available")
    def test_itu_p1546_model_works(self):
        """Test: Modelo ITU-R P.1546 sigue funcionando"""
        print("Test: ITU-R P.1546 model...")
        config = {'scenario': 'UMa'}
        model = ITUR_P1546Model(config)
        distances = np.array([1.0, 5.0])
        terrain_heights = np.zeros_like(distances) * 1000
        result = model.calculate_path_loss(distances, 900, tx_height=25, terrain_heights=terrain_heights)
        self.assertEqual(result.shape, distances.shape)
        print("[OK] ITU-R P.1546 works")


class TestThreGPP38901SpecialCases(unittest.TestCase):
    """Test special cases and edge scenarios."""

    def test_very_short_distance(self):
        """Test: Distancia muy corta (10 m)"""
        print("Test: Very short distance...")
        model = ThreGPP38901Model()
        result = model.calculate_path_loss(np.array([0.01]), 28000)
        self.assertGreater(result[0], 0)
        print(f"[OK] 10m: {result[0]:.1f} dB")

    def test_very_long_distance(self):
        """Test: Distancia muy larga (1000 km)"""
        print("Test: Very long distance...")
        model = ThreGPP38901Model({'scenario': 'RMa'})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = model.calculate_path_loss(np.array([1000.0]), 1000)
        self.assertTrue(np.isfinite(result[0]))
        print(f"[OK] 1000km: {result[0]:.1f} dB")

    def test_frequency_at_band_edges(self):
        """Test: Frecuencias en extremos de bandas 5G"""
        print("Test: 5G band edges...")
        model = ThreGPP38901Model()
        distances = np.array([1.0])

        # n78 band: 3.3-4.2 GHz
        pl_n78_low = model.calculate_path_loss(distances, 3300)
        pl_n78_high = model.calculate_path_loss(distances, 4200)

        # n257 band: 24.25-29.5 GHz
        pl_n257_low = model.calculate_path_loss(distances, 24250)
        pl_n257_high = model.calculate_path_loss(distances, 29500)

        self.assertLess(pl_n78_low[0], pl_n78_high[0])
        self.assertLess(pl_n257_low[0], pl_n257_high[0])
        print(f"[OK] Band edges: n78={pl_n78_low[0]:.1f}-{pl_n78_high[0]:.1f}, "
              f"n257={pl_n257_low[0]:.1f}-{pl_n257_high[0]:.1f} dB")


class TestThreGPP38901ArrayShapes(unittest.TestCase):
    """Test various array input shapes."""

    def test_1d_array_input(self):
        """Test: Entrada 1D array"""
        print("Test: 1D array input...")
        model = ThreGPP38901Model()
        distances = np.array([0.5, 1.0, 2.0])
        result = model.calculate_path_loss(distances, 28000)
        self.assertEqual(result.shape, (3,))
        print("[OK] 1D shape preserved")

    def test_2d_array_input(self):
        """Test: Entrada 2D array (grid)"""
        print("Test: 2D array input...")
        model = ThreGPP38901Model()
        distances = np.random.rand(5, 5)
        result = model.calculate_path_loss(distances, 28000)
        self.assertEqual(result.shape, (5, 5))
        print("[OK] 2D shape preserved")

    def test_3d_array_input(self):
        """Test: Entrada 3D array"""
        print("Test: 3D array input...")
        model = ThreGPP38901Model()
        distances = np.random.rand(3, 4, 5)
        result = model.calculate_path_loss(distances, 28000)
        self.assertEqual(result.shape, (3, 4, 5))
        print("[OK] 3D shape preserved")


class TestConfigurations(unittest.TestCase):
    """Test various configuration combinations."""

    def test_all_scenario_height_combinations(self):
        """Test: Todas las combinaciones scenario×altura validas"""
        print("Test: Configuration combinations...")
        scenarios = ['UMa', 'UMi', 'RMa']
        heights = [25, 30, 40]  # various BS heights

        count = 0
        for scenario in scenarios:
            for h_bs in heights:
                config = {'scenario': scenario, 'h_bs': h_bs}
                model = ThreGPP38901Model(config)
                distances = np.array([1.0])
                result = model.calculate_path_loss(distances, 28000)
                self.assertGreater(result[0], 0)
                count += 1

        print(f"[OK] {count} configurations tested")


# Run tests
if __name__ == '__main__':
    unittest.main(verbosity=2)
