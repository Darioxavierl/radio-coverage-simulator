"""
Test FASE 4: Clutter Model Validation

Verifica:
1. Detección de clutter morphology (urban/suburban/rural)
2. Height gain correction ITU Annex 5
3. Distance-dependent clutter application
4. Vectorización correcta
5. Valores en rango realista

Autor: Fase 4 Implementation
Fecha: 2025
"""

import numpy as np
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.clutter_model import ClutterModel


def test_clutter_classification():
    """Test: Detección de clutter morphology"""
    print("\n" + "="*70)
    print("TEST 1: Clutter Classification (Morphology Detection)")
    print("="*70)
    
    model = ClutterModel()
    
    # Crear perfiles de prueba
    n_samples = 50
    distances = np.linspace(0, 10000, n_samples)  # 0-10 km
    
    # Caso 1: Terreno plano (rural)
    terrain_rural = 1000 * np.ones(n_samples)
    category = model.classify_clutter_from_dem(terrain_rural, distances, 5000, local_window_m=2000)
    print(f"Terreno plano: variabilidad ~0m → {category}")
    assert category == 'rural', f"Debería ser rural, fue {category}"
    
    # Caso 2: Terreno levemente variable (suburban)
    terrain_suburban = 1000 + 30 * np.sin(np.linspace(0, 2*np.pi, n_samples))
    category = model.classify_clutter_from_dem(terrain_suburban, distances, 5000, local_window_m=2000)
    print(f"Terreno levemente variable: variabilidad ~30m → {category}")
    assert category == 'suburban', f"Debería ser suburban, fue {category}"
    
    # Caso 3: Terreno muy variable (urban)
    terrain_urban = 1000 + 100 * np.sin(np.linspace(0, 4*np.pi, n_samples))
    category = model.classify_clutter_from_dem(terrain_urban, distances, 5000, local_window_m=2000)
    print(f"Terreno muy variable: variabilidad ~100m → {category}")
    assert category == 'urban', f"Debería ser urban, fue {category}"
    
    print("✓ PASS: Detección de clutter correcta")


def test_height_gain_correction():
    """Test: Height gain correction ITU Annex 5"""
    print("\n" + "="*70)
    print("TEST 2: Height Gain Correction (ITU Annex 5)")
    print("="*70)
    
    model = ClutterModel()
    
    # Caso 1: RX bajo clutter (urban, h_clutter=25m, h_rx=1.5m) → pérdida significativa
    loss = model.calculate_height_gain_correction(1.5, 'urban')
    print(f"Urban: h_rx=1.5m (bajo clutter 25m) → pérdida={loss:.2f} dB")
    assert 4.0 < loss <= 8.5, f"Pérdida bajo clutter fuera de rango: {loss}"
    
    # Caso 2: RX a mitad de clutter (h_rx=12.5m) → pérdida intermedia
    loss_half = model.calculate_height_gain_correction(12.5, 'urban')
    print(f"Urban: h_rx=12.5m (mitad clutter) → pérdida={loss_half:.2f} dB")
    assert 2.0 < loss_half < 5.0, f"Pérdida intermedia fuera de rango: {loss_half}"
    
    # Caso 3: RX sobre clutter (h_rx>25m) → sin pérdida
    loss_over = model.calculate_height_gain_correction(50.0, 'urban')
    print(f"Urban: h_rx=50m (sobre clutter) → pérdida={loss_over:.2f} dB")
    assert loss_over < 0.1, f"RX sobre clutter debería tener pérdida ~0: {loss_over}"
    
    # Validación: pérdida decrece con altura
    print(f"\nValidación:")
    print(f"  h_rx=1.5m:  {loss:.2f} dB")
    print(f"  h_rx=12.5m: {loss_half:.2f} dB")
    print(f"  h_rx=50m:   {loss_over:.2f} dB")
    assert loss > loss_half > loss_over, "Pérdida no decrece con altura"
    
    print("✓ PASS: Height gain correction correcta")


def test_distance_dependent_clutter():
    """Test: Aplicación distancia-dependiente"""
    print("\n" + "="*70)
    print("TEST 3: Distance-Dependent Clutter Application")
    print("="*70)
    
    model = ClutterModel()
    
    # Perfil sintético (rural)
    n_samples = 50
    distances = np.linspace(0, 10000, n_samples)
    terrain = 1000 * np.ones(n_samples)
    
    # Parámetros
    h_rx = 1.5  # Bajo clutter
    
    # Caso 1: Distancia cercana (500m, < d_apply=3000m para rural)
    loss_near = model.calculate_clutter_loss(terrain, distances, 500, h_rx, 'rural')
    print(f"Rural, d=500m: pérdida={loss_near:.2f} dB (cercano)")
    
    # Caso 2: Distancia en rango (2000m)
    loss_mid = model.calculate_clutter_loss(terrain, distances, 2000, h_rx, 'rural')
    print(f"Rural, d=2000m: pérdida={loss_mid:.2f} dB (rango)")
    
    # Caso 3: Distancia lejana (5000m, > d_apply=3000m)
    loss_far = model.calculate_clutter_loss(terrain, distances, 5000, h_rx, 'rural')
    print(f"Rural, d=5000m: pérdida={loss_far:.2f} dB (lejano)")
    
    # Validación: pérdida decrece con distancia (o es similar)
    print(f"\nValidación: pérdida debe decrecer con distancia")
    assert loss_near >= loss_mid, f"Cercano debería tener >= pérdida que mid"
    assert loss_mid >= loss_far, f"Mid debería tener >= pérdida que lejano"
    
    print("✓ PASS: Distance-dependent clutter correcta")


def test_environment_comparison():
    """Test: Comparación rural vs suburban vs urban"""
    print("\n" + "="*70)
    print("TEST 4: Environment Comparison (Rural/Suburban/Urban)")
    print("="*70)
    
    model = ClutterModel()
    
    # Perfil sintético
    n_samples = 50
    distances = np.linspace(0, 10000, n_samples)
    terrain = 1000 * np.ones(n_samples)
    
    h_rx = 1.5
    distance = 500  # Cercano, donde clutter es más significativo
    
    # Comparar categorías
    loss_rural = model.calculate_clutter_loss(terrain, distances, distance, h_rx, 'rural')
    loss_suburban = model.calculate_clutter_loss(terrain, distances, distance, h_rx, 'suburban')
    loss_urban = model.calculate_clutter_loss(terrain, distances, distance, h_rx, 'urban')
    
    print(f"Distancia: {distance}m, h_rx={h_rx}m (bajo clutter)")
    print(f"Rural:     {loss_rural:.2f} dB")
    print(f"Suburban:  {loss_suburban:.2f} dB")
    print(f"Urban:     {loss_urban:.2f} dB")
    
    # Urban > Suburban > Rural
    assert loss_urban > loss_suburban, "Urban debería tener más pérdida que suburban"
    assert loss_suburban > loss_rural, "Suburban debería tener más pérdida que rural"
    
    print("✓ PASS: Urban > Suburban > Rural (correctamente ordenado)")


def test_vectorization():
    """Test: Vectorización para múltiples receptores"""
    print("\n" + "="*70)
    print("TEST 5: Vectorization (Multiple Receivers)")
    print("="*70)
    
    model = ClutterModel()
    
    n_receptors = 5
    n_samples = 50
    
    # Perfiles distintos (cada uno con diferente variabilidad)
    terrain_profiles = np.zeros((n_receptors, n_samples))
    for i in range(n_receptors):
        # Variabilidad creciente
        amplitude = i * 20  # 0, 20, 40, 60, 80 m
        terrain_profiles[i] = 1000 + amplitude * np.sin(np.linspace(0, 2*np.pi, n_samples))
    
    # Distancias de perfiles
    profile_distances = np.tile(np.linspace(0, 10000, n_samples), (n_receptors, 1))
    
    # Distancias finales
    distances = np.array([500, 1000, 2000, 5000, 10000])
    
    h_rx = 1.5
    
    # Vectorizado
    losses = model.calculate_clutter_correction_vectorized(
        terrain_profiles, profile_distances, distances, h_rx, environment=None
    )
    
    print(f"n_receptors: {n_receptors}")
    print(f"Pérdidas por receptor:")
    for i, loss in enumerate(losses):
        print(f"  Receptor {i+1}: {loss:.2f} dB")
    
    # Validaciones
    assert len(losses) == n_receptors, f"Output shape incorrecto: {len(losses)}"
    assert np.all(losses >= 0), f"Hay pérdidas negativas: {losses}"
    assert np.all(losses <= 10), f"Hay pérdidas > 10dB: {losses}"
    
    # Pérdidas deben variar (receivers tiene different variability)
    unique_losses = len(np.unique(np.round(losses, 2)))
    print(f"Valores únicos (redondeados): {unique_losses}/{n_receptors}")
    assert unique_losses > 1, "Pérdidas deberían variar entre receptores"
    
    print("✓ PASS: Vectorización correcta")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("\n" + "#"*70)
    print("# PHASE 4: CLUTTER MODEL TESTS")
    print("#"*70)
    
    tests = [
        test_clutter_classification,
        test_height_gain_correction,
        test_distance_dependent_clutter,
        test_environment_comparison,
        test_vectorization,
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
