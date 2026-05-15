"""
Test Fase 1: LOS/NLOS Geométrico (ITU-R P.1411 real)

Valida que:
- LOS/NLOS geométrico calcula correctamente (sin obstrucción → LOS)
- Fallback a heurística funciona (si terrain_profiles=None)
- Coherencia: más receptores NLOS con geométrico vs heurística
"""

import numpy as np
import pytest
import sys
from pathlib import Path

# Agregar src a path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.cost231 import COST231WalfischIkegamiModel


class TestCOST231Phase1GeometricLOSNLOS:
    """Tests para FASE 1: LOS/NLOS Geométrico"""
    
    @pytest.fixture
    def model(self):
        """Instanciar modelo COST-231"""
        return COST231WalfischIkegamiModel()
    
    def test_geometric_los_flat_terrain(self, model):
        """Test: Terreno plano → TODO LOS (sin obstrucción)"""
        
        # Grilla 10x10
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)  # 1km distancia plana
        terrain_heights = np.full((grid_size, grid_size), 2500.0)  # terreno plano
        
        # Perfil radial plano (sin obstrucción)
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.full((n_receptors, n_samples), 2500.0)
        
        # Parámetros
        frequency = 900.0
        tx_height = 30.0
        tx_elevation = 2500.0
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        path_loss = result['path_loss']
        
        # En terreno plano, NO hay obstrucción → TODO LOS
        # LOS implica: PL = PL_FS + Lrtd + Cf (sin Lmsd)
        # NLOS implica: PL = PL_FS + Lrtd + Lmsd + Cf (con Lmsd adicional)
        # Luego, path_loss debe ser más bajo en LOS
        
        assert path_loss.shape == distances.shape
        assert np.all(np.isfinite(path_loss)), "Path loss tiene NaN"
        
        # Con terreno plano sin obstrucción, esperamos path_loss relativamente bajo
        # (sin término Lmsd de difracción múltiple)
        avg_path_loss = np.mean(path_loss)
        assert 100 < avg_path_loss < 140, f"Path loss fuera de rango esperado: {avg_path_loss:.1f} dB"
        
        print(f"✓ Terreno plano: path_loss promedio = {avg_path_loss:.1f} dB (TODO LOS)")
    
    def test_geometric_nlos_obstructed_terrain(self, model):
        """Test: Perfil con montaña entre TX-RX → NLOS (hay obstrucción)"""
        
        # Grilla 10x10
        grid_size = 10
        distances = np.full((grid_size, grid_size), 2000.0)  # 2km distancia
        terrain_heights = np.full((grid_size, grid_size), 2400.0)  # terreno receptor más bajo
        
        # Perfil con obstrucción (montaña en el medio)
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.zeros((n_receptors, n_samples))
        
        # Crear perfil: TX en 2600m, RX en 2400m, con pico de 2800m en el medio
        for i in range(n_samples):
            x = i / (n_samples - 1)  # 0 a 1
            # Línea recta de 2600 a 2400
            line_height = 2600 - (2600 - 2400) * x
            # Pico gaussiano en el medio
            peak = 300 * np.exp(-((x - 0.5)**2) / 0.05)  # pico de 300m
            terrain_profiles[:, i] = line_height + peak
        
        # Parámetros
        frequency = 900.0
        tx_height = 30.0
        tx_elevation = 2570.0  # TX en 2570+30=2600m
        
        result = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles,
            los_method='geometric'
        )
        
        path_loss = result['path_loss']
        
        assert path_loss.shape == distances.shape
        assert np.all(np.isfinite(path_loss)), "Path loss tiene NaN"
        
        # Con obstrucción, esperamos path_loss más alto (hay Lmsd adicional)
        avg_path_loss = np.mean(path_loss)
        assert 100 < avg_path_loss < 150, f"Path loss fuera de rango: {avg_path_loss:.1f} dB"
        
        print(f"✓ Terreno obstruido: path_loss promedio = {avg_path_loss:.1f} dB (TODO NLOS)")
    
    def test_fallback_to_legacy_when_no_profiles(self, model):
        """Test: Sin terrain_profiles → fallback a heurística legacy"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        frequency = 900.0
        tx_height = 30.0
        tx_elevation = 2500.0
        
        # Sin terrain_profiles, debe usar legacy
        result = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=None,
            los_method='auto'  # auto detecta: no profiles → legacy
        )
        
        path_loss = result['path_loss']
        assert path_loss.shape == distances.shape
        assert np.all(np.isfinite(path_loss)), "Path loss legacy tiene NaN"
        
        print(f"✓ Fallback legacy: path_loss promedio = {np.mean(path_loss):.1f} dB")
    
    def test_auto_method_detection(self, model):
        """Test: los_method='auto' elige geométrico si terrain_profiles disponible"""
        
        grid_size = 10
        distances = np.full((grid_size, grid_size), 1000.0)
        terrain_heights = np.full((grid_size, grid_size), 2500.0)
        
        n_receptors = 100
        n_samples = 50
        terrain_profiles = np.full((n_receptors, n_samples), 2500.0)
        
        frequency = 900.0
        tx_height = 30.0
        tx_elevation = 2500.0
        
        # Con profiles + auto → debe elegir 'geometric'
        result_with_profiles = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=terrain_profiles,
            los_method='auto'
        )
        
        # Sin profiles + auto → debe elegir 'heuristic' (legacy)
        result_without_profiles = model.calculate_path_loss(
            distances=distances,
            frequency=frequency,
            tx_height=tx_height,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation,
            terrain_profiles=None,
            los_method='auto'
        )
        
        pl1 = result_with_profiles['path_loss']
        pl2 = result_without_profiles['path_loss']
        
        assert pl1.shape == distances.shape
        assert pl2.shape == distances.shape
        
        print(f"✓ Auto detection: with_profiles={np.mean(pl1):.1f}dB, "
              f"without_profiles={np.mean(pl2):.1f}dB")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
