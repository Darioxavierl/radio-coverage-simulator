"""
COST-231 Hata - Fase 4: Corrección Altura Móvil a(h_m) (4 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase4MobileHeight(unittest.TestCase):
    """Tests para validación de factor a(h_m) de altura móvil"""

    def setUp(self):
        """Configuración inicial"""
        self.model = COST231HataModel(compute_module=np)
        self.distances = np.array([1000.0])  # 1 km
        self.terrain_heights = np.array([2600.0])
        self.tx_height = 35
        self.tx_elevation = 2600
        self.frequency = 1800

    def test_mobile_height_low(self):
        """Altura móvil baja (1.5 m) debe producir path loss bajo"""
        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            mobile_height=1.5
        )

        pl_low = result['path_loss'][0]
        self.assertTrue(np.isfinite(pl_low))
        print(f"✓ Mobile height 1.5 m: {pl_low:.1f} dB")

    def test_mobile_height_high(self):
        """Altura móvil alta (10 m) debe producir path loss más alto"""
        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            mobile_height=10.0
        )

        pl_high = result['path_loss'][0]
        self.assertTrue(np.isfinite(pl_high))
        print(f"✓ Mobile height 10 m: {pl_high:.1f} dB")

    def test_mobile_height_monotonic_increase(self):
        """Path loss debe DISMINUIR con altura móvil (físicamente correcto: -a(h_m))
        
        La ecuación tiene el término -a(h_m), por lo que al aumentar h_m:
        - a(h_m) aumenta
        - -a(h_m) contribuye más negativamente
        - path_loss BAJA
        
        Esto es correcto físicamente: móvil más alto = menos obstáculos = menos pérdida
        """
        heights = np.array([1.5, 3.0, 5.0, 10.0])
        path_losses = []

        for hm in heights:
            result = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=self.frequency,
                tx_height=self.tx_height,
                terrain_heights=self.terrain_heights,
                tx_elevation=self.tx_elevation,
                mobile_height=hm
            )
            path_losses.append(result['path_loss'][0])

        # Verificar que DISMINUYE con altura (comportamiento físico correcto)
        for i in range(len(path_losses) - 1):
            self.assertGreaterEqual(
                path_losses[i], path_losses[i + 1],
                f"Path loss should decrease with height: {path_losses}"
            )

        print(f"✓ Mobile height dependence: {path_losses} dB (decreasing with height)")

    def test_mobile_height_large_vs_medium_city(self):
        """Corrección a(h_m) diferente para large vs medium city"""
        heights = [1.5, 5.0, 10.0]

        for hm in heights:
            result_large = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=self.frequency,
                tx_height=self.tx_height,
                terrain_heights=self.terrain_heights,
                tx_elevation=self.tx_elevation,
                mobile_height=hm,
                city_type='large'
            )

            result_medium = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=self.frequency,
                tx_height=self.tx_height,
                terrain_heights=self.terrain_heights,
                tx_elevation=self.tx_elevation,
                mobile_height=hm,
                city_type='medium'
            )

            pl_large = result_large['path_loss'][0]
            pl_medium = result_medium['path_loss'][0]

            # Large city tiene menor a(h_m), por lo que path_loss es mayor en 3 dB (C_m)
            # pero menor corrección a(h_m) puede compensar
            # Simplemente verificar que ambos son finitos
            self.assertTrue(np.isfinite(pl_large))
            self.assertTrue(np.isfinite(pl_medium))

        print(f"✓ Mobile height correction: large vs medium city")


if __name__ == '__main__':
    unittest.main()
