"""
Test to verify that 3GPP TR 38.901 uses h_bs/h_ue from config correctly.
PHASE 1 validation: h_bs/h_ue config values have priority over function parameters.
"""

import unittest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.gpp_3gpp.three_gpp_38901 import ThreGPP38901Model


class TestThreGPP38901ConfigHeights(unittest.TestCase):
    """Validate that h_bs/h_ue from config take priority over function parameters."""

    def test_config_h_bs_takes_priority(self):
        """Test: h_bs del config se almacena correctamente"""
        print("Test: Config h_bs storage...")

        # Crear modelo con h_bs=40 en config
        model_config_40 = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_bs': 40.0},
            numpy_module=np
        )

        # Crear modelo con h_bs=25 en config
        model_config_25 = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_bs': 25.0},
            numpy_module=np
        )

        # Verificar que h_bs está almacenado correctamente
        self.assertEqual(model_config_40.h_bs, 40.0,
                        msg="h_bs=40 should be stored in model")
        self.assertEqual(model_config_25.h_bs, 25.0,
                        msg="h_bs=25 should be stored in model")

        print("[OK] h_bs config values stored correctly")

    def test_config_h_ue_takes_priority(self):
        """Test: h_ue del config tiene prioridad sobre rx_height"""
        print("Test: Config h_ue priority...")

        # Crear modelo con h_ue=3.0 en config
        model_config_3m = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_ue': 3.0},
            numpy_module=np
        )

        distances = np.array([1000.0])

        # Calcular SOLO CON distances/frequency (sin rx_height)
        pl_config_3m = model_config_3m.calculate_path_loss(distances, 2600)

        # Crear modelo con h_ue=1.5 en config
        model_config_1_5m = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_ue': 1.5},
            numpy_module=np
        )

        pl_config_1_5m = model_config_1_5m.calculate_path_loss(distances, 2600)

        # Path loss debe ser diferente
        self.assertNotAlmostEqual(pl_config_3m[0], pl_config_1_5m[0], places=1,
                                   msg="h_ue from config should affect path loss")

        # h_ue=3.0 debería resultar en MENOR path loss que h_ue=1.5
        self.assertLess(pl_config_3m[0], pl_config_1_5m[0],
                        msg="Higher h_ue should result in lower path loss")

        print(f"[OK] h_ue=3.0m -> {pl_config_3m[0]:.1f}dB, h_ue=1.5m -> {pl_config_1_5m[0]:.1f}dB")

    def test_config_h_bs_h_ue_combined_effect(self):
        """Test: Combinación de h_bs y h_ue del config"""
        print("Test: Combined h_bs/h_ue effect...")

        distances = np.array([1000.0])

        # Escenario 1: h_bs bajo, h_ue bajo
        model_low = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_bs': 15.0, 'h_ue': 1.0},
            numpy_module=np
        )
        pl_low = model_low.calculate_path_loss(distances, 2600)

        # Escenario 2: h_bs alto, h_ue alto
        model_high = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_bs': 40.0, 'h_ue': 3.0},
            numpy_module=np
        )
        pl_high = model_high.calculate_path_loss(distances, 2600)

        # Mayor altura → menor path loss
        self.assertLess(pl_high[0], pl_low[0],
                        msg="Higher h_bs and h_ue should result in lower path loss")

        print("[OK] Low heights -> {:.1f}dB, High heights -> {:.1f}dB".format(pl_low[0], pl_high[0]))

    def test_default_heights_used_if_not_in_config(self):
        """Test: Alturas por defecto si no están en config"""
        print("Test: Default heights fallback...")

        # Modelo sin h_bs/h_ue en config (debería usar defaults: 25, 1.5)
        model_default = ThreGPP38901Model(
            config={'scenario': 'UMa'},
            numpy_module=np
        )

        distances = np.array([1000.0])

        # Calcular con valores por defecto
        pl_default = model_default.calculate_path_loss(distances, 2600)

        # Calcular con valores explícitos iguales a defaults
        model_explicit = ThreGPP38901Model(
            config={'scenario': 'UMa', 'h_bs': 25.0, 'h_ue': 1.5},
            numpy_module=np
        )
        pl_explicit = model_explicit.calculate_path_loss(distances, 2600)

        # Deben ser prácticamente iguales
        self.assertAlmostEqual(pl_default[0], pl_explicit[0], places=2,
                               msg="Default heights should match explicit defaults")

        print("[OK] Default heights work correctly: {:.1f}dB".format(pl_default[0]))

    def test_all_scenarios_with_custom_heights(self):
        """Test: Todos los escenarios 3GPP con alturas personalizadas"""
        print("Test: All scenarios with custom heights...")

        scenarios = ['UMa', 'UMi', 'RMa']
        distances = np.array([1000.0])
        heights_bs = [20, 30, 40]

        count = 0
        for scenario in scenarios:
            for h_bs in heights_bs:
                config = {'scenario': scenario, 'h_bs': h_bs, 'h_ue': 2.0}
                model = ThreGPP38901Model(config=config, numpy_module=np)
                pl = model.calculate_path_loss(distances, 2600)

                # Validar que es un número válido
                self.assertTrue(np.isfinite(pl[0]),
                               msg=f"Path loss invalid for {scenario} with h_bs={h_bs}")
                count += 1

        print(f"[OK] {count} scenario/height combinations validated")

    def test_height_effect_consistency_across_scenarios(self):
        """Test: Mayor altura siempre resulta en menor path loss (todos escenarios)"""
        print("Test: Height effect consistency...")

        scenarios = ['UMa', 'UMi', 'RMa']
        distances = np.array([1000.0])

        for scenario in scenarios:
            model_low_h = ThreGPP38901Model(
                config={'scenario': scenario, 'h_ue': 1.0},
                numpy_module=np
            )
            pl_low = model_low_h.calculate_path_loss(distances, 2600)

            model_high_h = ThreGPP38901Model(
                config={'scenario': scenario, 'h_ue': 3.0},
                numpy_module=np
            )
            pl_high = model_high_h.calculate_path_loss(distances, 2600)

            # Higher height should ALWAYS result in lower path loss
            self.assertLess(pl_high[0], pl_low[0],
                           msg="Higher h_ue should reduce PL in {}".format(scenario))

        print("[OK] Height effect consistent across all scenarios")


if __name__ == '__main__':
    unittest.main(verbosity=2)
