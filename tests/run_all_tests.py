"""
Ejecuta todos los tests
"""
import sys
import unittest
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Importar tests
from test_gpu_detector import TestGPUDetector
from test_compute_engine import TestComputeEngine
from test_propagation_models import (TestFreeSpaceModel, TestOkumuraHataModel,
                                      TestModelConsistency)
from test_coverage_calculator import TestCoverageCalculator, TestCoverageCalculatorGPU
from test_models import TestAntenna, TestSite, TestProject
from test_gpu_functionality import TestGPUFunctionality, TestCPUGPUConsistency
from test_project_system import (TestProject as TestProjectSystem,
                                  TestSiteSerialization, TestProjectManager)
from test_simulation_dialog import TestSimulationDialog, TestPropagationModelSelection
from test_cost231_complete import *
from test_cost231_integration import *
from test_itu_r_p1546_complete import *
from test_itu_r_p1546_integration import *
from test_3gpp_38901_complete import *
from test_3gpp_38901_integration import *
from test_3gpp_config_heights import TestThreGPP38901ConfigHeights  # PHASE 5: Validar h_bs/h_ue
from test_units_consistency import TestUnitsConsistency  # PHASE 5: Validar unidades


def run_all_tests():
    """Ejecuta toda la suite de tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    print("="*70)
    print("RF COVERAGE TOOL - TEST SUITE")
    print("="*70)
    print("\nExecuting comprehensive tests for CPU and GPU functionality...\n")
    
    # Agregar tests básicos
    suite.addTests(loader.loadTestsFromTestCase(TestGPUDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestComputeEngine))
    
    # Tests de modelos de propagación
    suite.addTests(loader.loadTestsFromTestCase(TestFreeSpaceModel))
    suite.addTests(loader.loadTestsFromTestCase(TestOkumuraHataModel))
    suite.addTests(loader.loadTestsFromTestCase(TestModelConsistency))
    
    # Tests de cálculo de cobertura
    suite.addTests(loader.loadTestsFromTestCase(TestCoverageCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestCoverageCalculatorGPU))
    
    # Tests de modelos de datos
    suite.addTests(loader.loadTestsFromTestCase(TestAntenna))
    suite.addTests(loader.loadTestsFromTestCase(TestSite))
    suite.addTests(loader.loadTestsFromTestCase(TestProject))
    
    # Tests del sistema de proyectos (guardar/cargar)
    suite.addTests(loader.loadTestsFromTestCase(TestProjectSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestSiteSerialization))
    suite.addTests(loader.loadTestsFromTestCase(TestProjectManager))
    
    # Tests del diálogo de simulación y selector de modelo
    suite.addTests(loader.loadTestsFromTestCase(TestSimulationDialog))
    suite.addTests(loader.loadTestsFromTestCase(TestPropagationModelSelection))
    
    # Tests específicos de GPU (se omiten si GPU no disponible)
    suite.addTests(loader.loadTestsFromTestCase(TestGPUFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestCPUGPUConsistency))

    # Tests de COST-231 (completo + integración)
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_cost231_complete']))
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_cost231_integration']))

    # Tests de ITU-R P.1546 (completo + integración)
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_itu_r_p1546_complete']))
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_itu_r_p1546_integration']))

    # Tests de 3GPP TR 38.901 (completo + integración)
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_3gpp_38901_complete']))
    suite.addTests(loader.loadTestsFromModule(sys.modules['test_3gpp_38901_integration']))

    # PHASE 5: Tests de validación - h_bs/h_ue y unidades
    suite.addTests(loader.loadTestsFromTestCase(TestThreGPP38901ConfigHeights))
    suite.addTests(loader.loadTestsFromTestCase(TestUnitsConsistency))

    # Ejecutar
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN DE TESTS")
    print("="*70)
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"[OK] Exitosos: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f"[FAIL] Fallidos: {len(result.failures)}")
    print(f"[ERROR] Errores: {len(result.errors)}")
    print(f"[SKIP] Omitidos: {len(result.skipped)}")
    
    if result.skipped:
        print("\nTests omitidos:")
        for test, reason in result.skipped:
            print(f"  - {test}: {reason}")
    
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
