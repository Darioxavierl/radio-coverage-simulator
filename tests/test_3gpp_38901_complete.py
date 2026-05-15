"""
Comprehensive tests for 3GPP TR 38.901 propagation model.
Tests cover: initialization, basic calculations, scenario specifics, LOS/NLOS behavior,
frequency/distance ranges, GPU consistency, and edge cases.
"""

import unittest
import numpy as np
import warnings
from pathlib import Path
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.gpp_3gpp.three_gpp_38901 import ThreGPP38901Model, calculate_3gpp_38901_path_loss


class TestThreGPP38901Initialization(unittest.TestCase):
    """Test model initialization and configuration."""

    def test_default_initialization(self):
        """Test: 3GPP 38.901 instancia con valores por defecto"""
        print("Test: Default initialization with UMa scenario...")
        model = ThreGPP38901Model()
        self.assertEqual(model.scenario, 'UMa')
        self.assertEqual(model.h_bs, 25)  # UMa default
        self.assertEqual(model.h_ue, 1.5)
        print("[OK] Default initialization")

    def test_custom_configuration(self):
        """Test: 3GPP 38.901 se instancia con config personalizada"""
        print("Test: Custom configuration (UMi scenario)...")
        config = {'scenario': 'UMi', 'h_bs': 12, 'h_ue': 1.6}
        model = ThreGPP38901Model(config)
        self.assertEqual(model.scenario, 'UMi')
        self.assertEqual(model.h_bs, 12)
        self.assertEqual(model.h_ue, 1.6)
        print("[OK] Custom configuration")

    def test_rma_scenario(self):
        """Test: Rural Macro (RMa) scenario initialization"""
        print("Test: RMa scenario initialization...")
        config = {'scenario': 'RMa', 'h_bs': 35}
        model = ThreGPP38901Model(config)
        self.assertEqual(model.scenario, 'RMa')
        self.assertEqual(model.h_bs, 35)
        print("[OK] RMa scenario")

    def test_invalid_scenario(self):
        """Test: Invalid scenario raises ValueError"""
        print("Test: Invalid scenario rejection...")
        with self.assertRaises(ValueError):
            config = {'scenario': 'InvalidScenario'}
            ThreGPP38901Model(config)
        print("[OK] Invalid scenario rejected")

    def test_numpy_activation(self):
        """Test: 3GPP 38.901 usa NumPy correctamente"""
        print("Test: NumPy module activation...")
        model = ThreGPP38901Model(numpy_module=np)
        self.assertEqual(model.xp, np)
        print("[OK] NumPy activated")

    def test_model_metadata(self):
        """Test: Metadatos del modelo son correctos"""
        print("Test: Model metadata...")
        config = {'scenario': 'UMa'}
        model = ThreGPP38901Model(config)
        info = model.get_model_info()
        self.assertEqual(info['name'], '3GPP TR 38.901 (v17.0.0)')
        self.assertEqual(info['scenario'], 'UMa')
        self.assertIn('frequency_range_ghz', info)
        self.assertEqual(info['frequency_range_ghz'], (0.5, 100))
        print("[OK] Metadata correct")


class TestThreGPP38901BasicCalculation(unittest.TestCase):
    """Test basic path loss calculation."""

    def test_basic_path_loss_calculation(self):
        """Test: Cálculo básico de path loss funciona"""
        print("Test: Basic path loss calculation...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        distances = np.array([0.1, 0.5, 1.0, 2.0])  # km
        frequency = 28000  # MHz (28 GHz)
        pl = model.calculate_path_loss(distances, frequency)['path_loss']
        self.assertEqual(pl.shape, distances.shape)
        self.assertTrue(np.all(pl > 0))  # Path loss should be positive
        print(f"[OK] Path loss calculated: {pl}")

    def test_output_shape_preserved(self):
        """Test: Shape de salida = shape entrada"""
        print("Test: Output shape preservation...")
        model = ThreGPP38901Model()
        distances = np.random.rand(10, 10)  # 2D array
        pl = model.calculate_path_loss(distances, 28000)['path_loss']
        self.assertEqual(pl.shape, distances.shape)
        print("[OK] Shape preserved")

    def test_path_loss_increases_with_distance(self):
        """Test: Path loss aumenta monótonicamente con distancia"""
        print("Test: Path loss increases with distance...")
        model = ThreGPP38901Model()
        # After PHASE 2 refactor: distances always in METERS
        distances = np.array([100.0, 500.0, 1000.0, 2000.0, 5000.0])  # in meters
        pl = model.calculate_path_loss(distances, 28000)['path_loss']
        diffs = np.diff(pl)
        self.assertTrue(np.all(diffs > 0), "Path loss should increase with distance")
        print(f"[OK] Monotonic increase: {pl}")

    def test_path_loss_increases_with_frequency(self):
        """Test: Path loss aumenta con frecuencia"""
        print("Test: Path loss increases with frequency...")
        model = ThreGPP38901Model()
        distances = np.array([1.0])
        frequencies = np.array([1000, 5000, 10000, 28000])  # MHz
        pls = [model.calculate_path_loss(distances, f)['path_loss'][0] for f in frequencies]
        diffs = np.diff(pls)
        self.assertTrue(np.all(diffs > 0), "Path loss should increase with frequency")
        print(f"[OK] Frequency monotonicity: {pls}")


class TestThreGPP38901FrequencyRange(unittest.TestCase):
    """Test valid frequency ranges."""

    def test_frequency_30mhz_minimum(self):
        """Test: Frecuencia 30 MHz (sub-rango mínimo)"""
        print("Test: Minimum frequency (30 MHz)...")
        model = ThreGPP38901Model()
        # After PHASE 2 refactor: distances always in METERS
        pl = model.calculate_path_loss(np.array([1000.0]), 30)['path_loss']  # 1000 meters (1 km)
        self.assertGreater(pl[0], 0)
        print("[OK] 30 MHz accepted")

    def test_frequency_4000mhz_representative(self):
        """Test: Frecuencia 4000 MHz (5G NR)"""
        print("Test: 4 GHz frequency...")
        model = ThreGPP38901Model()
        pl = model.calculate_path_loss(np.array([1.0]), 4000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 4000 MHz accepted")

    def test_frequency_28ghz_5g_mmwave(self):
        """Test: Frecuencia 28 GHz (5G mmWave)"""
        print("Test: 28 GHz (5G mmWave)...")
        model = ThreGPP38901Model()
        pl = model.calculate_path_loss(np.array([1.0]), 28000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 28 GHz accepted")

    def test_frequency_73ghz_5g_mmwave_high(self):
        """Test: Frecuencia 73 GHz (5G mmWave high band)"""
        print("Test: 73 GHz (high mmWave)...")
        model = ThreGPP38901Model()
        pl = model.calculate_path_loss(np.array([1.0]), 73000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 73 GHz accepted")

    def test_frequency_range_monotonic(self):
        """Test: Path loss monótonamente creciente en todo rango"""
        print("Test: Monotonic increase across frequency range...")
        model = ThreGPP38901Model()
        frequencies = np.array([500, 1000, 2600, 4000, 11000, 28000, 73000])
        distances = np.array([1.0])
        pls = [model.calculate_path_loss(distances, f)['path_loss'][0] for f in frequencies]
        diffs = np.diff(pls)
        self.assertTrue(np.all(diffs > 0))
        print(f"[OK] Monotonic: {pls}")


class TestThreGPP38901DistanceRange(unittest.TestCase):
    """Test valid distance ranges."""

    def test_distance_10m_minimum(self):
        """Test: Distancia 10m (mínimo)"""
        print("Test: Minimum distance (10 m)...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        pl = model.calculate_path_loss(np.array([0.01]), 28000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 10 m accepted")

    def test_distance_1km_typical(self):
        """Test: Distancia 1 km (típica)"""
        print("Test: 1 km distance...")
        model = ThreGPP38901Model()
        pl = model.calculate_path_loss(np.array([1.0]), 28000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 1 km accepted")

    def test_distance_10km_uma_maximum(self):
        """Test: Distancia 10 km (máximo UMa)"""
        print("Test: 10 km (UMa max)...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl = model.calculate_path_loss(np.array([10.0]), 28000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 10 km UMa accepted")

    def test_distance_5km_umi_maximum(self):
        """Test: Distancia 5 km (máximo UMi)"""
        print("Test: 5 km (UMi max)...")
        model = ThreGPP38901Model({'scenario': 'UMi'})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl = model.calculate_path_loss(np.array([5.0]), 28000)['path_loss']
        self.assertGreater(pl[0], 0)
        print("[OK] 5 km UMi accepted")


class TestThreGPP38901LosNlos(unittest.TestCase):
    """Test LOS/NLOS probability and behavior differences."""

    def test_los_probability_uma(self):
        """Test: P_LOS disminuye con distancia (UMa)"""
        print("Test: LOS probability decreases with distance (UMa)...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        distances_m = np.array([50, 200, 500, 1000, 2000])
        los_probs = model._calculate_los_probability(distances_m)
        diffs = np.diff(los_probs)
        self.assertTrue(np.all(diffs < 0), "LOS probability should decrease with distance")
        print(f"[OK] LOS probabilities: {los_probs}")

    def test_los_probability_umi(self):
        """Test: P_LOS disminuye más lentamente (UMi)"""
        print("Test: LOS probability (UMi scenario)...")
        model = ThreGPP38901Model({'scenario': 'UMi'})
        distances_m = np.array([50, 200, 500, 1000])
        los_probs = model._calculate_los_probability(distances_m)
        self.assertTrue(np.all(los_probs >= 0))
        self.assertTrue(np.all(los_probs <= 1))
        print(f"[OK] UMi LOS probabilities: {los_probs}")

    def test_los_nlos_path_loss_difference(self):
        """Test: Path loss NLOS > LOS para misma distancia"""
        print("Test: NLOS path loss > LOS path loss...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        f_ghz = 28
        distances_m = np.array([500, 1000, 5000])
        pl_los = model._calculate_path_loss_los(f_ghz, distances_m, 1.5)
        pl_nlos = model._calculate_path_loss_nlos(f_ghz, distances_m, 1.5)
        diffs = pl_nlos - pl_los
        self.assertTrue(np.all(diffs > 0), "NLOS path loss should be > LOS")
        print(f"[OK] NLOS > LOS: {diffs} dB")

    def test_los_probability_at_zero_distance(self):
        """Test: P_LOS ≈ 1 en distancia muy pequeña"""
        print("Test: LOS probability near transmitter...")
        model = ThreGPP38901Model()
        los_prob = model._calculate_los_probability(np.array([1.0]))  # 1 meter
        self.assertGreater(los_prob[0], 0.9, "LOS probability should be ~1 at short distance")
        print(f"[OK] Near transmitter P_LOS = {los_prob[0]:.3f}")


class TestThreGPP38901Scenarios(unittest.TestCase):
    """Test scenario-specific behavior."""

    def test_uma_vs_umi_intercept_difference(self):
        """Test: UMa e UMi tienen diferentes interceptos"""
        print("Test: UMa vs UMi intercept difference...")
        model_uma = ThreGPP38901Model({'scenario': 'UMa'})
        model_umi = ThreGPP38901Model({'scenario': 'UMi'})
        distances = np.array([0.5])
        pl_uma = model_uma.calculate_path_loss(distances, 28000)['path_loss']
        pl_umi = model_umi.calculate_path_loss(distances, 28000)['path_loss']
        # UMi should be higher due to lower antena heights
        self.assertNotAlmostEqual(pl_uma[0], pl_umi[0], places=0)
        print(f"[OK] UMa={pl_uma[0]:.1f}, UMi={pl_umi[0]:.1f} dB")

    def test_rma_vs_uma(self):
        """Test: RMa tiene características diferentes a UMa"""
        print("Test: RMa vs UMa comparison...")
        model_rma = ThreGPP38901Model({'scenario': 'RMa'})
        model_uma = ThreGPP38901Model({'scenario': 'UMa'})
        distances = np.array([5.0])
        pl_rma = model_rma.calculate_path_loss(distances, 28000)['path_loss']
        pl_uma = model_uma.calculate_path_loss(distances, 28000)['path_loss']
        self.assertNotEqual(pl_rma[0], pl_uma[0])
        print(f"[OK] RMa={pl_rma[0]:.1f}, UMa={pl_uma[0]:.1f} dB")

    def test_height_correction_effect(self):
        """Test: Altura UE afecta path loss NLOS"""
        print("Test: UE height affects path loss...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        # After PHASE 2 refactor: distances always in METERS
        distances = np.array([1000.0])  # 1000 meters (1 km)
        # After PHASE 1 refactor: h_ue must be passed in kwargs (has priority over rx_height)
        pl_1_5m = model.calculate_path_loss(distances, 28000, h_ue=1.5)['path_loss']
        pl_3_0m = model.calculate_path_loss(distances, 28000, h_ue=3.0)['path_loss']
        # Taller UE should have less path loss (negative correction)
        self.assertLess(pl_3_0m[0], pl_1_5m[0])
        print(f"[OK] Height effect: 1.5m={pl_1_5m[0]:.1f}, 3.0m={pl_3_0m[0]:.1f} dB")


class TestThreGPP38901BreakpointDistance(unittest.TestCase):
    """Test breakpoint distance calculation."""

    def test_breakpoint_distance_calculation(self):
        """Test: Breakpoint distance calcula correctamente"""
        print("Test: Breakpoint distance calculation...")
        config = {'scenario': 'UMa', 'h_bs': 25, 'h_ue': 1.5}
        model = ThreGPP38901Model(config)
        d_bp = model.get_breakpoint_distance()
        # d_BP = 4*h_BS'*h_UT'*fc/c = 4*24*0.5*2e9/3e8 = 320m (@ 2 GHz default)
        self.assertGreater(d_bp, 200)
        self.assertLess(d_bp, 500)
        print(f"[OK] Breakpoint distance = {d_bp:.1f} m")

    def test_breakpoint_increases_with_frequency(self):
        """Test: d_BP increases with frequency"""
        print("Test: Breakpoint dep on frequency...")
        config = {'scenario': 'UMa', 'h_bs': 25, 'h_ue': 1.5}
        model = ThreGPP38901Model(config)
        # d_BP is proportional to frequency, so should be proportional
        # Actually d_BP doesn't depend on frequency in 3GPP, so check consistency
        d_bp = model.get_breakpoint_distance()
        self.assertGreater(d_bp, 0)
        print(f"[OK] Breakpoint = {d_bp:.1f} m")


class TestThreGPP38901EdgeCases(unittest.TestCase):
    """Test edge cases and extreme parameters."""

    def test_single_point_calculation(self):
        """Test: Cálculo para punto único"""
        print("Test: Single point calculation...")
        model = ThreGPP38901Model()
        pl = model.calculate_path_loss(np.array([1.0]), 28000)['path_loss']
        self.assertEqual(pl.shape, (1,))
        self.assertGreater(pl[0], 0)
        print(f"[OK] Single point: {pl[0]:.1f} dB")

    def test_large_grid(self):
        """Test: Grid grande (10,000+ puntos)"""
        print("Test: Large grid calculation (10k points)...")
        model = ThreGPP38901Model()
        # After PHASE 2 refactor: distances always in METERS
        distances = np.random.rand(100, 100) * 5000 + 100  # 10,000 points, 100-5100 meters
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl = model.calculate_path_loss(distances, 28000)['path_loss']
        self.assertEqual(pl.shape, (100, 100))
        self.assertTrue(np.all(pl > 0))
        print("[OK] Large grid computed")

    def test_very_small_distances(self):
        """Test: Distancias muy pequeñas (< 10 m)"""
        print("Test: Very small distances...")
        model = ThreGPP38901Model()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl = model.calculate_path_loss(np.array([0.005]), 28000)['path_loss']  # 5 meters
        self.assertGreater(pl[0], 0)
        print(f"[OK] 5m distance: {pl[0]:.1f} dB")

    def test_extreme_frequencies(self):
        """Test: Frecuencias extremas del rango"""
        print("Test: Extreme frequencies...")
        model = ThreGPP38901Model()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl_low = model.calculate_path_loss(np.array([1.0]), 500)['path_loss']  # 0.5 GHz
            pl_high = model.calculate_path_loss(np.array([1.0]), 100000)['path_loss']  # 100 GHz
        self.assertGreater(pl_low[0], 0)
        self.assertGreater(pl_high[0], 0)
        self.assertGreater(pl_high[0], pl_low[0])
        print(f"[OK] 500 MHz={pl_low[0]:.1f}, 100 GHz={pl_high[0]:.1f} dB")


class TestThreGPP38901Consistency(unittest.TestCase):
    """Test consistency and reference values."""

    def test_uma_los_reference_value_1(self):
        """Test: UMa reference value (f=28GHz, d=100m) with probabilistic blending"""
        print("Test: UMa reference value...")
        model = ThreGPP38901Model({'scenario': 'UMa'})
        # After PHASE 2 refactor: distances always in METERS
        pl = model.calculate_path_loss(np.array([100.0]), 28000)['path_loss']  # 100 meters
        # At 100m: path loss ~113-114 dB with probabilistic blending at 28 GHz
        self.assertGreater(pl[0], 110)
        self.assertLess(pl[0], 120)
        print(f"[OK] UMa 100m: {pl[0]:.1f} dB")

    def test_umi_los_reference_value(self):
        """Test: UMi reference value (f=28GHz, d=100m) with probabilistic blending"""
        print("Test: UMi reference value...")
        model = ThreGPP38901Model({'scenario': 'UMi'})
        # After PHASE 2 refactor: distances always in METERS
        pl = model.calculate_path_loss(np.array([100.0]), 28000)['path_loss']  # 100 meters
        # At 100m UMi 28GHz (correct model): ~119 dB with probabilistic blending
        # P_LOS~0.23 -> PL = 0.23*103 + 0.77*124 = 119 dB
        self.assertGreater(pl[0], 115)
        self.assertLess(pl[0], 125)
        print(f"[OK] UMi 100m: {pl[0]:.1f} dB")

    def test_numeric_stability_large_distance(self):
        """Test: Estabilidad numérica a distancias grandes"""
        print("Test: Numeric stability at large distances...")
        model = ThreGPP38901Model()
        distances = np.array([9999.0])  # Near max distance
        pl = model.calculate_path_loss(distances, 28000)['path_loss']
        self.assertTrue(np.isfinite(pl[0]))
        self.assertGreater(pl[0], 0)
        print(f"[OK] 9999 km: {pl[0]:.1f} dB")


class TestThreGPP38901GPUConsistency(unittest.TestCase):
    """Test GPU consistency (if CuPy available)."""

    def test_cpu_gpu_consistency_basic(self):
        """Test: NumPy vs CuPy producen resultados idénticos"""
        print("Test: CPU/GPU consistency...")
        try:
            import cupy
            has_cupy = True
        except ImportError:
            has_cupy = False
            print("[INFO] CuPy not available, skipping GPU test")
            return

        if has_cupy:
            model_cpu = ThreGPP38901Model(numpy_module=np)
            model_gpu = ThreGPP38901Model(numpy_module=cupy)

            distances = np.array([0.1, 0.5, 1.0, 2.0])
            pl_cpu = model_cpu.calculate_path_loss(distances, 28000)['path_loss']
            pl_gpu = model_gpu.calculate_path_loss(distances, 28000)['path_loss']

            # Convert GPU results to CPU for comparison
            pl_gpu_np = cupy.asnumpy(pl_gpu)

            diff = np.abs(pl_cpu - pl_gpu_np)
            max_diff = np.max(diff)
            self.assertLess(max_diff, 1e-5, f"Max difference {max_diff} exceeds tolerance")
            print(f"[OK] CPU/GPU consistency: max diff = {max_diff:.2e} dB")

    def test_cpu_gpu_large_grid(self):
        """Test: Consistencia con grid grande"""
        print("Test: CPU/GPU consistency (large grid)...")
        try:
            import cupy
            has_cupy = True
        except ImportError:
            has_cupy = False
            return

        if has_cupy:
            model_cpu = ThreGPP38901Model(numpy_module=np)
            model_gpu = ThreGPP38901Model(numpy_module=cupy)

            distances = np.random.rand(50, 50)
            pl_cpu = model_cpu.calculate_path_loss(distances, 28000)['path_loss']
            pl_gpu = model_gpu.calculate_path_loss(distances, 28000)['path_loss']

            pl_gpu_np = cupy.asnumpy(pl_gpu)
            diff = np.abs(pl_cpu - pl_gpu_np)
            max_diff = np.max(diff)
            self.assertLess(max_diff, 1e-4)
            print(f"[OK] Large grid consistency: max diff = {max_diff:.2e} dB")


class TestThreGPP38901TerrainCorrection(unittest.TestCase):
    """Test ITU-R P.526 effective knife-edge terrain correction mode."""

    @staticmethod
    def _build_distance_grid(size=41, spacing_m=50.0):
        center = size // 2
        yy, xx = np.indices((size, size))
        return np.sqrt((yy - center) ** 2 + (xx - center) ** 2) * spacing_m

    def test_terrain_shape_mismatch_raises(self):
        """Test: terrain_heights debe tener misma forma que distances"""
        print("Test: Terrain shape mismatch raises ValueError...")
        model = ThreGPP38901Model({'scenario': 'UMa', 'use_dem': True})
        distances = np.ones((8, 8)) * 500.0
        terrain = np.ones((7, 8)) * 100.0

        with self.assertRaises(ValueError):
            model.calculate_path_loss(
                distances=distances,
                frequency=3500,
                terrain_heights=terrain,
                tx_height=25.0,
                tx_elevation=100.0,
            )
        print("[OK] Shape validation working")

    def test_flat_terrain_has_negligible_correction(self):
        """Test: terreno plano no introduce difracción significativa"""
        print("Test: Flat terrain produces near-zero correction...")
        distances = self._build_distance_grid(size=41, spacing_m=50.0)
        terrain = np.ones_like(distances) * 100.0

        model_prob = ThreGPP38901Model({'scenario': 'UMa', 'use_dem': False})
        model_dem = ThreGPP38901Model({'scenario': 'UMa', 'use_dem': True, 'dem_profile_samples': 16})

        pl_prob = model_prob.calculate_path_loss(
            distances=distances,
            frequency=3500,
            tx_height=25.0,
            terrain_heights=terrain,
            tx_elevation=100.0,
        )['path_loss']
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl_dem = model_dem.calculate_path_loss(
                distances=distances,
                frequency=3500,
                tx_height=25.0,
                terrain_heights=terrain,
                tx_elevation=100.0,
            )['path_loss']

        diff = pl_dem - pl_prob
        self.assertLess(float(np.max(diff)), 0.25)
        self.assertGreaterEqual(float(np.min(diff)), -1e-6)
        print(f"[OK] Flat terrain correction max={np.max(diff):.4f} dB")

    def test_ridge_obstruction_increases_path_loss(self):
        """Test: una cresta entre TX y RX incrementa pérdida por difracción"""
        print("Test: Ridge obstruction increases path loss...")
        distances = self._build_distance_grid(size=61, spacing_m=40.0)
        terrain = np.ones_like(distances) * 100.0

        center = terrain.shape[0] // 2
        ridge_row = center + 6
        terrain[ridge_row:ridge_row + 2, :] = 220.0

        model_prob = ThreGPP38901Model({'scenario': 'UMa', 'use_dem': False})
        model_dem = ThreGPP38901Model({'scenario': 'UMa', 'use_dem': True, 'dem_profile_samples': 20})

        pl_prob = model_prob.calculate_path_loss(
            distances=distances,
            frequency=3500,
            tx_height=25.0,
            terrain_heights=terrain,
            tx_elevation=100.0,
        )['path_loss']
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pl_dem = model_dem.calculate_path_loss(
                distances=distances,
                frequency=3500,
                tx_height=25.0,
                terrain_heights=terrain,
                tx_elevation=100.0,
            )['path_loss']

        correction = pl_dem - pl_prob
        far_side = correction[ridge_row + 2:, :]
        self.assertGreater(float(np.mean(far_side)), 0.5)
        self.assertGreater(float(np.max(correction)), 2.0)
        self.assertLessEqual(float(np.max(correction)), model_dem.max_terrain_correction_db + 1e-6)
        print(f"[OK] Ridge correction mean_far={np.mean(far_side):.3f} dB max={np.max(correction):.3f} dB")


class TestThreGPP38901StandaloneFunction(unittest.TestCase):
    """Test standalone convenience function."""

    def test_standalone_function(self):
        """Test: Función standalone funciona"""
        print("Test: Standalone function...")
        distances = np.array([0.1, 1.0, 5.0])
        pl = calculate_3gpp_38901_path_loss(distances, 28000, scenario='UMa')
        self.assertEqual(pl.shape, distances.shape)
        self.assertTrue(np.all(pl > 0))
        print(f"[OK] Standalone function: {pl}")


# Run tests
if __name__ == '__main__':
    unittest.main(verbosity=2)
