"""
Test FASE 5: Percentile Tables Validation

Verifica:
1. Tablas de percentiles temporal y espacial
2. Correcciones de percentil correctas
3. Monotonía: P99 < P50 < P1
4. Rango de variación [-3.09, 3.09] dB
5. Consistencia temporal vs espacial

Referencia: ITU-R P.1546-6 Annex 5

Autor: Fase 5 Implementation
Fecha: 2025
"""

import numpy as np
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.models.traditional.itu_r_p1546_tables import (
    PERCENTILE_TIME_VARIATION,
    PERCENTILE_LOCATION_VARIATION,
    AVAILABLE_PERCENTILES,
    get_percentile_correction,
    apply_percentile_correction,
)


def test_percentile_tables_exist():
    """Test: Tablas de percentiles existen y son completas"""
    print("\n" + "="*70)
    print("TEST 1: Percentile Tables Existence")
    print("="*70)
    
    # Verificar que ambas tablas existen
    print(f"Percentiles disponibles: {AVAILABLE_PERCENTILES}")
    
    # Tiempo
    print(f"\nVariation Temporal:")
    for p in AVAILABLE_PERCENTILES:
        val = PERCENTILE_TIME_VARIATION.get(p)
        print(f"  P{p:2d}: {val:+6.2f} dB")
    
    # Ubicación
    print(f"\nVariation Spatial:")
    for p in AVAILABLE_PERCENTILES:
        val = PERCENTILE_LOCATION_VARIATION.get(p)
        print(f"  P{p:2d}: {val:+6.2f} dB")
    
    # Validar completitud
    assert len(PERCENTILE_TIME_VARIATION) == 5, "Faltan percentiles temporales"
    assert len(PERCENTILE_LOCATION_VARIATION) == 5, "Faltan percentiles espaciales"
    
    print("\n✓ PASS: Tablas de percentiles completas")


def test_percentile_monotonicity():
    """Test: Monotonía: P99 < P50 < P1"""
    print("\n" + "="*70)
    print("TEST 2: Percentile Monotonicity (P99 < P50 < P1)")
    print("="*70)
    
    # Temporal
    p99_time = PERCENTILE_TIME_VARIATION[99]
    p50_time = PERCENTILE_TIME_VARIATION[50]
    p1_time = PERCENTILE_TIME_VARIATION[1]
    
    print(f"Temporal: P99={p99_time:.2f} < P50={p50_time:.2f} < P1={p1_time:.2f}")
    assert p99_time < p50_time < p1_time, "Temporal: monotonía incorrecta"
    
    # Espacial
    p99_loc = PERCENTILE_LOCATION_VARIATION[99]
    p50_loc = PERCENTILE_LOCATION_VARIATION[50]
    p1_loc = PERCENTILE_LOCATION_VARIATION[1]
    
    print(f"Spatial:  P99={p99_loc:.2f} < P50={p50_loc:.2f} < P1={p1_loc:.2f}")
    assert p99_loc < p50_loc < p1_loc, "Spatial: monotonía incorrecta"
    
    print("\n✓ PASS: Monotonía correcta")


def test_percentile_reference():
    """Test: P50 es referencia (0 dB)"""
    print("\n" + "="*70)
    print("TEST 3: P50 as Reference (0 dB)")
    print("="*70)
    
    p50_time = PERCENTILE_TIME_VARIATION[50]
    p50_loc = PERCENTILE_LOCATION_VARIATION[50]
    
    print(f"P50 Temporal: {p50_time:.2f} dB (esperado: 0.0 dB)")
    print(f"P50 Spatial:  {p50_loc:.2f} dB (esperado: 0.0 dB)")
    
    assert p50_time == 0.0, "P50 temporal debe ser 0 dB"
    assert p50_loc == 0.0, "P50 spatial debe ser 0 dB"
    
    print("\n✓ PASS: P50 es referencia correcta")


def test_percentile_symmetry():
    """Test: P1 y P99 son aproximadamente simétricos alrededor de P50"""
    print("\n" + "="*70)
    print("TEST 4: Percentile Symmetry (P1 ≈ -P99)")
    print("="*70)
    
    # Temporal
    p1_time = PERCENTILE_TIME_VARIATION[1]
    p99_time = PERCENTILE_TIME_VARIATION[99]
    
    print(f"Temporal: P1={p1_time:.2f}, P99={p99_time:.2f}")
    print(f"  Suma P1+P99: {p1_time + p99_time:.2f} dB (esperado ~0)")
    
    assert abs(p1_time + p99_time) < 0.1, "Temporal: no es simétrico"
    
    # Espacial
    p1_loc = PERCENTILE_LOCATION_VARIATION[1]
    p99_loc = PERCENTILE_LOCATION_VARIATION[99]
    
    print(f"Spatial:  P1={p1_loc:.2f}, P99={p99_loc:.2f}")
    print(f"  Suma P1+P99: {p1_loc + p99_loc:.2f} dB (esperado ~0)")
    
    assert abs(p1_loc + p99_loc) < 0.1, "Spatial: no es simétrico"
    
    print("\n✓ PASS: Simetría correcta")


def test_percentile_range():
    """Test: Rango de variación [-3.09, 3.09] dB"""
    print("\n" + "="*70)
    print("TEST 5: Percentile Range [-3.09, 3.09] dB")
    print("="*70)
    
    MIN_CORRECTION = -3.09
    MAX_CORRECTION = 3.09
    
    # Temporal
    for p in AVAILABLE_PERCENTILES:
        val = PERCENTILE_TIME_VARIATION[p]
        print(f"Temporal P{p:2d}: {val:+6.2f} dB", end="")
        assert MIN_CORRECTION <= val <= MAX_CORRECTION, f"Fuera de rango: {val}"
        print(" ✓")
    
    # Espacial
    for p in AVAILABLE_PERCENTILES:
        val = PERCENTILE_LOCATION_VARIATION[p]
        print(f"Spatial  P{p:2d}: {val:+6.2f} dB", end="")
        assert MIN_CORRECTION <= val <= MAX_CORRECTION, f"Fuera de rango: {val}"
        print(" ✓")
    
    print("\n✓ PASS: Todos los valores en rango correcto")


def test_get_percentile_correction_function():
    """Test: Función get_percentile_correction()"""
    print("\n" + "="*70)
    print("TEST 6: get_percentile_correction() Function")
    print("="*70)
    
    # Temporal
    for p in [1, 10, 50, 90, 99]:
        val = get_percentile_correction(p, 'time')
        expected = PERCENTILE_TIME_VARIATION[p]
        print(f"Temporal P{p:2d}: {val:+6.2f} dB (esperado: {expected:+6.2f})")
        assert val == expected, f"Valor incorrecto para P{p}"
    
    # Espacial
    for p in [1, 10, 50, 90, 99]:
        val = get_percentile_correction(p, 'location')
        expected = PERCENTILE_LOCATION_VARIATION[p]
        print(f"Spatial  P{p:2d}: {val:+6.2f} dB (esperado: {expected:+6.2f})")
        assert val == expected, f"Valor incorrecto para P{p}"
    
    print("\n✓ PASS: get_percentile_correction() correcta")


def test_apply_percentile_correction():
    """Test: Aplicación de corrección de percentil"""
    print("\n" + "="*70)
    print("TEST 7: apply_percentile_correction() Function")
    print("="*70)
    
    # Referencia
    E_50 = 85.0  # dBμV/m a 50%
    
    print(f"Campo referencia (P50): {E_50:.2f} dBμV/m")
    print("\nCorrecciones aplicadas:")
    
    # Temporal
    for p in [1, 10, 50, 90, 99]:
        E_p = apply_percentile_correction(E_50, p, 'time')
        correction = PERCENTILE_TIME_VARIATION[p]
        expected = E_50 + correction
        print(f"  Temporal P{p:2d}: {E_p:+7.2f} dBμV/m (correction: {correction:+6.2f} dB)")
        assert E_p == expected, f"Corrección incorrecta para P{p}"
    
    # Validación: E_P1 > E_P50 > E_P99 (campo más fuerte en P1)
    E_p1 = apply_percentile_correction(E_50, 1, 'time')
    E_p99 = apply_percentile_correction(E_50, 99, 'time')
    
    print(f"\nValidación:")
    print(f"  E_P1  = {E_p1:.2f} dBμV/m (máximo)")
    print(f"  E_P50 = {E_50:.2f} dBμV/m (medio)")
    print(f"  E_P99 = {E_p99:.2f} dBμV/m (mínimo)")
    
    assert E_p1 > E_50 > E_p99, "Monotonía incorrecto en aplicación"
    
    print("\n✓ PASS: apply_percentile_correction() correcta")


def run_all_tests():
    """Ejecuta todos los tests"""
    print("\n" + "#"*70)
    print("# PHASE 5: PERCENTILE TABLES TESTS")
    print("#"*70)
    
    tests = [
        test_percentile_tables_exist,
        test_percentile_monotonicity,
        test_percentile_reference,
        test_percentile_symmetry,
        test_percentile_range,
        test_get_percentile_correction_function,
        test_apply_percentile_correction,
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
