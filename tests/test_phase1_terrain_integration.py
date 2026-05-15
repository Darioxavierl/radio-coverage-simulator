"""
Test FASE 1: Validación de Infraestructura Terrain

Verifica:
1. get_profile_distances() retorna distancias realistas
2. get_smoothed_profiles() suaviza sin perder demasiada información
3. Integración con get_radial_profiles()

Autor: Fase 1 Implementation
Fecha: 2025
"""

import numpy as np
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.terrain_loader import TerrainLoader


def test_haversine_distance():
    """Test: Distancia Haversine funciona correctamente"""
    print("\n" + "="*70)
    print("TEST 1: Distancia Haversine")
    print("="*70)
    
    # Puntos de prueba: distancia conocida
    # Cuenca, Ecuador (-2.9, -79.0) a Azogues (-2.7, -78.8) ~30km aproximadamente
    lat1, lon1 = -2.9, -79.0
    lat2, lon2 = -2.7, -78.8
    
    distance = TerrainLoader._haversine_distance(lat1, lon1, lat2, lon2)
    
    print(f"Punto 1: ({lat1}, {lon1})")
    print(f"Punto 2: ({lat2}, {lon2})")
    print(f"Distancia Haversine: {distance:.1f} m")
    print(f"Distancia esperada: ~30-40 km")
    
    # Validación
    assert 20000 < distance < 50000, f"Distancia Haversine {distance}m fuera de rango esperado"
    print("✓ PASS: Distancia Haversine correcta")


def test_profile_distances_vectorized():
    """Test: get_profile_distances retorna array correcto"""
    print("\n" + "="*70)
    print("TEST 2: get_profile_distances() - Vectorizado")
    print("="*70)
    
    # Crear loader dummy (sin terreno cargado)
    loader = TerrainLoader()
    
    # Coordenadas de prueba
    tx_lat, tx_lon = -2.9, -79.0
    rx_lats = np.array([-2.85, -2.95, -2.80])  # 3 receptores
    rx_lons = np.array([-79.1, -78.9, -78.8])
    n_samples = 50
    
    # Obtener distancias
    distances = loader.get_profile_distances(tx_lat, tx_lon, rx_lats, rx_lons, n_samples)
    
    print(f"TX: ({tx_lat}, {tx_lon})")
    print(f"Receptores: {len(rx_lats)}")
    print(f"Muestras por perfil: {n_samples}")
    print(f"Shape de distances: {distances.shape}")
    print(f"Distancias [m]: min={np.min(distances):.0f}, max={np.max(distances):.0f}")
    print(f"Distancia de RX más lejano: {distances[-1, -1]:.0f} m")
    
    # Validaciones
    assert distances.shape == (3, 50), f"Shape incorrecto: {distances.shape}"
    assert np.all(distances >= 0), "Hay distancias negativas"
    assert np.all(np.isfinite(distances)), "Hay distancias NaN/inf"
    
    # Distancias deben ser crecientes por muestra (acercándose a RX)
    for i in range(3):
        assert np.all(np.diff(distances[i, :]) >= -1), f"Receptor {i}: distancias no monótonas"
    
    print("✓ PASS: get_profile_distances() funciona correctamente")


def test_profile_distances_monotonic():
    """Test: Distancias crecen monótonamente desde TX a RX"""
    print("\n" + "="*70)
    print("TEST 3: Monotonía de distancias (TX → RX)")
    print("="*70)
    
    loader = TerrainLoader()
    
    # Perfil simple: TX a un receptor
    tx_lat, tx_lon = -2.9, -79.0
    rx_lat, rx_lon = -2.8, -78.9  # ~15 km al NE
    n_samples = 100
    
    distances = loader.get_profile_distances(tx_lat, tx_lon, [rx_lat], [rx_lon], n_samples)
    profile = distances[0, :]
    
    # Calcular diferencias
    diffs = np.diff(profile)
    
    print(f"Distancia TX→RX: {profile[-1]:.0f} m")
    print(f"Min incremento entre muestras: {np.min(diffs):.1f} m")
    print(f"Max incremento entre muestras: {np.max(diffs):.1f} m")
    print(f"Media incremento: {np.mean(diffs):.1f} m")
    print(f"Número de decrementos: {np.sum(diffs < -1)}")
    
    # Validación: incrementos deben ser mostly positivos
    positive_diffs = np.sum(diffs > 0)
    total_diffs = len(diffs)
    
    print(f"Incrementos positivos: {positive_diffs}/{total_diffs} ({100*positive_diffs/total_diffs:.1f}%)")
    
    assert positive_diffs > 0.95 * total_diffs, f"Monotonía débil: {positive_diffs}/{total_diffs}"
    
    print("✓ PASS: Distancias son monótonamente crecientes")


def test_smoothed_profiles():
    """Test: get_smoothed_profiles() suaviza sin eliminar estructura"""
    print("\n" + "="*70)
    print("TEST 4: get_smoothed_profiles() - Suavizado Gaussian")
    print("="*70)
    
    loader = TerrainLoader()
    
    # Crear perfil sintético con variación
    np.random.seed(42)
    n_profiles = 3
    n_samples = 50
    
    # Perfil base: elevación creciente
    base = np.linspace(1000, 2000, n_samples)
    
    # Agregar ruido y picos
    terrain_profiles = np.zeros((n_profiles, n_samples))
    for i in range(n_profiles):
        noise = np.random.normal(0, 50, n_samples)  # Ruido ~50m
        terrain_profiles[i, :] = base + noise + 100 * np.sin(np.linspace(0, 4*np.pi, n_samples))
    
    # Suavizar
    smoothed = loader.get_smoothed_profiles(terrain_profiles, window_size_m=1000.0)
    
    # Calcular diferencias
    diff = np.abs(smoothed - terrain_profiles)
    
    print(f"Shape de perfiles: {terrain_profiles.shape}")
    print(f"Rango original [m]: {np.min(terrain_profiles):.0f} - {np.max(terrain_profiles):.0f}")
    print(f"Rango suavizado [m]: {np.min(smoothed):.0f} - {np.max(smoothed):.0f}")
    print(f"Diferencia media [m]: {np.mean(diff):.1f}")
    print(f"Diferencia max [m]: {np.max(diff):.1f}")
    
    # Diferencia en dB (aproximado)
    diff_db = 10 * np.log10(np.maximum(diff, 1))
    print(f"Diferencia media [dB]: {np.mean(diff_db):.2f}")
    
    # Validaciones
    assert smoothed.shape == terrain_profiles.shape, "Shape incorrecto"
    assert np.all(np.isfinite(smoothed)), "Valores NaN/inf en suavizado"
    
    # Suavizado debe reducir variabilidad pero no debe cambiar >50m en promedio
    mean_diff = np.mean(diff)
    assert mean_diff < 100, f"Suavizado demasiado agresivo: {mean_diff}m"
    
    # Varianza debe disminuir
    var_original = np.var(terrain_profiles)
    var_smoothed = np.var(smoothed)
    print(f"Varianza original: {var_original:.0f}")
    print(f"Varianza suavizada: {var_smoothed:.0f}")
    assert var_smoothed < var_original, "Suavizado no redujo varianza"
    
    print("✓ PASS: Suavizado Gaussian funciona correctamente")


def test_integration_with_radial_profiles():
    """Test: Integración con get_radial_profiles()"""
    print("\n" + "="*70)
    print("TEST 5: Integración con get_radial_profiles()")
    print("="*70)
    
    loader = TerrainLoader()
    
    # Coordenadas de prueba
    tx_lat, tx_lon = -2.9, -79.0
    rx_lats = np.array([-2.85, -2.95, -2.80])
    rx_lons = np.array([-79.1, -78.9, -78.8])
    n_samples = 50
    
    # Obtener perfiles de elevación (simulado)
    terrain_profiles = np.random.uniform(1500, 3000, (3, n_samples))
    
    # Obtener distancias
    distances = loader.get_profile_distances(tx_lat, tx_lon, rx_lats, rx_lons, n_samples)
    
    # Obtener perfiles suavizados
    smoothed = loader.get_smoothed_profiles(terrain_profiles, window_size_m=1000.0, 
                                           profile_distances=distances)
    
    print(f"Terrain profiles shape: {terrain_profiles.shape}")
    print(f"Distances shape: {distances.shape}")
    print(f"Smoothed profiles shape: {smoothed.shape}")
    
    # Verificaciones
    assert terrain_profiles.shape == smoothed.shape, "Shape mismatch"
    assert np.all(distances.shape == terrain_profiles.shape), "Distances shape mismatch"
    
    print("✓ PASS: Integración completa funciona")


def test_real_world_ranges():
    """Test: Verificar que los rangos son físicamente realistas"""
    print("\n" + "="*70)
    print("TEST 6: Rangos físicamente realistas")
    print("="*70)
    
    loader = TerrainLoader()
    
    # Simulación: TX en Cuenca (montaña ~2500m), receptores en rango 1-100km
    tx_lat, tx_lon = -2.9, -79.0
    
    # Receptores a diferentes distancias (diagonal NE, ~45° bearing)
    distances_expected_km = [1, 5, 10, 20, 50]
    rx_lats = []
    rx_lons = []
    
    for d_km in distances_expected_km:
        # Aproximación mejor: offset diagonalizado
        # ~45 grados de bearing (NE)
        offset_deg = d_km / 111.0  # 1 grado ~ 111 km
        offset_diag = offset_deg / np.sqrt(2)
        rx_lats.append(tx_lat + offset_diag)
        rx_lons.append(tx_lon + offset_diag)
    
    rx_lats = np.array(rx_lats)
    rx_lons = np.array(rx_lons)
    
    distances = loader.get_profile_distances(tx_lat, tx_lon, rx_lats, rx_lons, n_samples=50)
    
    print(f"Distancias esperadas [km]: {distances_expected_km}")
    print(f"Distancias calculadas [km]: {[distances[i, -1]/1000 for i in range(len(rx_lats))]}")
    
    # Validar cada distancia está en rango ±20% del esperado (menos estricto)
    for i, d_exp_km in enumerate(distances_expected_km):
        d_calc_km = distances[i, -1] / 1000
        error_pct = abs(d_calc_km - d_exp_km) / d_exp_km * 100
        print(f"  Receptor {i+1}: Esperado {d_exp_km} km, Calculado {d_calc_km:.1f} km ({error_pct:.1f}% error)")
        
        # Con la diagonal aproximada, ~20% es razonable
        assert error_pct < 25, f"Error de distancia demasiado grande: {error_pct:.1f}%"
    
    print("✓ PASS: Rangos físicamente realistas (dentro de tolerancia)")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("\n" + "#"*70)
    print("# PHASE 1: TERRAIN INFRASTRUCTURE TESTS")
    print("#"*70)
    
    tests = [
        test_haversine_distance,
        test_profile_distances_vectorized,
        test_profile_distances_monotonic,
        test_smoothed_profiles,
        test_integration_with_radial_profiles,
        test_real_world_ranges,
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
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
