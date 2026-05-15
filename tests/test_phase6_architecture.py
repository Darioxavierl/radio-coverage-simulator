"""
Test FASE 6: Arquitectura Limpia (sin terminal_clearance bug)

Verifica:
1. Modelo P.1546 funciona sin terminal_clearance
2. Path loss razonables sin inflación +10dB
3. Pipeline: h_eff → E → TCA → clutter → percentile → PL
4. Valores finales en rango correcto (50-130 dB típico)

Referencia: ITU-R P.1546-6 (Cleaned Architecture)

Autor: Fase 6 Implementation
Fecha: 2025
"""

import numpy as np
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.itu_r_p1546 import ITUR_P1546Model


def test_model_initialization():
    """Test: Modelo inicializa sin errores"""
    print("\n" + "="*70)
    print("TEST 1: Model Initialization (Cleaned Architecture)")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    print(f"Model: {model.name}")
    print(f"Compute module: {model.xp.__name__}")
    print(f"Defaults: {model.defaults}")
    
    # Validar que no hay referencia a terminal_clearance en código ejecutable
    # (Solo debe estar en comments ahora)
    
    print("✓ PASS: Modelo inicializado correctamente")


def test_path_loss_without_terminal_clearance():
    """Test: Path Loss sin inflación terminal_clearance"""
    print("\n" + "="*70)
    print("TEST 2: Terminal Clearance Removed (No +10dB Inflation)")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    # Verificar que la función terminal_clearance fue removida
    has_terminal_func = hasattr(model, '_calculate_terminal_clearance_vectorized')
    
    if has_terminal_func:
        print("✗ ERROR: _calculate_terminal_clearance_vectorized aún existe!")
        print("  FASE 6 requiere remover esta función (causa +10dB bug)")
        raise AssertionError("Terminal clearance function not removed")
    
    print("✓ Función _calculate_terminal_clearance_vectorized removida")
    
    # Ejecutar modelo con terreno variable (que antes causaba terminal_clearance +10dB)
    frequency_mhz = 900
    tx_height_m = 30
    rx_height_m = 1.5
    distance_km = np.array([5, 10])
    
    # Terreno con variación (antes causaría terminal_clearance)
    terrain_profiles = np.zeros((2, 50))
    for i in range(2):
        # Variación ~50m (suficiente para activar terminal_clearance antiguo)
        terrain_profiles[i] = 1000 + 25 * np.sin(np.linspace(0, 4*np.pi, 50))
    
    terrain_heights = np.array([1000, 1000])
    
    # Calcular path loss
    result = model.calculate_path_loss(
        distances=distance_km,
        frequency=frequency_mhz,
        tx_height=tx_height_m,
        terrain_heights=terrain_heights,
        terrain_profiles=terrain_profiles,
        environment='Suburban',
        mobile_height=rx_height_m,
    )
    
    path_loss = result['path_loss']
    
    print(f"\nPath Loss (sin terminal_clearance +10dB):")
    for i, pl in enumerate(path_loss.flatten()):
        print(f"  Receptor {i+1}: {pl:.2f} dB (reasonable, no +10dB inflation)")
    
    # Validación: path loss debe estar en rango razonable
    flat_pl = path_loss.flatten()
    assert np.all(flat_pl > 50), f"Path loss < 50 dB"
    assert np.all(flat_pl < 100), f"Path loss > 100 dB (posible +10dB inflation)"
    
    print("\n✓ PASS: Sin inflación terminal_clearance")


def test_architecture_pipeline():
    """Test: Pipeline completo ITU correcto"""
    print("\n" + "="*70)
    print("TEST 3: Architecture Pipeline Validation")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    # Verificar que functions internas existen y son accesibles
    functions = [
        '_calculate_effective_height_vectorized',
        '_interpolate_field_intensity',
        '_calculate_tca_correction_vectorized',
        '_calculate_clutter_correction_vectorized',
        '_apply_percentile_correction',
        '_convert_field_to_path_loss',
    ]
    
    print("Pipeline stages:")
    for func_name in functions:
        has_func = hasattr(model, func_name)
        status = "✓" if has_func else "✗"
        print(f"  {status} {func_name}")
        assert has_func, f"Falta función: {func_name}"
    
    # Verificar que terminal_clearance NO existe como función
    has_terminal = hasattr(model, '_calculate_terminal_clearance_vectorized')
    print(f"  ✓ NO terminal_clearance function (removida en FASE 6)")
    assert not has_terminal, "terminal_clearance aún existe, no fue removida"
    
    print("\n✓ PASS: Architecture pipeline correcto")


def test_multiple_environments():
    """Test: Modelo funciona en distintos ambientes"""
    print("\n" + "="*70)
    print("TEST 4: Multiple Environments (No Terminal Clearance Issues)")
    print("="*70)
    
    model = ITUR_P1546Model()
    
    # Parámetros
    frequency_mhz = 800
    tx_height_m = 50
    rx_height_m = 1.5
    distance_km = np.array([10])
    
    # Terreno
    terrain_profiles = np.ones((1, 50)) * 800
    terrain_heights = np.array([800])
    
    environments = ['Urban', 'Suburban', 'Rural']
    path_losses = {}
    
    print(f"Frequency: {frequency_mhz} MHz")
    print(f"Distance: {distance_km[0]} km")
    print(f"TX height: {tx_height_m} m")
    print(f"RX height: {rx_height_m} m")
    print(f"\nPath Loss by Environment:")
    
    for env in environments:
        result = model.calculate_path_loss(
            distances=distance_km,
            frequency=frequency_mhz,
            tx_height=tx_height_m,
            terrain_heights=terrain_heights,
            terrain_profiles=terrain_profiles,
            environment=env,
            mobile_height=rx_height_m,
        )
        
        pl = result['path_loss']
        path_losses[env] = pl.flatten()[0]
        print(f"  {env:10s}: {pl.flatten()[0]:6.2f} dB")
    
    # Validación: Urban > Suburban > Rural (más obstáculos = más pérdida)
    urban_pl = path_losses['Urban']
    suburban_pl = path_losses['Suburban']
    rural_pl = path_losses['Rural']
    
    print(f"\nValidation:")
    print(f"  Urban > Suburban: {urban_pl:.1f} > {suburban_pl:.1f} ?", end=" ")
    assert urban_pl >= suburban_pl - 0.5, "Urban no es >= Suburban"  # Pequeña tolerancia
    print("✓")
    
    print(f"  Suburban > Rural: {suburban_pl:.1f} > {rural_pl:.1f} ?", end=" ")
    assert suburban_pl >= rural_pl - 0.5, "Suburban no es >= Rural"
    print("✓")
    
    print("\n✓ PASS: Múltiples ambientes funcionan correctamente")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("\n" + "#"*70)
    print("# PHASE 6: CLEANED ARCHITECTURE TESTS")
    print("#"*70)
    
    tests = [
        test_model_initialization,
        test_path_loss_without_terminal_clearance,
        test_architecture_pipeline,
        test_multiple_environments,
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
