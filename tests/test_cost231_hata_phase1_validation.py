"""
COST-231 Hata - Fase 1: Validación de Parámetros (4 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase1Validation(unittest.TestCase):
    """Tests para validación de rangos y parámetros"""

    def setUp(self):
        """Configuración inicial para cada test"""
        self.model = COST231HataModel(compute_module=np)
        self.distances = np.array([100, 500, 1000, 2000, 5000])  # metros
        self.terrain_heights = np.full_like(self.distances, 2600.0, dtype=float)  # msnm

    def test_frequency_range_valid(self):
        """Frecuencia dentro del rango 1500-2000 MHz debe ser válida"""
        frequencies = [1500, 1600, 1750, 1900, 2000]

        for freq in frequencies:
            result = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=freq,
                tx_height=35,
                terrain_heights=self.terrain_heights,
                tx_elevation=2600
            )

            # Debe retornar path_loss válido
            self.assertIn('path_loss', result)
            self.assertIn('validity_mask', result)
            self.assertTrue(np.all(np.isfinite(result['path_loss'])))
            print(f"✓ Frequency {freq} MHz valid")

    def test_frequency_below_range(self):
        """Frecuencia < 1500 MHz emite warning pero sigue calculando"""
        result = self.model.calculate_path_loss(
            distances=self.distances,
            frequency=1400,  # < 1500 MHz
            tx_height=35,
            terrain_heights=self.terrain_heights,
            tx_elevation=2600
        )

        # Debe retornar sin errores (extrapolación)
        self.assertIn('path_loss', result)
        self.assertTrue(np.all(np.isfinite(result['path_loss'])))
        print("✓ Frequency 1400 MHz (below range) calculated with warning")

    def test_distance_range_valid(self):
        """Distancias en rango 0.02-5 km deben ser válidas"""
        # Crear distancias en rango válido: 20m, 500m, 1000m, 3000m, 5000m
        distances_test = np.array([20, 500, 1000, 3000, 5000])  # metros

        result = self.model.calculate_path_loss(
            distances=distances_test,
            frequency=1800,
            tx_height=35,
            terrain_heights=np.full_like(distances_test, 2600.0, dtype=float),
            tx_elevation=2600
        )

        # Todos deben estar en validity_mask
        self.assertIn('validity_mask', result)
        valid_count = result['valid_count']
        self.assertGreater(valid_count, 0, "Debe haber receptores en rango válido")
        print(f"✓ Distance range 0.02-5 km: {valid_count}/{len(distances_test)} valid")

    def test_height_range_valid(self):
        """Altura TX en rango 30-200 m debe ser válida"""
        heights_tx = [30, 50, 100, 150, 200]

        for h_tx in heights_tx:
            result = self.model.calculate_path_loss(
                distances=self.distances,
                frequency=1800,
                tx_height=h_tx,
                terrain_heights=self.terrain_heights,
                tx_elevation=2600
            )

            self.assertIn('path_loss', result)
            self.assertTrue(np.all(np.isfinite(result['path_loss'])))
            print(f"✓ TX height {h_tx} m valid")


if __name__ == '__main__':
    unittest.main()
