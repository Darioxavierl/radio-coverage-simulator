# Tests - RF Coverage Tool

Suite completa de tests unitarios para el simulador de cobertura radioeléctrica.

## Ejecución de Tests

### Modo CPU-Only (Recomendado para desarrollo)

```powershell
$env:FORCE_CPU_ONLY='true'
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/run_all_tests.py
```

### Tests Individuales

```powershell
$env:FORCE_CPU_ONLY='true'

# GPU Detector
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/test_gpu_detector.py

# Compute Engine
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/test_compute_engine.py

# Propagation Models
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/test_propagation_models.py

# Coverage Calculator
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/test_coverage_calculator.py

# Data Models
& "G:/My Drive/Universidad/Tesis/.env/Scripts/python.exe" tests/test_models.py
```

## Estructura de Tests

### `test_gpu_detector.py`
- Detección de GPU/CUDA
- Fallback a CPU
- Información de dispositivo

### `test_compute_engine.py`
- Inicialización CPU/GPU
- Cambio dinámico entre modos
- Operaciones matemáticas básicas

### `test_propagation_models.py`
- Free Space Path Loss Model
- Okumura-Hata Model
- Consistencia CPU vs GPU

### `test_coverage_calculator.py`
- Cálculo de distancias Haversine
- Patrones de antena
- Generación de mapas de cobertura
- Propiedades dinámicas

### `test_models.py`
- Modelos de datos (Antenna, Site, Project)
- Serialización / Deserialización
- Validaciones

## Cobertura

Actualmente se prueban:
- ✅ Detección y manejo de GPU/CPU
- ✅ Modelos de propagación básicos
- ✅ Cálculos de cobertura
- ✅ Modelos de datos
- ✅ Serialización de proyectos

## Notas

- Los tests que requieren GPU se omiten automáticamente si no está disponible
- Use `FORCE_CPU_ONLY=true` para evitar intentar cargar CuPy si causa problemas
- Todos los tests deben pasar en modo CPU-only

## Resultados Esperados

```
Tests ejecutados: ~25
Exitosos: ~24
Omitidos: ~1 (GPU tests si no disponible)
```
