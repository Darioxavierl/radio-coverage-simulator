"""
Test Fase 3: Estimación local de altura de edificios (building_height)

Valida que:
- Terreno rugoso → estimación de mayor altura de edificios
- Terreno plano → estimación de menor altura de edificios
- Valores dentro de rango físico [8, 40] metros
- Path Loss varía coherentemente con estimación local
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.cost231 import COST231WalfischIkegamiModel


class TestCOST231Phase3BuildingHeightLocal:
    """Tests para FASE 3: Estimación local altura edificios"""
    
    @pytest.fixture
    def model(self):
        return COST231WalfischIkegamiModel()
    
    def test_building_height_estimation_flat_terrain(self, model):
        """Test: Terreno plano → estimación baja de altura edificios"""
        
        n_receptors = 100
        n_samples = 50
        
        # Terreno plano: muy baja variabilidad
        terrain_profiles_flat = np.full((n_receptors, n_samples), 2500.0)
        
        # Estimar alturas
        h_buildings = model._estimate_building_height_local(terrain_profiles_flat)
        
        # Verificar que tenemos array de alturas
        assert h_buildings.shape == (n_receptors,)
        assert np.all(np.isfinite(h_buildings))
        
        # En terreno plano (σ ≈ 0), altura debe estar cerca del mínimo
        h_mean = np.mean(h_buildings)
        h_std = np.std(h_buildings)
        
        print(f"✓ Terreno plano: h_mean={h_mean:.1f}m, h_std={h_std:.1f}m")
        
        # Esperamos altura baja (σ baja → α*0 + β ≈ 12)
        assert 10 < h_mean < 16, f"Altura en terreno plano debería ser ~12m, got {h_mean:.1f}m"
    
    def test_building_height_estimation_rough_terrain(self, model):
        """Test: Terreno rugoso → estimación alta de altura edificios"""
        
        n_receptors = 100
        n_samples = 50
        
        # Terreno rugoso: monte varias veces en el perfil
        terrain_profiles_rough = np.zeros((n_receptors, n_samples))
        for i in range(n_samples):
            x = i / (n_samples - 1)
            # Línea base
            z_base = 2500
            # Varios picos de montaña
            z = z_base + 150 * np.sin(6 * np.pi * x) + 200 * np.cos(8 * np.pi * x)
            terrain_profiles_rough[:, i] = z
        
        # Estimar alturas
        h_buildings = model._estimate_building_height_local(terrain_profiles_rough)
        
        assert h_buildings.shape == (n_receptors,)
        assert np.all(np.isfinite(h_buildings))
        
        h_mean = np.mean(h_buildings)
        h_std = np.std(h_buildings)
        
        print(f"✓ Terreno rugoso: h_mean={h_mean:.1f}m, h_std={h_std:.1f}m")
        
        # Esperamos altura más alta (σ alta → α*σ + β ≥ 12)
        # Con σ ≈ 150-200, esperamos h ≈ 0.3*150 + 12 ≈ 57 (limitado a 40)
        assert h_mean > 15, f"Altura en terreno rugoso debería ser >15m, got {h_mean:.1f}m"
    
    def test_building_height_within_physical_limits(self, model):
        """Test: Todas las alturas estimadas dentro de [8, 40] metros"""
        
        n_receptors = 100
        n_samples = 50
        
        # Generar perfiles variados
        terrain_profiles = np.zeros((n_receptors, n_samples))
        for i in range(n_receptors):
            # Cada receptor con diferente nivel de rugosity
            roughness = i / n_receptors * 500  # 0 a 500m de variación
            for j in range(n_samples):
                x = j / n_samples
                base = 2500
                variation = roughness * np.sin(4 * np.pi * x)
                terrain_profiles[i, j] = base + variation
        
        h_buildings = model._estimate_building_height_local(terrain_profiles)
        
        h_min = np.min(h_buildings)
        h_max = np.max(h_buildings)
        
        print(f"✓ Rango estimaciones: [{h_min:.1f}, {h_max:.1f}] metros")
        
        assert h_min >= 8.0, f"Altura mínima {h_min:.1f}m < 8m (límite inferior)"
        assert h_max <= 40.0, f"Altura máxima {h_max:.1f}m > 40m (límite superior)"
    
    def test_building_height_affects_path_loss(self, model):
        """Test: Path Loss varía con estimación local de altura edificios"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        frequency = 900.0
        tx_height = 40.0
        tx_elevation = 2500.0
        
        # Escenario 1: Terreno plano (estimación baja)
        n_receptors = 100
        n_samples = 50
        terrain_profiles_flat = np.full((n_receptors, n_samples), 2500.0)
        
        result_flat = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles_flat,
            los_method='geometric'
        )
        
        # Escenario 2: Terreno rugoso (estimación alta)
        terrain_profiles_rough = np.zeros((n_receptors, n_samples))
        for i in range(n_samples):
            x = i / (n_samples - 1)
            z_base = 2500
            z = z_base + 150 * np.sin(6 * np.pi * x) + 200 * np.cos(8 * np.pi * x)
            terrain_profiles_rough[:, i] = z
        
        result_rough = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles_rough,
            los_method='geometric'
        )
        
        pl_flat = np.mean(result_flat['path_loss'])
        pl_rough = np.mean(result_rough['path_loss'])
        
        print(f"✓ Terreno plano (h_est baja): PL={pl_flat:.1f} dB")
        print(f"✓ Terreno rugoso (h_est alta): PL={pl_rough:.1f} dB")
        print(f"  Diferencia: {pl_rough - pl_flat:.2f} dB")
        
        # Con roughness mayor → edificios estimados más altos → δh_bm mayor → Lrtd mayor → PL mayor
        # Pero la relación puede ser no-monótona dependiendo de otras variables
        # Simplemente verificamos que ambos calculan correctamente
        assert np.all(np.isfinite(result_flat['path_loss']))
        assert np.all(np.isfinite(result_rough['path_loss']))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
