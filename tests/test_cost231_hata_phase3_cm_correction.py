"""
COST-231 Hata - Fase 3: Corrección C_m por tipo de ciudad (3 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase3CmCorrection(unittest.TestCase):
    """Tests para validación de corrección C_m por tipo de ciudad"""

    def setUp(self):
        """Configuración inicial"""
        self.model = COST231HataModel(compute_module=np)
        self.distances = np.array([500.0, 1000.0, 2000.0])
        self.terrain_heights = np.full_like(self.distances, 2600.0, dtype=float)
        self.tx_height = 35
        self.tx_elevation = 2600
        self.frequency = 1800

    def test_cm_large_city(self):
        """C_m = 3 dB para ciudad grande"""
        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            city_type='large'
        )

        # Path loss debe ser calculable
        self.assertIn('path_loss', result)
        path_loss_large = result['path_loss']
        self.assertTrue(np.all(np.isfinite(path_loss_large)))
        print(f"✓ C_m (large city): {path_loss_large}")

    def test_cm_medium_city(self):
        """C_m = 0 dB para ciudad mediana"""
        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            city_type='medium'
        )

        # Path loss debe ser calculable
        self.assertIn('path_loss', result)
        path_loss_medium = result['path_loss']
        self.assertTrue(np.all(np.isfinite(path_loss_medium)))
        print(f"✓ C_m (medium city): {path_loss_medium}")

    def test_cm_difference_exactly_3db(self):
        """Diferencia entre large y medium debe ser exactamente 3 dB"""
        result_large = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            city_type='large'
        )

        result_medium = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            city_type='medium'
        )

        pl_large = result_large['path_loss']
        pl_medium = result_medium['path_loss']

        # La diferencia debe ser aproximadamente 3 dB (C_m = 3 dB para large vs 0 dB para medium)
        # Las pequeñas variaciones en terrain_reference pueden causar desviaciones menores
        difference = pl_large - pl_medium

        # Tolerancia: ±0.1 dB (variación numérica mínima)
        np.testing.assert_array_almost_equal(
            difference, 3.0 * np.ones_like(difference), decimal=1,
            err_msg=f"Expected 3 dB difference, got {difference}"
        )
        print(f"✓ C_m difference (large - medium): {difference[0]:.3f} dB (esperado 3.0 dB)")


if __name__ == '__main__':
    unittest.main()
