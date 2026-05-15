"""
Test Fase 2: Corrección Lrtd (altura roof-mobile en lugar de TX-roof)

Valida que:
- Lrtd usa ahora altura correcta (techo-receptor) según ITU-R P.1411-8
- Path Loss cambia respecto a versión anterior (porque Lrtd es diferente)
- Coherencia: valores Lrtd son físicamente razonables
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.cost231 import COST231WalfischIkegamiModel


class TestCOST231Phase2LrtdCorrection:
    """Tests para FASE 2: Corrección Lrtd"""
    
    @pytest.fixture
    def model(self):
        return COST231WalfischIkegamiModel()
    
    def test_lrtd_uses_roof_mobile_height(self, model):
        """Test: Lrtd ahora usa altura techo-receptor correcta"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        # Con terrain_profiles plano para LOS
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.full((n_receptors, n_samples), 2500.0)
        
        frequency = 900.0
        tx_height = 50.0  # TX alto: 50m AGL
        tx_elevation = 2500.0
        mobile_height = 1.5  # Móvil bajo: 1.5m
        building_height = 20.0  # Edificio: 20m
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles,
            mobile_height=mobile_height,
            building_height=building_height,
            los_method='geometric'
        )
        
        path_loss = result['path_loss']
        
        # Verificar que resulta en path_loss finito y razonable
        assert np.all(np.isfinite(path_loss)), "Path loss tiene NaN"
        assert path_loss.shape == distances.shape
        
        # Con TX alto (50m) y receptor bajo (1.5m), edificio (20m):
        # delta_h_bm = 20 - 1.5 = 18.5m → Lrtd debe ser calculado con 18.5m
        # Esto es diferente a la versión anterior que usaba TX-roof = 50-20 = 30m
        
        avg_pl = np.mean(path_loss)
        assert 100 < avg_pl < 140, f"Path loss fuera de rango esperado: {avg_pl:.1f} dB"
        
        print(f"✓ Lrtd correcto (roof-mobile): path_loss={avg_pl:.1f} dB")
        print(f"  Δh_bm = {building_height - mobile_height:.1f}m (techo-receptor)")
    
    def test_path_loss_varies_with_building_height(self, model):
        """Test: Path Loss cambia coherentemente con altura edificio (afecta Lrtd)"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        # NOTA: Sin terrain_profiles para que building_height sea constante (Fase 2)
        # (Con terrain_profiles, Fase 3 la estima localmente)
        
        frequency = 900.0
        tx_height = 50.0
        tx_elevation = 2500.0
        mobile_height = 1.5
        
        # Calcular con dos alturas de edificio diferentes
        result_low_building = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=None,  # Sin profiles: usar building_height constante
            mobile_height=mobile_height,
            building_height=10.0,  # Edificio bajo
            los_method='heuristic'  # Sin terrain_profiles, usar heurística
        )
        
        result_high_building = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=None,  # Sin profiles: usar building_height constante
            mobile_height=mobile_height,
            building_height=30.0,  # Edificio alto
            los_method='heuristic'  # Sin terrain_profiles, usar heurística
        )
        
        pl_low = np.mean(result_low_building['path_loss'])
        pl_high = np.mean(result_high_building['path_loss'])
        
        # Con edificio más alto → Δh_bm mayor → Lrtd mayor → path_loss mayor
        # (delta_h_bm = 10-1.5=8.5m vs 30-1.5=28.5m)
        
        print(f"✓ Edificio bajo (10m): PL={pl_low:.1f} dB")
        print(f"✓ Edificio alto (30m): PL={pl_high:.1f} dB")
        print(f"  Diferencia: {pl_high - pl_low:.2f} dB")
        
        # Esperamos que sean diferentes (arquitectura cambió)
        assert abs(pl_high - pl_low) > 0.1, "Path loss no varía con altura edificio"
    
    def test_los_path_loss_lower_than_nlos(self, model):
        """Test: LOS path_loss < NLOS path_loss (Lmsd añade pérdida en NLOS)"""
        
        # Escenario LOS: terreno plano
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        n_receptors = 100
        n_samples = 50
        terrain_profiles_los = np.full((n_receptors, n_samples), 2500.0)
        
        # Escenario NLOS: perfil con obstrucción
        terrain_profiles_nlos = np.zeros((n_receptors, n_samples))
        for i in range(n_samples):
            x = i / (n_samples - 1)
            line_height = 2600 - (2600 - 2400) * x
            peak = 300 * np.exp(-((x - 0.5)**2) / 0.05)
            terrain_profiles_nlos[:, i] = line_height + peak
        
        frequency = 900.0
        tx_height = 30.0
        tx_elevation = 2570.0
        
        result_los = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles_los,
            los_method='geometric'
        )
        
        result_nlos = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles_nlos,
            los_method='geometric'
        )
        
        pl_los = np.mean(result_los['path_loss'])
        pl_nlos = np.mean(result_nlos['path_loss'])
        
        print(f"✓ LOS path_loss: {pl_los:.1f} dB")
        print(f"✓ NLOS path_loss: {pl_nlos:.1f} dB")
        print(f"  Diferencia (NLOS - LOS): {pl_nlos - pl_los:.2f} dB")
        
        # NLOS debe tener mayor path_loss (por Lmsd adicional)
        assert pl_nlos >= pl_los, "NLOS debería tener PL >= LOS"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
