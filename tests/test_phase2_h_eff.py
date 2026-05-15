"""
Test FASE 2: Validación de h_eff refactorizado

Verifica:
1. h_eff con profile_distances reales vs linspace fallback (convergencia <5%)
2. h_eff con smoothed_terrain_profiles vs raw profiles
3. Valores en rango físicamente realista [10-1200m]
4. Per-receptor processing correcto

Autor: Fase 2 Implementation
Fecha: 2025
"""

import numpy as np
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.itu_r_p1546 import ITUR_P1546Model
from core.terrain_loader import TerrainLoader


def test_h_eff_with_and_without_profile_distances():
    """Test: h_eff con distancias reales vs fallback linspace"""
    print("\n" + "="*70)
    print("TEST 1: h_eff - Profile distances reales vs linspace")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    # Datos de prueba
    n_receptors = 3
    n_samples = 50
    
    # Coordenadas
    tx_lat, tx_lon = -2.9, -79.0
    rx_lats = np.array([-2.85, -2.95, -2.80])
    rx_lons = np.array([-79.1, -78.9, -78.8])
    
    # Obtener distancias reales
    loader = TerrainLoader()
    profile_distances = loader.get_profile_distances(tx_lat, tx_lon, rx_lats, rx_lons, n_samples)
    
    # Crear perfiles de terreno sintéticos
    np.random.seed(42)
    terrain_profiles = np.random.uniform(1500, 3000, (n_receptors, n_samples))
    
    # Distancias finales (receptor) en metros
    distances_final = profile_distances[:, -1]
    
    tx_height = 35.0
    tx_elevation = 2500.0
    terrain_heights_final = terrain_profiles[:, -1]
    
    # CASO 1: CON profile_distances reales
    h_eff_with_distances = model._calculate_effective_height_vectorized(
        distances=distances_final,
        tx_height=tx_height,
        tx_elevation=tx_elevation,
        terrain_heights=terrain_heights_final,
        terrain_profiles=terrain_profiles,
        profile_distances=profile_distances
    )
    
    # CASO 2: SIN profile_distances (fallback linspace)
    h_eff_without_distances = model._calculate_effective_height_vectorized(
        distances=distances_final,
        tx_height=tx_height,
        tx_elevation=tx_elevation,
        terrain_heights=terrain_heights_final,
        terrain_profiles=terrain_profiles,
        profile_distances=None
    )
    
    # Calcular diferencias
    diffs = np.abs(h_eff_with_distances - h_eff_without_distances)
    pct_diffs = 100 * diffs / np.maximum(np.abs(h_eff_without_distances), 1.0)
    
    print(f"h_eff con profile_distances: {h_eff_with_distances}")
    print(f"h_eff sin profile_distances: {h_eff_without_distances}")
    print(f"Diferencia [m]: {diffs}")
    print(f"Diferencia [%]: {pct_diffs}")
    print(f"Diferencia máxima: {np.max(pct_diffs):.2f}%")
    
    # Validación: divergence <5%
    max_divergence = np.max(pct_diffs)
    assert max_divergence < 5.0, f"Divergence demasiada: {max_divergence:.2f}%"
    
    print("✓ PASS: h_eff converge correctamente con profile_distances")


def test_h_eff_with_smoothed_profiles():
    """Test: h_eff con smoothed vs raw terrain profiles"""
    print("\n" + "="*70)
    print("TEST 2: h_eff - Smoothed vs raw terrain profiles")
    print("="*70)
    
    model = ITUR_P1546Model()
    loader = TerrainLoader()
    
    # Datos de prueba
    n_receptors = 3
    n_samples = 50
    
    # Crear perfiles con ruido
    np.random.seed(42)
    base_elevation = np.linspace(1500, 2500, n_samples)
    raw_profiles = np.zeros((n_receptors, n_samples))
    for i in range(n_receptors):
        noise = np.random.normal(0, 100, n_samples)  # Ruido ~100m
        raw_profiles[i, :] = base_elevation + noise
    
    # Suavizar perfiles
    smoothed_profiles = loader.get_smoothed_profiles(raw_profiles, window_size_m=1000.0)
    
    # Coordenadas para profile_distances
    tx_lat, tx_lon = -2.9, -79.0
    rx_lats = np.array([-2.85, -2.95, -2.80])
    rx_lons = np.array([-79.1, -78.9, -78.8])
    profile_distances = loader.get_profile_distances(tx_lat, tx_lon, rx_lats, rx_lons, n_samples)
    
    distances_final = profile_distances[:, -1]
    tx_height = 35.0
    tx_elevation = 2500.0
    terrain_heights_final = raw_profiles[:, -1]
    
    # CASO 1: CON raw profiles
    h_eff_raw = model._calculate_effective_height_vectorized(
        distances=distances_final,
        tx_height=tx_height,
        tx_elevation=tx_elevation,
        terrain_heights=terrain_heights_final,
        terrain_profiles=raw_profiles,
        profile_distances=profile_distances
    )
    
    # CASO 2: CON smoothed profiles
    h_eff_smoothed = model._calculate_effective_height_vectorized(
        distances=distances_final,
        tx_height=tx_height,
        tx_elevation=tx_elevation,
        terrain_heights=terrain_heights_final,
        terrain_profiles=smoothed_profiles,
        profile_distances=profile_distances
    )
    
    print(f"h_eff (raw profiles): {h_eff_raw}")
    print(f"h_eff (smoothed profiles): {h_eff_smoothed}")
    print(f"Diferencia: {np.abs(h_eff_raw - h_eff_smoothed)}")
    
    # El suavizado debe reducir diferencias locales pero mantener tendencia general
    # Diferencia esperada: <50m para este caso
    max_diff = np.max(np.abs(h_eff_raw - h_eff_smoothed))
    print(f"Diferencia máxima: {max_diff:.1f} m")
    
    assert max_diff < 100, f"Diferencia excesiva: {max_diff:.1f}m"
    
    print("✓ PASS: h_eff funciona correctamente con smoothed profiles")


def test_h_eff_ranges():
    """Test: h_eff en rango físicamente realista"""
    print("\n" + "="*70)
    print("TEST 3: h_eff - Rango físicamente realista [10-1200m]")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    # Múltiples escenarios
    test_cases = [
        {"name": "Montaña alta", "tx_elev": 3000, "terrain_min": 2000, "terrain_max": 3500, "tx_h": 50},
        {"name": "Llano bajo", "tx_elev": 100, "terrain_min": 0, "terrain_max": 500, "tx_h": 30},
        {"name": "Mixto", "tx_elev": 1500, "terrain_min": 1000, "terrain_max": 2500, "tx_h": 35},
    ]
    
    for case in test_cases:
        print(f"\n  Caso: {case['name']}")
        
        n_receptors = 5
        n_samples = 50
        
        # Perfiles sintéticos
        np.random.seed(42)
        terrain_profiles = np.random.uniform(case['terrain_min'], case['terrain_max'], 
                                           (n_receptors, n_samples))
        
        distances_final = np.array([1000, 5000, 10000, 20000, 50000])  # en metros
        terrain_heights_final = np.mean(terrain_profiles, axis=1)
        
        h_eff = model._calculate_effective_height_vectorized(
            distances=distances_final,
            tx_height=case['tx_h'],
            tx_elevation=case['tx_elev'],
            terrain_heights=terrain_heights_final,
            terrain_profiles=terrain_profiles,
            profile_distances=None
        )
        
        print(f"    h_eff: {h_eff}")
        print(f"    Range: [{np.min(h_eff):.1f}, {np.max(h_eff):.1f}] m")
        
        # Validar rango ITU
        assert np.all(h_eff >= 10.0), f"h_eff < 10m: {h_eff}"
        assert np.all(h_eff <= 1200.0), f"h_eff > 1200m: {h_eff}"
        
        print(f"    ✓ Rango válido")
    
    print("\n✓ PASS: h_eff siempre en rango [10-1200m]")


def test_h_eff_per_receptor_processing():
    """Test: Procesamiento per-receptor es correcto"""
    print("\n" + "="*70)
    print("TEST 4: h_eff - Procesamiento per-receptor")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    n_receptors = 5
    n_samples = 50
    
    # Perfiles distintos para cada receptor
    np.random.seed(42)
    terrain_profiles = np.zeros((n_receptors, n_samples))
    for i in range(n_receptors):
        # Cada receptor tiene una "montaña" a diferente altura base
        base = 1000 + i * 500
        terrain_profiles[i, :] = base + np.random.normal(0, 50, n_samples)
    
    distances_final = np.array([1000, 5000, 10000, 15000, 20000])
    terrain_heights_final = terrain_profiles[:, -1]
    
    tx_height = 35.0
    tx_elevation = 2000.0
    
    h_eff = model._calculate_effective_height_vectorized(
        distances=distances_final,
        tx_height=tx_height,
        tx_elevation=tx_elevation,
        terrain_heights=terrain_heights_final,
        terrain_profiles=terrain_profiles,
        profile_distances=None
    )
    
    print(f"Perfiles base: {terrain_profiles[:, 0]}")
    print(f"h_eff por receptor: {h_eff}")
    
    # Cada h_eff debe ser único (per-receptor processing)
    unique_h_eff = len(np.unique(h_eff))
    print(f"Valores únicos de h_eff: {unique_h_eff}/{n_receptors}")
    
    assert unique_h_eff > 1, "h_eff no debería ser idéntico para todos los receptores"
    
    print("✓ PASS: Procesamiento per-receptor correcto")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("\n" + "#"*70)
    print("# PHASE 2: EFFECTIVE HEIGHT (h_eff) REFACTORING TESTS")
    print("#"*70)
    
    tests = [
        test_h_eff_with_and_without_profile_distances,
        test_h_eff_with_smoothed_profiles,
        test_h_eff_ranges,
        test_h_eff_per_receptor_processing,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ FAIL: {test_func.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
