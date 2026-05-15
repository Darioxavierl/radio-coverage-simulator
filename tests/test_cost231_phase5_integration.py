"""
Test Fase 5: Integración de parámetros COST-231

Valida que:
- Todas las correcciones funcionan juntas (Fases 1-4)
- Parámetros correctos fluyen a través de toda la cadena
- Return type es correcto (Dict con 'path_loss', 'validity_mask')
- Path Loss es coherente LOS < NLOS
- Resultados finales son físicamente razonables
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.cost231 import COST231WalfischIkegamiModel


class TestCOST231Phase5Integration:
    """Tests para FASE 5: Integración de todas las correcciones"""
    
    @pytest.fixture
    def model(self):
        return COST231WalfischIkegamiModel()
    
    def test_return_type_dict_with_metadata(self, model):
        """Test: return type es Dict con 'path_loss' y 'validity_mask'"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.full((n_receptors, n_samples), 2500.0)
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=30.0,
            terrain_heights=terrain_heights,
            tx_elevation=2500.0,
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        # Verificar que es diccionario con keys correctas
        assert isinstance(result, dict), f"Result no es dict: {type(result)}"
        assert 'path_loss' in result, "Result no tiene 'path_loss'"
        assert 'validity_mask' in result, "Result no tiene 'validity_mask'"
        
        # Verificar tipos de datos
        assert isinstance(result['path_loss'], (np.ndarray, float))
        assert isinstance(result['validity_mask'], (np.ndarray, bool))
        
        print(f"✓ Return type correcto: Dict con path_loss y validity_mask")
    
    def test_path_loss_all_parameters_integrated(self, model):
        """Test: Path Loss con TODOS los parámetros integrados"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        # Terreno con variación (para estimación local building_height)
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.zeros((n_receptors, n_samples))
        for i in range(n_samples):
            x = i / (n_samples - 1)
            z = 2500 + 50 * np.sin(4 * np.pi * x)
            terrain_profiles[:, i] = z
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=40.0,
            terrain_heights=terrain_heights,
            tx_elevation=2500.0,
            mobile_height=1.5,
            building_height=20.0,  # valor default (será estimado localmente)
            street_width=20.0,
            environment='Urban',
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        path_loss = result['path_loss']
        
        # Verificar que path_loss es finito y razonable
        assert np.all(np.isfinite(path_loss)), "Path loss tiene NaN"
        assert path_loss.shape == distances.shape
        
        avg_pl = np.mean(path_loss)
        assert 100 < avg_pl < 150, f"Path loss fuera de rango: {avg_pl:.1f} dB"
        
        print(f"✓ Path Loss integrado: {avg_pl:.1f} dB (rango válido)")
    
    def test_los_vs_nlos_coherence_integrated(self, model):
        """Test: LOS < NLOS en terms de path_loss (integración Fase 1-4)"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        # Escenario LOS: terreno plano
        terrain_profiles_los = np.full((100, 50), 2500.0)
        
        # Escenario NLOS: terreno con obstáculos
        terrain_profiles_nlos = np.zeros((100, 50))
        for i in range(50):
            x = i / 49
            z = 2600 - (2600 - 2400) * x
            peak = 400 * np.exp(-((x - 0.5)**2) / 0.08)
            terrain_profiles_nlos[:, i] = z + peak
        
        result_los = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=30.0,
            terrain_heights=terrain_heights,
            tx_elevation=2570.0,
            terrain_profiles=terrain_profiles_los,
            environment='Urban',
            los_method='geometric'
        )
        
        result_nlos = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=30.0,
            terrain_heights=terrain_heights,
            tx_elevation=2570.0,
            terrain_profiles=terrain_profiles_nlos,
            environment='Urban',
            los_method='geometric'
        )
        
        pl_los = np.mean(result_los['path_loss'])
        pl_nlos = np.mean(result_nlos['path_loss'])
        
        print(f"✓ LOS path_loss: {pl_los:.1f} dB")
        print(f"✓ NLOS path_loss: {pl_nlos:.1f} dB")
        print(f"  Diferencia: {pl_nlos - pl_los:.2f} dB")
        
        # NLOS > LOS (porque hay Lmsd adicional)
        assert pl_nlos >= pl_los, "NLOS debería tener PL >= LOS"
    
    def test_parameter_variations_integrated(self, model):
        """Test: Path Loss varía coherentemente con parámetros"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        terrain_profiles = np.full((100, 50), 2500.0)
        
        # Variar frecuencia (debe afectar path_loss)
        result_900 = model.calculate_path_loss(
            distances=distances,
            frequency=900.0,
            tx_height=30.0,
            terrain_heights=terrain_heights,
            tx_elevation=2500.0,
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        result_1800 = model.calculate_path_loss(
            distances=distances,
            frequency=1800.0,
            tx_height=30.0,
            terrain_heights=terrain_heights,
            tx_elevation=2500.0,
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        pl_900 = np.mean(result_900['path_loss'])
        pl_1800 = np.mean(result_1800['path_loss'])
        
        # Mayor frecuencia → mayor path_loss (20*log10(f) aumenta)
        assert pl_1800 > pl_900, f"1800MHz ({pl_1800:.1f}) debería > 900MHz ({pl_900:.1f})"
        
        diff = pl_1800 - pl_900
        expected_diff = 20 * np.log10(1800 / 900)  # ~6 dB solo base
        # Pero hay otros términos en Lrtd (10*log10(f)) y posiblemente Lmsd que afiaden
        
        print(f"✓ Variación frecuencia:")
        print(f"  900MHz: {pl_900:.1f} dB")
        print(f"  1800MHz: {pl_1800:.1f} dB")
        print(f"  Diferencia: {diff:.2f} dB (base esperada ~{expected_diff:.2f} dB)")
        
        # Diferencia debe estar entre base y base*2 (considerando otros términos)
        assert expected_diff < diff < expected_diff * 2, \
            f"Diferencia {diff:.2f} fuera de rango [{expected_diff:.2f}, {expected_diff*2:.2f}]"
    
    def test_all_environments_integrated(self, model):
        """Test: Path Loss para Urban, Suburban, Rural (Fase 4)"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        terrain_profiles = np.zeros((100, 50))
        for i in range(50):
            x = i / 49
            z = 2600 - (2600 - 2400) * x
            peak = 300 * np.exp(-((x - 0.5)**2) / 0.1)
            terrain_profiles[:, i] = z + peak
        
        environments = ['Urban', 'Suburban', 'Rural']
        results = {}
        
        for env in environments:
            result = model.calculate_path_loss(
                distances=distances,
                frequency=900.0,
                tx_height=30.0,
                terrain_heights=terrain_heights,
                tx_elevation=2570.0,
                terrain_profiles=terrain_profiles,
                environment=env,
                los_method='geometric'
            )
            results[env] = np.mean(result['path_loss'])
        
        print(f"✓ Path Loss por ambiente:")
        for env, pl in results.items():
            print(f"  {env}: {pl:.1f} dB")
        
        # Urban debería ser diferente de Suburban y Rural (por kf diferente en Lmsd)
        assert results['Urban'] != results['Suburban'] or results['Suburban'] != results['Rural']
        
        # Todos deben ser números válidos
        for env in environments:
            assert np.isfinite(results[env]), f"{env} path_loss es {results[env]}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
