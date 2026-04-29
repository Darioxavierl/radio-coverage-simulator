"""
Test to verify that all propagation models handle distance units consistently.
PHASE 2 validation: All models receive distances in meters (from Haversine).
"""

import unittest
import numpy as np
from pathlib import Path
import sys
import warnings

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

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

from core.models.gpp_3gpp.three_gpp_38901 import ThreGPP38901Model


class TestUnitsConsistency(unittest.TestCase):
    """Verify all models receive distances in meters and produce plausible results."""

    def test_free_space_with_meter_distances(self):
        """Test: Free Space modelo con distancias en metros"""
        print("Test: Free Space meter distances...")

        model = FreeSpacePathLossModel(compute_module=np)

        # Distancias típicas en metros: 100m, 1km, 5km, 10km
        distances_m = np.array([100.0, 1000.0, 5000.0, 10000.0])
        frequency_mhz = 2600

        path_loss = model.calculate_path_loss(distances_m, frequency_mhz)

        # Validar rango razonable para Free Space
        self.assertTrue(np.all(path_loss >= 50))
        self.assertTrue(np.all(path_loss <= 150))

        # Validar monotonicidad: mayor distancia → mayor path loss
        self.assertTrue(np.all(np.diff(path_loss) > 0),
                       msg="Path loss should increase with distance")

        print("[OK] Distances: {}m -> Path loss: {} dB".format(distances_m, path_loss))

    def test_okumura_hata_with_meter_distances(self):
        """Test: Okumura-Hata modelo con distancias en metros"""
        print("Test: Okumura-Hata meter distances...")

        config = {'environment': 'Urban', 'city_type': 'medium'}
        model = OkumuraHataModel(config=config, compute_module=np)

        distances_m = np.array([1000.0, 5000.0, 10000.0, 20000.0])  # 1-20 km
        frequency_mhz = 900  # GSM band

        path_loss = model.calculate_path_loss(
            distances_m, frequency_mhz,
            tx_height=35,
            terrain_heights=np.zeros_like(distances_m)
        )

        # Validar rango para Okumura-Hata
        self.assertTrue(np.all(path_loss >= 50))
        self.assertTrue(np.all(path_loss <= 200))

        # Validar monotonicidad
        self.assertTrue(np.all(np.diff(path_loss) > 0))

        print("[OK] Distances: {}m -> Path loss: {} dB".format(distances_m, path_loss))

    @unittest.skipIf(not COST231_AVAILABLE, "COST-231 not available")
    def test_cost231_with_meter_distances(self):
        """Test: COST-231 modelo con distancias en metros"""
        print("Test: COST-231 meter distances...")

        config = {'building_height': 15.0, 'street_width': 12.0}
        model = COST231WalfischIkegamiModel(config=config, compute_module=np)

        # COST-231 es para corta distancia: 20m-5km
        distances_m = np.array([50.0, 100.0, 500.0, 1000.0, 2000.0])
        frequency_mhz = 900

        path_loss = model.calculate_path_loss(
            distances_m, frequency_mhz,
            tx_height=30,
            terrain_heights=np.zeros_like(distances_m)
        )

        # Validar rango para COST-231
        self.assertTrue(np.all(path_loss >= 50))
        self.assertTrue(np.all(path_loss <= 180))

        # Validar monotonicidad
        self.assertTrue(np.all(np.diff(path_loss) > 0))

        print("[OK] Distances: {}m -> Path loss: {} dB".format(distances_m, path_loss))

    @unittest.skipIf(not ITU_P1546_AVAILABLE, "ITU-R P.1546 not available")
    def test_itu_p1546_with_meter_distances(self):
        """Test: ITU-R P.1546 modelo con distancias en metros"""
        print("Test: ITU-R P.1546 meter distances...")

        config = {'environment': 'Urban'}
        model = ITUR_P1546Model(config=config, compute_module=np)

        # ITU-R P.1546 válido para 1-1000 km (1000-1e6 metros)
        distances_m = np.array([1000.0, 10000.0, 100000.0, 500000.0])
        frequency_mhz = 900

        path_loss = model.calculate_path_loss(
            distances_m, frequency_mhz,
            tx_height=30,
            terrain_heights=np.zeros_like(distances_m)
        )

        # Validar rango para ITU-R P.1546
        self.assertTrue(np.all(path_loss >= 50))
        self.assertTrue(np.all(path_loss <= 250))

        # Validar monotonicidad
        self.assertTrue(np.all(np.diff(path_loss) > 0))

        print("[OK] Distances: {}m -> Path loss: {} dB".format(distances_m, path_loss))

    def test_three_gpp_with_meter_distances(self):
        """Test: 3GPP TR 38.901 modelo con distancias en metros"""
        print("Test: 3GPP 38.901 meter distances...")

        model = ThreGPP38901Model(
            config={'scenario': 'UMa'},
            numpy_module=np
        )

        # 3GPP válido para 10m-10km (10-1e4 metros)
        distances_m = np.array([10.0, 100.0, 1000.0, 5000.0, 10000.0])
        frequency_mhz = 3500  # n78 band

        path_loss = model.calculate_path_loss(distances_m, frequency_mhz)

        # Validar rango para 3GPP
        self.assertTrue(np.all(path_loss >= 20))
        self.assertTrue(np.all(path_loss <= 200))

        # Validar monotonicidad
        self.assertTrue(np.all(np.diff(path_loss) > 0))

        print("[OK] Distances: {}m -> Path loss: {} dB".format(distances_m, path_loss))

    def test_no_unit_detection_heuristics_in_3gpp(self):
        """Test: 3GPP NO usa heurísticas de detección de unidades"""
        print("Test: No unit detection heuristics...")

        model = ThreGPP38901Model(
            config={'scenario': 'UMa'},
            numpy_module=np
        )

        # Distancias pequeñas (70m) que podrían confundir heurística vieja
        # Heurística vieja: if max(distances) > 100: asumir metros, else asumir km
        # Nueva: SIEMPRE asumir metros
        distances_small_m = np.array([10.0, 50.0, 70.0])  # Todos < 100

        # Calcular sin warnings sobre rango
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            pl_small = model.calculate_path_loss(distances_small_m, 28000)

            # No debe haber warnings por distancia pequeña
            # (solo puede haber warning de "outside valid range" si distancia muy pequeña)
            warnings_about_units = [x for x in w if 'meter' in str(x.message).lower()]
            self.assertEqual(len(warnings_about_units), 0,
                           msg="Should not have unit ambiguity warnings")

        # Path loss debe ser consistente: distancia mayor → path loss mayor
        self.assertTrue(np.all(np.diff(pl_small) > 0))

        print(f"[OK] Small distances handled correctly: {distances_small_m}m")

    def test_frequency_independence_from_units(self):
        """Test: Frecuencia no afectada por cambios de unidades"""
        print("Test: Frequency independence...")

        model = FreeSpacePathLossModel(compute_module=np)
        distance_m = np.array([1000.0])  # 1 km = 1000 m

        # Misma distancia, diferentes frecuencias
        pl_900mhz = model.calculate_path_loss(distance_m, 900)
        pl_1800mhz = model.calculate_path_loss(distance_m, 1800)
        pl_2600mhz = model.calculate_path_loss(distance_m, 2600)

        # Mayor frecuencia → mayor path loss (siempre)
        self.assertLess(pl_900mhz[0], pl_1800mhz[0])
        self.assertLess(pl_1800mhz[0], pl_2600mhz[0])

        print(f"[OK] Frequency effect: 900MHz={pl_900mhz[0]:.1f}dB < 1800MHz={pl_1800mhz[0]:.1f}dB < 2600MHz={pl_2600mhz[0]:.1f}dB")

    def test_typical_simulation_range_all_models(self):
        """Test: Rango típico de simulación (5km grid)"""
        print("Test: Typical simulation range...")

        # Simulación típica: radius_km=5, resolution=100
        # Máxima distancia: ~7.07 km = 7070 metros
        # Mínima distancia: ~0 m (antena location)

        typical_distances = np.linspace(1, 7070, 10)  # 1m a 7070m

        models_config = [
            ("Free Space", FreeSpacePathLossModel(compute_module=np), {}),
            ("Okumura-Hata", OkumuraHataModel({'environment': 'Urban'}, compute_module=np),
             {'tx_height': 25, 'terrain_heights': np.zeros_like(typical_distances)}),
            ("3GPP UMa", ThreGPP38901Model({'scenario': 'UMa'}, numpy_module=np), {}),
        ]

        if COST231_AVAILABLE:
            models_config.append(("COST-231",
                                COST231WalfischIkegamiModel({'building_height': 15.0}, compute_module=np),
                                {'tx_height': 30, 'terrain_heights': np.zeros_like(typical_distances)}))

        for model_name, model, extra_kwargs in models_config:
            try:
                pl = model.calculate_path_loss(typical_distances, 2600, **extra_kwargs)

                # Todas las pérdidas deben ser positivas y finitas
                self.assertTrue(np.all(pl > 0))
                self.assertTrue(np.all(np.isfinite(pl)))

                # Deben ser monótonas (salvo posible variabilidad en ITU-R por LOS/NLOS)
                if model_name not in ['ITU-R P.1546']:
                    self.assertTrue(np.all(np.diff(pl) > -5),  # Permitir pequeña variabilidad
                                   msg=f"{model_name} should be mostly monotonic")

                print(f"  [OK] {model_name}: range {pl.min():.1f}-{pl.max():.1f} dB")

            except Exception as e:
                self.fail(f"{model_name} failed with typical range: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
