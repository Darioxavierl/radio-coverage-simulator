"""
Tests exhaustivos para modelo Okumura-Hata completo

Valida:
- Cálculo correcto de path loss
- Uso de elevaciones del terreno (altura efectiva)
- Correcciones por ambiente (Urban/Suburban/Rural)
- Correcciones por tipo de ciudad (Large/Medium)
- Factor de corrección móvil a(hm)
- Extensión COST-231 para >1500 MHz
- Consistencia CPU/GPU
- Validación de rangos
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from core.models.traditional.okumura_hata import OkumuraHataModel


class TestOkumuraHataInitialization(unittest.TestCase):
    """Tests de inicialización del modelo"""

    def test_initialization_default(self):
        """Verifica inicialización con valores por defecto"""
        model = OkumuraHataModel()
        self.assertIsNotNone(model)
        self.assertEqual(model.name, "Okumura-Hata")
        self.assertEqual(model.mobile_height, 1.5)
        self.assertEqual(model.environment, 'Urban')
        self.assertEqual(model.city_type, 'medium')
        self.assertIsNotNone(model.xp)

    def test_initialization_with_config(self):
        """Verifica inicialización con configuración personalizada"""
        config = {
            'mobile_height': 2.0,
            'environment': 'Suburban',
            'city_type': 'large'
        }
        model = OkumuraHataModel(config=config)
        self.assertEqual(model.mobile_height, 2.0)
        self.assertEqual(model.environment, 'Suburban')
        self.assertEqual(model.city_type, 'large')

    def test_initialization_with_cupy(self):
        """Verifica inicialización con CuPy (GPU)"""
        try:
            import cupy as cp
            model = OkumuraHataModel(compute_module=cp)
            self.assertTrue(model.xp.__name__ == 'cupy')
        except ImportError:
            self.skipTest("CuPy not available")


class TestOkumuraHataBasicCalculation(unittest.TestCase):
    """Tests de cálculo básico"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()

    def test_basic_path_loss_calculation(self):
        """Verifica cálculo básico de path loss"""
        distances = np.array([1000, 2000, 5000, 10000])  # metros
        frequency = 900  # MHz
        tx_height = 50  # metros
        terrain_heights = np.zeros(len(distances))  # terreno plano

        path_loss = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )['path_loss']

        # Verificar shape
        self.assertEqual(path_loss.shape, distances.shape)

        # Path loss debe aumentar con la distancia
        self.assertTrue(np.all(path_loss[1:] > path_loss[:-1]))

        # Valores razonables para Okumura-Hata urbano
        # A 1 km: ~130 dB, a 10 km: ~160 dB
        self.assertTrue(np.all(path_loss > 100))
        self.assertTrue(np.all(path_loss < 180))

    def test_path_loss_increases_with_distance(self):
        """Verifica que path loss aumenta monotónicamente con distancia"""
        distances = np.linspace(1000, 20000, 20)  # 1 a 20 km
        frequency = 1800
        tx_height = 40
        terrain_heights = np.zeros(len(distances))

        path_loss = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )['path_loss']

        # Verificar monotonía creciente
        differences = np.diff(path_loss)
        self.assertTrue(np.all(differences > 0))

    def test_path_loss_increases_with_frequency(self):
        """Verifica que path loss aumenta con frecuencia"""
        distance = 5000  # 5 km
        frequencies = [900, 1800, 2100]  # MHz
        tx_height = 40
        terrain_heights = np.array([0.0])

        path_losses = []
        for freq in frequencies:
            pl = self.model.calculate_path_loss(
                np.array([distance]), freq, tx_height, terrain_heights
            )['path_loss']
            path_losses.append(pl[0])

        # Path loss debe aumentar con frecuencia
        self.assertTrue(path_losses[1] > path_losses[0])
        self.assertTrue(path_losses[2] > path_losses[1])


class TestOkumuraHataTerrainHandling(unittest.TestCase):
    """Tests de manejo de elevaciones del terreno"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()

    def test_with_flat_terrain(self):
        """Verifica cálculo con terreno plano"""
        distances = np.array([5000])
        frequency = 1800
        tx_height = 40
        tx_elevation = 100  # TX a 100 msnm
        terrain_heights = np.array([100.0])  # terreno también a 100 msnm

        path_loss = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights,
            tx_elevation=tx_elevation
        )['path_loss']

        self.assertTrue(len(path_loss) == 1)
        self.assertTrue(100 < path_loss[0] < 180)

    def test_with_elevated_terrain(self):
        """Verifica que elevación del terreno afecta altura efectiva"""
        distances = np.array([5000, 5000])
        frequency = 1800
        tx_height = 40

        # Caso 1: TX y terreno a misma altura
        tx_elevation_1 = 100
        terrain_heights_1 = np.array([100.0, 100.0])
        pl_1 = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights_1,
            tx_elevation=tx_elevation_1
        )['path_loss']

        # Caso 2: TX más alto que terreno (mayor altura efectiva)
        tx_elevation_2 = 200
        terrain_heights_2 = np.array([100.0, 100.0])
        pl_2 = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights_2,
            tx_elevation=tx_elevation_2
        )['path_loss']

        # Mayor altura efectiva = menor path loss
        self.assertTrue(pl_2[0] < pl_1[0])

    def test_with_varying_terrain(self):
        """Verifica manejo de terreno variable"""
        distances = np.array([1000, 5000, 10000])
        frequency = 900
        tx_height = 50
        tx_elevation = 500  # TX a 500 msnm
        # Terreno variable pero promedio mantiene h_eff en rango [30, 200]
        # z_ref = mean([500, 500, 480]) = 493.33 → h_eff = 50 + 500 - 493.33 ≈ 56.67 (válido)
        terrain_heights = np.array([500.0, 500.0, 480.0])

        result = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights,
            tx_elevation=tx_elevation
        )
        path_loss = result['path_loss']
        validity_mask = result['validity_mask']

        # Debe calcular altura efectiva usando promedio del terreno
        self.assertEqual(len(path_loss), 3)
        # Receptores válidos deben tener path_loss > 100
        valid_pl = path_loss[validity_mask]
        if len(valid_pl) > 0:
            self.assertTrue(np.all(valid_pl > 100), "Path loss válido debe ser > 100")


class TestOkumuraHataTerrainReferenceMethods(unittest.TestCase):
    """Tests de métodos de referencia de terreno para h_b efectiva"""

    def test_global_mean_mode_matches_legacy_default(self):
        """El modo global_mean debe reproducir el comportamiento histórico"""
        distances = np.array([1000, 3000, 5000, 9000, 12000], dtype=float)
        terrain_heights = np.array([100, 130, 170, 210, 250], dtype=float)
        frequency = 900
        tx_height = 40
        tx_elevation = 380

        legacy = OkumuraHataModel()
        explicit_global = OkumuraHataModel(config={'terrain_reference_method': 'global_mean'})

        pl_legacy = legacy.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )['path_loss']

        pl_global = explicit_global.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )['path_loss']

        np.testing.assert_allclose(pl_legacy, pl_global, rtol=0.0, atol=1e-10)

    def test_local_annulus_mean_changes_path_loss_consistently(self):
        """local_annulus_mean debe modificar h_b efectiva respecto al promedio global"""
        # Todos los receptores en rango válido [1, 20] km
        distances = np.array([1200, 3200, 7000, 12000, 15000, 18000], dtype=float)
        terrain_heights = np.array([100, 100, 180, 250, 320, 380], dtype=float)
        frequency = 900
        tx_height = 40
        tx_elevation = 380

        model_global = OkumuraHataModel(config={'terrain_reference_method': 'global_mean'})
        model_local = OkumuraHataModel(config={
            'terrain_reference_method': 'local_annulus_mean',
            'terrain_reference_inner_km': 3.0,
            'terrain_reference_outer_km': 15.0,
            'terrain_min_samples': 1,
        })

        result_global = model_global.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )
        result_local = model_local.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )
        
        pl_global = result_global['path_loss']
        pl_local = result_local['path_loss']
        validity_global = result_global['validity_mask']
        validity_local = result_local['validity_mask']

        # El anillo local tiene elevación media mayor que global en este caso,
        # por tanto h_b efectiva baja y path loss debe aumentar.
        # Comparar solo receptores válidos en ambos modelos
        valid_both = validity_global & validity_local
        if np.any(valid_both):
            self.assertTrue(np.all(pl_local[valid_both] > pl_global[valid_both]))

    def test_local_annulus_fallback_to_global_when_no_samples(self):
        """Si no hay muestras suficientes en anillo, debe volver a global_mean"""
        distances = np.array([500, 1200, 2200, 2800], dtype=float)
        terrain_heights = np.array([100, 130, 150, 180], dtype=float)
        frequency = 900
        tx_height = 40
        tx_elevation = 300

        model_global = OkumuraHataModel(config={'terrain_reference_method': 'global_mean'})
        model_local = OkumuraHataModel(config={
            'terrain_reference_method': 'local_annulus_mean',
            'terrain_reference_inner_km': 10.0,
            'terrain_reference_outer_km': 15.0,
            'terrain_min_samples': 1,
        })

        pl_global = model_global.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )['path_loss']
        pl_local_fallback = model_local.calculate_path_loss(
            distances,
            frequency,
            tx_height,
            terrain_heights,
            tx_elevation=tx_elevation,
            environment='Urban'
        )['path_loss']

        np.testing.assert_allclose(pl_global, pl_local_fallback, rtol=0.0, atol=1e-10)


class TestOkumuraHataEnvironmentCorrections(unittest.TestCase):
    """Tests de correcciones por tipo de ambiente"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()
        self.distances = np.array([5000])  # 5 km
        self.frequency = 900
        self.tx_height = 40
        self.terrain_heights = np.zeros(1)

    def test_urban_environment(self):
        """Verifica cálculo en ambiente urbano"""
        pl = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Urban'
        )['path_loss']
        # Urbano es la referencia (sin corrección)
        self.assertTrue(len(pl) == 1)
        self.assertTrue(130 < pl[0] < 160)

    def test_suburban_environment(self):
        """Verifica corrección para ambiente suburbano"""
        pl_urban = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Urban'
        )['path_loss']

        pl_suburban = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Suburban'
        )['path_loss']

        # Suburban debe tener MENOR path loss que Urban
        self.assertTrue(pl_suburban[0] < pl_urban[0])

        # La diferencia debe ser razonable (típicamente 5-20 dB)
        diff = pl_urban[0] - pl_suburban[0]
        self.assertTrue(3 < diff < 25)

    def test_rural_environment(self):
        """Verifica corrección para ambiente rural"""
        pl_urban = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Urban'
        )['path_loss']

        pl_rural = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Rural'
        )['path_loss']

        # Rural debe tener MENOR path loss que Urban
        self.assertTrue(pl_rural[0] < pl_urban[0])

        # La diferencia debe ser significativa (típicamente 20-40 dB)
        diff = pl_urban[0] - pl_rural[0]
        self.assertTrue(15 < diff < 50)

    def test_environment_comparison(self):
        """Verifica orden: Rural < Suburban < Urban"""
        pl_urban = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Urban'
        )['path_loss'][0]

        pl_suburban = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Suburban'
        )['path_loss'][0]

        pl_rural = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, environment='Rural'
        )['path_loss'][0]

        # Verificar orden: menor path loss en Rural
        self.assertTrue(pl_rural < pl_suburban < pl_urban)


class TestOkumuraHataCityTypeCorrection(unittest.TestCase):
    """Tests de corrección por tipo de ciudad"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()
        self.distances = np.array([5000])
        self.frequency = 900
        self.tx_height = 40
        self.terrain_heights = np.zeros(1)

    def test_medium_city(self):
        """Verifica cálculo para ciudad mediana"""
        pl = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, city_type='medium'
        )['path_loss']
        self.assertTrue(130 < pl[0] < 160)

    def test_large_city(self):
        """Verifica cálculo para ciudad grande"""
        pl = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, city_type='large'
        )['path_loss']
        self.assertTrue(130 < pl[0] < 160)

    def test_large_vs_medium_city(self):
        """Compara path loss entre ciudad grande y mediana"""
        pl_medium = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, city_type='medium'
        )['path_loss'][0]

        pl_large = self.model.calculate_path_loss(
            self.distances, self.frequency, self.tx_height,
            self.terrain_heights, city_type='large'
        )['path_loss'][0]

        # La diferencia debe existir pero ser pequeña (~1-3 dB)
        diff = abs(pl_large - pl_medium)
        self.assertTrue(diff < 5)


class TestOkumuraHataCOST231Extension(unittest.TestCase):
    """Tests de extensión COST-231 para frecuencias >1500 MHz"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()
        self.distances = np.array([5000])
        self.tx_height = 40
        self.terrain_heights = np.zeros(1)

    def test_cost231_extension_applied(self):
        """Verifica que COST-231 se aplica para f>1500 MHz"""
        # Frecuencia en rango básico
        pl_1800 = self.model.calculate_path_loss(
            self.distances, 1800, self.tx_height, self.terrain_heights,
            environment='Urban', city_type='large'
        )['path_loss'][0]

        pl_1400 = self.model.calculate_path_loss(
            self.distances, 1400, self.tx_height, self.terrain_heights,
            environment='Urban', city_type='large'
        )['path_loss'][0]

        # 1800 MHz debe tener mayor path loss que 1400 MHz
        self.assertTrue(pl_1800 > pl_1400)

    def test_cost231_Cm_factor(self):
        """Verifica factor Cm de COST-231"""
        frequency = 1800  # > 1500 MHz

        # Cm = 3 dB para ciudad grande
        pl_large = self.model.calculate_path_loss(
            self.distances, frequency, self.tx_height, self.terrain_heights,
            environment='Urban', city_type='large'
        )['path_loss'][0]

        # Cm = 0 dB para ciudad mediana
        pl_medium = self.model.calculate_path_loss(
            self.distances, frequency, self.tx_height, self.terrain_heights,
            environment='Urban', city_type='medium'
        )['path_loss'][0]

        # La diferencia debe ser aproximadamente 3 dB
        diff = pl_large - pl_medium
        self.assertAlmostEqual(diff, 3.0, delta=0.5)


class TestOkumuraHataReferenceValues(unittest.TestCase):
    """Tests contra valores de referencia de la literatura"""

    def test_reference_case_1(self):
        """Test contra caso de referencia: 900 MHz, 5 km, urbano"""
        model = OkumuraHataModel()

        # Parámetros de referencia
        distance = 5000  # 5 km
        frequency = 900  # MHz
        hb = 50  # metros
        hm = 1.5  # metros
        terrain_heights = np.array([0.0])

        pl = model.calculate_path_loss(
            np.array([distance]), frequency, hb, terrain_heights,
            mobile_height=hm, environment='Urban', city_type='medium'
        )['path_loss'][0]

        # Valor esperado aproximado: ~140-148 dB (varía según implementación exacta)
        # Rango aceptable: 135-150 dB
        self.assertTrue(135 < pl < 150, f"Path loss {pl:.2f} dB fuera de rango esperado")

    def test_reference_case_2(self):
        """Test contra caso: 1800 MHz, 2 km, urbano"""
        model = OkumuraHataModel()

        distance = 2000  # 2 km
        frequency = 1800  # MHz
        hb = 40
        terrain_heights = np.array([0.0])

        pl = model.calculate_path_loss(
            np.array([distance]), frequency, hb, terrain_heights,
            environment='Urban'
        )['path_loss'][0]

        # Valor esperado aproximado: ~130-145 dB
        self.assertTrue(120 < pl < 145, f"Path loss {pl:.2f} dB fuera de rango esperado")


class TestOkumuraHataGPUConsistency(unittest.TestCase):
    """Tests de consistencia CPU vs GPU"""

    def test_cpu_gpu_consistency_basic(self):
        """Verifica que CPU y GPU dan mismos resultados"""
        try:
            import cupy as cp

            # Datos de prueba
            distances = np.array([1000, 2000, 5000, 10000])
            frequency = 1800
            tx_height = 40
            terrain_heights = np.array([0.0, 50.0, 100.0, 150.0])
            tx_elevation = 100.0

            # Modelo CPU
            model_cpu = OkumuraHataModel(compute_module=np)
            pl_cpu = model_cpu.calculate_path_loss(
                distances, frequency, tx_height, terrain_heights,
                tx_elevation=tx_elevation, environment='Urban'
            )['path_loss']

            # Modelo GPU
            model_gpu = OkumuraHataModel(compute_module=cp)
            distances_gpu = cp.array(distances)
            terrain_heights_gpu = cp.array(terrain_heights)

            pl_gpu = model_gpu.calculate_path_loss(
                distances_gpu, frequency, tx_height, terrain_heights_gpu,
                tx_elevation=tx_elevation, environment='Urban'
            )['path_loss']

            # Convertir GPU a CPU
            pl_gpu_cpu = cp.asnumpy(pl_gpu)

            # Verificar igualdad (tolerancia numérica)
            np.testing.assert_array_almost_equal(pl_cpu, pl_gpu_cpu, decimal=10)

            print(f"\n  CPU results: {pl_cpu}")
            print(f"  GPU results: {pl_gpu_cpu}")
            print(f"  Max difference: {np.max(np.abs(pl_cpu - pl_gpu_cpu)):.2e} dB")

        except ImportError:
            self.skipTest("CuPy not available")

    def test_cpu_gpu_consistency_environments(self):
        """Verifica consistencia CPU/GPU para todos los ambientes"""
        try:
            import cupy as cp

            distances = np.array([5000])
            frequency = 900
            tx_height = 50
            terrain_heights = np.array([0.0])

            for env in ['Urban', 'Suburban', 'Rural']:
                model_cpu = OkumuraHataModel(compute_module=np)
                model_gpu = OkumuraHataModel(compute_module=cp)

                pl_cpu = model_cpu.calculate_path_loss(
                    distances, frequency, tx_height, terrain_heights,
                    environment=env
                )['path_loss']

                pl_gpu = model_gpu.calculate_path_loss(
                    cp.array(distances), frequency, tx_height,
                    cp.array(terrain_heights), environment=env
                )['path_loss']

                pl_gpu_cpu = cp.asnumpy(pl_gpu)

                np.testing.assert_array_almost_equal(
                    pl_cpu, pl_gpu_cpu, decimal=10,
                    err_msg=f"Inconsistency for {env} environment"
                )

        except ImportError:
            self.skipTest("CuPy not available")


class TestOkumuraHataEdgeCases(unittest.TestCase):
    """Tests de casos extremos"""

    def setUp(self):
        """Setup antes de cada test"""
        self.model = OkumuraHataModel()

    def test_minimum_distance(self):
        """Verifica comportamiento en distancia mínima"""
        distances = np.array([1])  # 1 metro
        frequency = 900
        tx_height = 50
        terrain_heights = np.zeros(1)

        # No debe fallar
        pl = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )['path_loss']
        self.assertTrue(len(pl) == 1)

    def test_maximum_distance(self):
        """Verifica comportamiento en distancia máxima del rango"""
        distances = np.array([20000])  # 20 km
        frequency = 900
        tx_height = 50
        terrain_heights = np.zeros(1)

        pl = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )['path_loss']
        self.assertTrue(len(pl) == 1)
        self.assertTrue(150 < pl[0] < 180)

    def test_large_grid(self):
        """Verifica manejo de grid grande"""
        # Grid de 100x100 = 10,000 puntos
        distances = np.random.uniform(1000, 20000, 10000)
        frequency = 1800
        tx_height = 40
        terrain_heights = np.random.uniform(0, 200, 10000)

        result = self.model.calculate_path_loss(
            distances, frequency, tx_height, terrain_heights
        )
        pl = result['path_loss']

        self.assertEqual(len(pl), 10000)
        
        # ACTUALIZADO: Ahora usamos extrapolación profesional (como Atoll)
        # NO usamos NaN masking agresivo - receptores fuera de rango siguen calculándose
        # validity_mask es METADATO de confianza, no criterio de invalidación
        validity_mask = result['validity_mask']
        
        # Verificar que ALL receptores tienen valores finitos (extrapolación)
        self.assertTrue(np.all(np.isfinite(pl)), "Todos los path_loss deben ser finitos")
        
        # Receptores válidos deben estar en rango razonable
        valid_pl = pl[validity_mask]
        if len(valid_pl) > 0:
            self.assertTrue(np.all(valid_pl > 0), "Path loss válido debe ser > 0")
            self.assertTrue(np.all(valid_pl < 200), "Path loss válido debe ser < 200")
        
        # Receptores inválidos también tienen valores (extrapolados), no NaN
        invalid_pl = pl[~validity_mask]
        if len(invalid_pl) > 0:
            self.assertTrue(np.all(np.isfinite(invalid_pl)), "Path loss extrapolado debe ser finito")


class TestOkumuraHataModelInfo(unittest.TestCase):
    """Tests de información del modelo"""

    def test_get_model_info(self):
        """Verifica que retorna información correcta"""
        model = OkumuraHataModel()
        info = model.get_model_info()

        self.assertEqual(info['name'], 'Okumura-Hata')
        self.assertEqual(info['type'], 'Empírico')
        self.assertIn('Urban', info['environments'])
        self.assertIn('Suburban', info['environments'])
        self.assertIn('Rural', info['environments'])


if __name__ == '__main__':
    # Ejecutar tests con verbosity 2
    unittest.main(verbosity=2)
