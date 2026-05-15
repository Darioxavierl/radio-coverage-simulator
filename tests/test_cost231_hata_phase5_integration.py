"""
COST-231 Hata - Fase 5: Integración (vectorización, terrain, Dict return) (5 tests)
"""

import unittest
import numpy as np
from src.core.models.traditional.cost231_hata import COST231HataModel


class TestCOST231HataPhase5Integration(unittest.TestCase):
    """Tests para validación de vectorización, terrain integration, y Dict return"""

    def setUp(self):
        """Configuración inicial"""
        self.model = COST231HataModel(compute_module=np)

    def test_vectorized_multiple_receptors(self):
        """Cálculo vectorizado con múltiples receptores"""
        n_receptors = 100
        distances = np.random.uniform(100, 5000, n_receptors)  # 100m - 5km
        terrain_heights = np.full(n_receptors, 2600.0)

        result = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=terrain_heights,
            tx_elevation=2600
        )

        # Debe retornar arrays con mismo shape
        self.assertEqual(result['path_loss'].shape, (n_receptors,))
        self.assertEqual(result['validity_mask'].shape, (n_receptors,))
        self.assertEqual(result['hb_effective'].shape, (n_receptors,))
        self.assertIsInstance(result['valid_count'], (int, np.integer))

        # Todos los path_loss deben ser finitos
        self.assertTrue(np.all(np.isfinite(result['path_loss'])))
        print(f"✓ Vectorized {n_receptors} receptors: all finite")

    def test_return_dict_structure(self):
        """Estructura del diccionario retornado debe ser correcta"""
        distances = np.array([1000, 2000, 3000])
        terrain_heights = np.full_like(distances, 2600.0, dtype=float)

        result = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=terrain_heights,
            tx_elevation=2600
        )

        # Verificar claves requeridas
        required_keys = ['path_loss', 'hb_effective', 'validity_mask', 'valid_count']
        for key in required_keys:
            self.assertIn(key, result, f"Key '{key}' missing from result")

        # Verificar tipos
        self.assertIsInstance(result['path_loss'], np.ndarray)
        self.assertIsInstance(result['hb_effective'], np.ndarray)
        self.assertIsInstance(result['validity_mask'], np.ndarray)
        self.assertIsInstance(result['valid_count'], (int, np.integer))

        print(f"✓ Return dict structure correct: {list(result.keys())}")

    def test_terrain_profiles_integration(self):
        """Integración con terrain_profiles para altura efectiva"""
        n_receptors = 10
        n_samples = 50

        distances = np.full(n_receptors, 2000.0)  # 2 km
        terrain_heights = np.full(n_receptors, 2600.0)

        # Crear perfiles de terreno sintetizados (varían con distancia)
        terrain_profiles = np.zeros((n_receptors, n_samples))
        for i in range(n_receptors):
            # Cada perfil es una rampa del terreno TX a punto receptor
            h_start = 2600
            h_end = 2600 + np.random.uniform(-100, 100)  # variación aleatoria
            terrain_profiles[i, :] = np.linspace(h_start, h_end, n_samples)

        result = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=terrain_heights,
            tx_elevation=2600,
            terrain_profiles=terrain_profiles
        )

        # hb_effective debe ser calculado desde terrain_profiles
        self.assertIn('hb_effective', result)
        self.assertEqual(result['hb_effective'].shape, (n_receptors,))
        self.assertTrue(np.all(np.isfinite(result['hb_effective'])))

        print(f"✓ Terrain profiles integration: hb_eff={result['hb_effective'][:3]}")

    def test_validity_mask_consistency(self):
        """Máscara de validez debe ser consistente con parámetros"""
        # Rango válido COST-231 Hata: 0.02-5 km (20m-5000m)
        distances = np.array([10, 50, 500, 1000, 5000, 10000, 50000])  # Desde 10m hasta 50km
        terrain_heights = np.full_like(distances, 2600.0, dtype=float)

        result = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=terrain_heights,
            tx_elevation=2600
        )

        validity = result['validity_mask']
        valid_count = result['valid_count']

        # Verificar que valid_count = cantidad de True en validity_mask
        self.assertEqual(valid_count, np.sum(validity))

        # Receptores muy cercanos (<20m) NO deben ser válidos
        self.assertFalse(validity[0], "10m should be too close (<20m)")

        # Receptores en rango válido (50m, 500m, 1km, 5km) DEBEN ser válidos
        self.assertTrue(validity[1], "50m should be valid")
        self.assertTrue(validity[2], "500m should be valid")
        self.assertTrue(validity[3], "1km should be valid")
        self.assertTrue(validity[4], "5km should be valid")

        # Receptores muy lejanos (>5km) NO deben ser válidos
        self.assertFalse(validity[5], "10km should be too far (>5km)")
        self.assertFalse(validity[6], "50km should be too far (>5km)")

        print(f"✓ Validity mask: {valid_count}/{len(validity)} receptors valid")

    def test_large_scale_vectorization_performance(self):
        """Performance con muchos receptores debe ser razonable"""
        import time

        n_receptors = 5000
        distances = np.random.uniform(100, 5000, n_receptors)
        terrain_heights = np.full(n_receptors, 2600.0)

        start_time = time.time()
        result = self.model.calculate_path_loss(
            distances=distances,
            frequency=1800,
            tx_height=35,
            terrain_heights=terrain_heights,
            tx_elevation=2600
        )
        elapsed = time.time() - start_time

        # Debe completarse en < 1 segundo (vectorización eficiente)
        self.assertLess(elapsed, 1.0, f"Computation took {elapsed:.3f}s for {n_receptors} receptors")
        print(f"✓ Performance: {n_receptors} receptors in {elapsed*1000:.1f} ms")


if __name__ == '__main__':
    unittest.main()
