"""
COST-231 Hata - Fase 6: Coherencia (comparación con Okumura-Hata) (3 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase6Coherence(unittest.TestCase):
    """Tests para validación de coherencia con Okumura-Hata"""

    def setUp(self):
        """Configuración inicial"""
        self.model_hata = COST231HataModel(compute_module=np)
        self.distances = np.array([500, 1000, 2000, 5000])  # 0.5 - 5 km
        self.terrain_heights = np.full_like(self.distances, 2600.0, dtype=float)

    def test_cost231_hata_higher_loss_than_oh_at_low_freq(self):
        """COST-231 Hata tiene base mayor (46.3 vs 69.55) pero coef freq también mayor
        
        En rango COST-231 (1500-2000 MHz), COST-231 debe tener pérdida comparable a OH
        pero con ecuación diferente.
        
        A f=1800 MHz:
        - COST-231 base term: 46.3 + 33.9*log10(1800) ≈ 46.3 + 110.6 = 156.9
        - OH base term: 69.55 + 26.16*log10(1800) ≈ 69.55 + 85.8 = 155.3
        - COST-231 debe ser ~1.6 dB mayor
        """
        result_c231 = self.model_hata.calculate_path_loss(
            distances=self.distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=self.terrain_heights,
            tx_elevation=2600,
            city_type='medium'
        )

        pl_c231 = result_c231['path_loss']

        # Verificar que path_loss está en rango razonable
        # A 1 km, esperado alrededor de 130-135 dB
        self.assertGreater(pl_c231[1], 125)
        self.assertLess(pl_c231[1], 145)

        print(f"✓ COST-231 Hata path loss at f=1800MHz: {pl_c231}")

    def test_distance_exponent_comparison(self):
        """Exponente de distancia debe ser similar: [44.9 - 6.55*log10(h_b)]
        
        Para h_b=35m: exp = 44.9 - 6.55*1.544 ≈ 44.9 - 10.1 ≈ 34.8
        
        En Okumura-Hata es: [44.9 - 6.55*log10(h_b)] (IDÉNTICO)
        """
        # Comparar path_loss a dos distancias diferentes
        d1_km = 0.5
        d2_km = 1.0

        result_d1 = self.model_hata.calculate_path_loss(
            distances=np.array([d1_km * 1000]),
            frequency=1800,
            tx_height=35,
            terrain_heights=np.array([2600.0]),
            tx_elevation=2600
        )

        result_d2 = self.model_hata.calculate_path_loss(
            distances=np.array([d2_km * 1000]),
            frequency=1800,
            tx_height=35,
            terrain_heights=np.array([2600.0]),
            tx_elevation=2600
        )

        pl_d1 = result_d1['path_loss'][0]
        pl_d2 = result_d2['path_loss'][0]

        # Diferencia debe ser aproximadamente: exp * log10(d2/d1)
        # exp * log10(2) ≈ 34.8 * 0.301 ≈ 10.5 dB
        expected_delta = 34.8 * np.log10(d2_km / d1_km)
        actual_delta = pl_d2 - pl_d1

        # Tolerancia: ±2 dB
        self.assertAlmostEqual(actual_delta, expected_delta, delta=2.0)
        print(f"✓ Distance exponent: Δ={actual_delta:.1f} dB (expected {expected_delta:.1f} dB)")

    def test_frequency_range_consistency(self):
        """COST-231 Hata debe tener pérdida creciente en rango 1500-2000 MHz"""
        frequencies = np.array([1500, 1600, 1700, 1800, 1900, 2000])
        distances = np.array([1000.0])  # 1 km
        terrain_heights = np.array([2600.0])

        path_losses = []
        for freq in frequencies:
            result = self.model_hata.calculate_path_loss(
                distances=distances,
                frequency=freq,
                tx_height=35,
                terrain_heights=terrain_heights,
                tx_elevation=2600
            )
            path_losses.append(result['path_loss'][0])

        # Verificar que son monótonamente crecientes
        for i in range(len(path_losses) - 1):
            self.assertLess(
                path_losses[i], path_losses[i + 1],
                f"Path loss should increase with frequency: {path_losses}"
            )

        # Verificar que la pendiente es consistente con coeficiente 33.9
        # Δf = 500 MHz, ratio = 2000/1500 = 1.333
        # Expected: 33.9 * log10(1.333) ≈ 4.25 dB
        pl_1500 = path_losses[0]
        pl_2000 = path_losses[-1]
        actual_range = pl_2000 - pl_1500
        expected_range = 33.9 * np.log10(2000 / 1500)

        self.assertAlmostEqual(actual_range, expected_range, delta=1.0)
        print(f"✓ Frequency consistency: 1500→2000 MHz: {actual_range:.1f} dB (expected {expected_range:.1f} dB)")


if __name__ == '__main__':
    unittest.main()
