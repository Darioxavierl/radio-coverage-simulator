"""
COST-231 Hata - Fase 2: Validación Ecuación Base (3 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase2EquationBase(unittest.TestCase):
    """Tests para validación de ecuación base vs Okumura-Hata"""

    def setUp(self):
        """Configuración inicial"""
        self.model = COST231HataModel(compute_module=np)
        # Caso simple: una distancia, elevación plana
        self.distances = np.array([1000.0])  # 1 km
        self.terrain_heights = np.array([2600.0])
        self.tx_height = 35  # metros AGL
        self.tx_elevation = 2600  # msnm
        self.frequency = 1800  # MHz

    def test_equation_coefficient_base(self):
        """Constante base COST-231 (46.3 dB) vs Okumura-Hata (69.55 dB)"""
        # L = 46.3 + 33.9·log₁₀(f) − 13.82·log₁₀(h_b) − a(h_m) + ...
        # COST-231 debe ser ~23 dB menor que Okumura-Hata en las mismas condiciones

        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=self.frequency,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation,
            city_type='medium'
        )

        path_loss = result['path_loss'][0]

        # Valor esperado aproximado: 46.3 + 33.9*log(1800) - 13.82*log(35) - a_hm + (44.9-6.55*log(35))*log(1)
        # log(1800) ≈ 3.255, log(35) ≈ 1.544, log(1) = 0
        # = 46.3 + 110.6 - 21.3 - a_hm + 0 = 135.6 - a_hm (a_hm ≈ 0-5 dB)
        # Esperado rango: 130-135 dB

        self.assertGreater(path_loss, 125, f"Path loss {path_loss} dB parece bajo")
        self.assertLess(path_loss, 145, f"Path loss {path_loss} dB parece alto")
        print(f"✓ Equation base: Path loss = {path_loss:.1f} dB (esperado ~130-135 dB)")

    def test_frequency_coefficient_difference(self):
        """Coeficiente frecuencia COST-231 (33.9) vs Okumura-Hata (26.16)"""
        # A mayor frecuencia, mayor pérdida. COST-231 tiene +7.74 dB más por octava en f

        f_low = 1500  # Inicio rango COST-231
        f_high = 2000  # Fin rango

        result_low = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=f_low,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation
        )

        result_high = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=f_high,
            tx_height=self.tx_height,
            terrain_heights=self.terrain_heights,
            tx_elevation=self.tx_elevation
        )

        pl_low = result_low['path_loss'][0]
        pl_high = result_high['path_loss'][0]
        difference = pl_high - pl_low

        # Δf = 500 MHz, ratio = 2000/1500 = 1.333
        # Expected: 33.9 * log10(1.333) ≈ 33.9 * 0.125 ≈ 4.25 dB
        # (La ecuación es lineal en log10(f), no en f absoluto)
        # Δf/f ≈ ratio, así que diferencia ≈ 33.9 * log10(2000/1500)

        expected_delta = 33.9 * np.log10(f_high / f_low)
        tolerance = 1.0  # ±1 dB de tolerancia

        self.assertAlmostEqual(
            difference, expected_delta, delta=tolerance,
            msg=f"Difference {difference:.1f} dB vs expected {expected_delta:.1f} dB"
        )
        print(f"✓ Frequency coefficient: f_low={pl_low:.1f} dB, f_high={pl_high:.1f} dB, diff={difference:.1f} dB")

    def test_distance_dependence(self):
        """Validar dependencia con distancia: 44.9 - 6.55*log(h_b) aplicado a log(d)"""
        distances = np.array([100.0, 1000.0, 5000.0])  # 0.1, 1, 5 km

        results = []
        for d in distances:
            result = self.model.calculate_path_loss(
                distances=np.array([d]),
                frequency=self.frequency,
                tx_height=self.tx_height,
                terrain_heights=np.array([self.terrain_heights[0]]),
                tx_elevation=self.tx_elevation
            )
            results.append(result['path_loss'][0])

        # Verificar que aumenta monótonamente con distancia
        for i in range(len(results) - 1):
            self.assertLess(
                results[i], results[i + 1],
                f"Path loss should increase with distance: {results}"
            )

        print(f"✓ Distance dependence: {results[0]:.1f}, {results[1]:.1f}, {results[2]:.1f} dB")


if __name__ == '__main__':
    unittest.main()
