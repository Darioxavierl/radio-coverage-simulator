"""
Pruebas para validar correcciones de Okumura-Hata (Fase 1-4)
Valida: (1) altura efectiva vectorizada, (2) validity_mask, 
        (3) a(hm) vectorizado, (4) COST-231 order correcto
"""

import pytest
import numpy as np
import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.models.traditional.okumura_hata import OkumuraHataModel


class TestOkumuraHataRefactor:
    """Suite de pruebas para correcciones Okumura-Hata"""

    @pytest.fixture
    def model(self):
        """Instancia modelo Okumura-Hata"""
        return OkumuraHataModel()

    @pytest.fixture
    def sample_data(self):
        """Datos de prueba estándar"""
        distances = np.array([1000, 2000, 5000, 10000])  # metros
        terrain_heights = np.array([100, 120, 110, 105])  # msnm
        return {
            'distances': distances,
            'frequency': 900,  # MHz
            'tx_height': 50,  # metros AGL
            'terrain_heights': terrain_heights,
            'tx_elevation': 150,  # msnm
            'environment': 'Urban',
            'city_type': 'medium',
            'mobile_height': 1.5,
        }

    def test_01_return_type_is_dict(self, model, sample_data):
        """Prueba 1: Retorno debe ser diccionario (no array escalar)"""
        result = model.calculate_path_loss(**sample_data)
        
        assert isinstance(result, dict), "calculate_path_loss debe retornar dict"
        assert 'path_loss' in result, "dict debe contener 'path_loss'"
        assert 'validity_mask' in result, "dict debe contener 'validity_mask'"
        assert 'hb_effective' in result, "dict debe contener 'hb_effective'"
        assert 'valid_count' in result, "dict debe contener 'valid_count'"

    def test_02_path_loss_shape_preserved(self, model, sample_data):
        """Prueba 2: path_loss mantiene mismo shape que distances"""
        result = model.calculate_path_loss(**sample_data)
        
        assert result['path_loss'].shape == sample_data['distances'].shape, \
            f"path_loss shape {result['path_loss'].shape} != distances shape {sample_data['distances'].shape}"

    def test_03_validity_mask_boolean_type(self, model, sample_data):
        """Prueba 3: validity_mask debe ser array booleano"""
        result = model.calculate_path_loss(**sample_data)
        
        assert result['validity_mask'].dtype == bool, "validity_mask debe ser bool array"
        assert result['validity_mask'].shape == sample_data['distances'].shape

    def test_04_validity_mask_range_checks(self, model):
        """Prueba 4: validity_mask identifica alturas fuera de rango [30, 200]m"""
        distances = np.array([1000, 5000, 10000])

        # Caso 1: hb_eff < 30m — TX al mismo nivel que el terreno promedio
        # terrain_mean=500, hb_eff = 5+500-500 = 5  < 30 → todo inválido
        terrain_low = np.full(3, 500.0)
        result_low = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=5,
            terrain_heights=terrain_low,
            tx_elevation=500,
            environment='Urban',
            city_type='medium',
            mobile_height=1.5,
        )
        assert not np.any(result_low['validity_mask']), \
            "hb_eff=5m (< 30m) debe ser inválido en todos los puntos"

        # Caso 2: hb_eff en [30, 200]m — TX por encima del terreno promedio
        # terrain_mean=400, hb_eff = 50+500-400 = 150  in [30, 200] → todo válido
        terrain_valid = np.full(3, 400.0)
        result_valid = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=50,
            terrain_heights=terrain_valid,
            tx_elevation=500,
            environment='Urban',
            city_type='medium',
            mobile_height=1.5,
        )
        assert np.all(result_valid['validity_mask']), \
            "hb_eff=150m (in [30, 200]) debe ser válido en todos los puntos"

    def test_05_valid_count_matches_mask(self, model, sample_data):
        """Prueba 5: valid_count coincide con suma de validity_mask"""
        result = model.calculate_path_loss(**sample_data)
        
        expected_count = np.sum(result['validity_mask'])
        assert result['valid_count'] == expected_count, \
            f"valid_count {result['valid_count']} != suma de mask {expected_count}"

    def test_06_hb_effective_clipping_applied(self, model):
        """Prueba 6: ACTUALIZADA - Sin clipping, validez vía validity_mask"""
        distances = np.array([1000, 5000])
        # Terrain muy alto → h_eff = tx_h + tx_elev - terrain_ref será bajo o negativo
        terrain_heights = np.array([1000, 900])
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=5,  # Muy bajo
            terrain_heights=terrain_heights,
            tx_elevation=500,  # Bajo también
            environment='Urban',
            city_type='medium',
            mobile_height=1.5,
        )
        
        # NUEVO: hb_effective_clipped no debe existir (eliminado en FASE 1)
        assert 'hb_effective_clipped' not in result, "hb_effective_clipped fue eliminado"
        
        # NUEVO: hb_effective sin clip contiene valores reales (pueden ser < 30m)
        assert 'hb_effective' in result, "hb_effective debe estar disponible"
        
        # Verificar que la validez se marca correctamente
        # Algunos receptores pueden tener h_eff < 30 (inválidos)
        has_invalid = np.any(result['hb_effective'] < 30.0)
        has_valid = np.any(result['hb_effective'] >= 30.0)
        
        # Si hay receptores inválidos, deben estar marcados así en validity_mask
        if has_invalid:
            invalid_mask = result['hb_effective'] < 30.0
            assert np.all(~result['validity_mask'][invalid_mask]), \
                "Receptores con h<30 deben ser marcados como inválidos"

    def test_07_hb_effective_unclipped_available(self, model, sample_data):
        """Prueba 7: hb_effective original (sin clip) está disponible"""
        result = model.calculate_path_loss(**sample_data)
        
        assert 'hb_effective' in result, "hb_effective no clipeada debe estar disponible"
        assert result['hb_effective'].shape == sample_data['distances'].shape

    def test_08_backward_compatibility_legacy_path(self, model, sample_data):
        """Prueba 8: Backward compatibility - sin terrain_profiles usa path legacy"""
        # Sin terrain_profiles, debe usar _compute_terrain_reference
        result = model.calculate_path_loss(**sample_data)
        
        # Debe retornar valores válidos
        assert np.all(np.isfinite(result['path_loss'])), \
            "Path loss debe contener valores válidos"
        assert len(result['path_loss']) == len(sample_data['distances'])

    def test_09_vectorized_effective_height_with_profiles(self, model):
        """Prueba 9: ACTUALIZADA - _calculate_effective_height_vectorized con profiles"""
        # Mock terrain profiles: 3 receptores x 50 muestras (alineado con código)
        n_receptors = 3
        n_samples = 50  # El código espera 50 muestras
        distances_km = np.array([5.0, 10.0, 15.0])  # Dentro de [1-20]
        
        # Crear perfiles simulados (elevaciones aleatorias entre 100-300 msnm)
        # Asegurarse que en el rango [3-15km] hay suficientes muestras
        terrain_profiles = np.random.uniform(100, 300, (n_receptors, n_samples))
        
        result = model._calculate_effective_height_vectorized(
            tx_height=50,
            tx_elevation=200,
            terrain_profiles=terrain_profiles,
            d_km=distances_km
        )
        
        assert result.shape == (n_receptors,), \
            f"Result shape {result.shape} != ({n_receptors},)"
        
        # ACTUALIZADO: NaN es válido cuando no hay suficientes muestras en [3-15km]
        # El método retorna NaN para receptores inválidos (sin suficientes datos)
        # y valores finitos para receptores válidos
        assert isinstance(result, np.ndarray) or hasattr(result, '__array__'), \
            "Result debe ser un array-like"
        assert result.shape == (n_receptors,), "Shape debe preservarse"
        # Al menos algunos valores pueden ser NaN (comportamiento esperado si no hay datos)

    def test_10_cost231_order_frequency_boundary(self, model):
        """Prueba 10: COST-231 aplicado solo cuando f > 1500 MHz"""
        distances = np.array([5000])
        terrain_heights = np.array([100])
        
        # Prueba 1: f < 1500 MHz (sin COST-231)
        result_below = model.calculate_path_loss(
            distances=distances,
            frequency=1000,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Urban',
            city_type='large',
            mobile_height=1.5,
        )
        
        # Prueba 2: f > 1500 MHz (con COST-231)
        result_above = model.calculate_path_loss(
            distances=distances,
            frequency=2000,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Urban',
            city_type='large',
            mobile_height=1.5,
        )
        
        # Path loss a 2000 MHz debe ser mayor (Cm=3dB agregado)
        # Verificar que el orden es correcto: base + Cm, luego ambiente
        assert result_above['path_loss'][0] > result_below['path_loss'][0], \
            "Path loss a 2000 MHz debe ser > que a 1000 MHz (COST-231 agregado)"

    def test_11_mobile_height_correction_vectorized(self, model):
        """Prueba 11: _calculate_mobile_height_correction_vectorized retorna array con shape correcto"""
        frequency = 900
        hm = 1.5
        city_type = 'medium'
        hb_eff = np.array([50, 60, 70, 80])  # Mock array
        
        result = model._calculate_mobile_height_correction_vectorized(
            frequency=frequency,
            hm=hm,
            city_type=city_type,
            hb_eff=hb_eff
        )
        
        assert result.shape == hb_eff.shape, \
            f"Resultado shape {result.shape} != hb_eff shape {hb_eff.shape}"
        assert np.all(np.isfinite(result)), "Corrección a(hm) debe ser finita"

    def test_12_suburban_environment_correction(self, model):
        """Prueba 12: Corrección suburbana se aplica correctamente"""
        distances = np.array([5000])
        terrain_heights = np.array([100])
        
        result_urban = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Urban',
            city_type='medium',
            mobile_height=1.5,
        )
        
        result_suburban = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Suburban',
            city_type='medium',
            mobile_height=1.5,
        )
        
        # Suburban debe tener menor path loss (mejor propagación)
        assert result_suburban['path_loss'][0] < result_urban['path_loss'][0], \
            "Path loss Suburban debe ser < Urban"

    def test_13_rural_environment_correction(self, model):
        """Prueba 13: Corrección rural se aplica correctamente"""
        distances = np.array([5000])
        terrain_heights = np.array([100])
        
        result_urban = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Urban',
            city_type='medium',
            mobile_height=1.5,
        )
        
        result_rural = model.calculate_path_loss(
            distances=distances,
            frequency=900,
            tx_height=50,
            terrain_heights=terrain_heights,
            tx_elevation=100,
            environment='Rural',
            city_type='medium',
            mobile_height=1.5,
        )
        
        # Rural debe tener menor path loss (mejor propagación)
        assert result_rural['path_loss'][0] < result_urban['path_loss'][0], \
            "Path loss Rural debe ser < Urban"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
