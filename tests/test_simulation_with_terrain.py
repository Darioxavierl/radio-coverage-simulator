"""
Test de integración completa: Simulación con datos de terreno real

Verifica el flujo completo desde GUI hasta resultados con TerrainLoader
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import numpy as np
from models.antenna import Antenna, Technology
from core.coverage_calculator import CoverageCalculator
from core.compute_engine import ComputeEngine
from core.terrain_loader import TerrainLoader
from core.models.traditional.okumura_hata import OkumuraHataModel


class TestSimulationWithTerrain(unittest.TestCase):
    """Test de simulación completa con terreno"""

    def setUp(self):
        """Setup antes de cada test"""
        # Verificar si existe archivo de terreno
        self.terrain_file = Path('data/terrain/cuenca_terrain.tif')
        self.terrain_exists = self.terrain_file.exists()

        if not self.terrain_exists:
            self.skipTest("Terrain file not available")

        # Crear componentes
        self.engine = ComputeEngine()
        self.calculator = CoverageCalculator(self.engine)
        self.terrain_loader = TerrainLoader(str(self.terrain_file))

    def test_terrain_loader_initialization(self):
        """Verifica que el terreno se carga correctamente"""
        self.assertTrue(self.terrain_loader.is_loaded())

        stats = self.terrain_loader.get_stats()
        print(f"\n[TERRAIN LOADED]")
        print(f"  File: {self.terrain_file}")
        print(f"  Elevation range: {stats['min']:.1f} - {stats['max']:.1f} m")
        print(f"  Mean elevation: {stats['mean']:.1f} m")

    def test_simulation_okumura_hata_with_terrain(self):
        """Test de simulación Okumura-Hata con terreno real"""
        print(f"\n[SIMULATION TEST - Okumura-Hata with Terrain]")

        # Crear antena en Cuenca
        antenna = Antenna(
            name="Test Antenna",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=40.0,
            frequency_mhz=1800,
            tx_power_dbm=43.0,
            technology=Technology.LTE_1800
        )

        # Obtener elevación del TX
        tx_elevation = self.terrain_loader.get_elevation(antenna.latitude, antenna.longitude)
        print(f"  Antenna location: ({antenna.latitude}, {antenna.longitude})")
        print(f"  TX elevation: {tx_elevation:.1f} m")
        print(f"  TX height AGL: {antenna.height_agl} m")
        print(f"  Effective height: {antenna.height_agl + tx_elevation:.1f} m")

        # Modelo Okumura-Hata
        model = OkumuraHataModel(compute_module=self.calculator.xp)

        # Parámetros de simulación
        model_params = {
            'environment': 'Urban',
            'city_type': 'medium',
            'mobile_height': 1.5,
            'tx_elevation': tx_elevation
        }

        print(f"  Model: Okumura-Hata")
        print(f"  Environment: {model_params['environment']}")
        print(f"  City type: {model_params['city_type']}")
        print(f"  Mobile height: {model_params['mobile_height']} m")

        # Ejecutar simulación
        print(f"\n[CALCULATING COVERAGE]")
        coverage = self.calculator.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=3.0,
            resolution=50,  # 50x50 grid para test rápido
            model=model,
            model_params=model_params,
            terrain_loader=self.terrain_loader
        )

        # Verificar resultados
        self.assertIn('rsrp', coverage)
        self.assertIn('lats', coverage)
        self.assertIn('lons', coverage)

        rsrp = coverage['rsrp']
        print(f"  Grid size: {rsrp.shape}")
        print(f"  RSRP range: {rsrp.min():.1f} to {rsrp.max():.1f} dBm")
        print(f"  Valid points: {np.sum(rsrp > -120)}/{rsrp.size}")

        # Verificar valores razonables
        self.assertTrue(-150 < rsrp.min() < 0)
        self.assertTrue(-100 < rsrp.max() < 50)

        print(f"\n[TEST PASSED]")

    def test_simulation_comparison_with_without_terrain(self):
        """Compara simulación con y sin terreno"""
        print(f"\n[COMPARISON TEST - With vs Without Terrain]")

        antenna = Antenna(
            name="Test Antenna",
            latitude=-2.9,
            longitude=-79.0,
            height_agl=40.0,
            frequency_mhz=900,
            tx_power_dbm=43.0
        )

        model = OkumuraHataModel(compute_module=self.calculator.xp)

        # CON terreno
        tx_elevation = self.terrain_loader.get_elevation(antenna.latitude, antenna.longitude)
        model_params_with = {
            'environment': 'Urban',
            'city_type': 'medium',
            'mobile_height': 1.5,
            'tx_elevation': tx_elevation
        }

        coverage_with = self.calculator.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=2.0,
            resolution=30,
            model=model,
            model_params=model_params_with,
            terrain_loader=self.terrain_loader
        )

        # SIN terreno (terreno plano)
        model_params_without = {
            'environment': 'Urban',
            'city_type': 'medium',
            'mobile_height': 1.5,
            'tx_elevation': 0.0
        }

        coverage_without = self.calculator.calculate_single_antenna_quick(
            antenna=antenna,
            center_lat=antenna.latitude,
            center_lon=antenna.longitude,
            radius_km=2.0,
            resolution=30,
            model=model,
            model_params=model_params_without,
            terrain_loader=None  # Sin terreno
        )

        # Comparar
        rsrp_with = coverage_with['rsrp']
        rsrp_without = coverage_without['rsrp']

        diff = rsrp_with - rsrp_without
        mean_diff = np.mean(diff)

        print(f"  WITH terrain RSRP: {rsrp_with.min():.1f} to {rsrp_with.max():.1f} dBm")
        print(f"  WITHOUT terrain RSRP: {rsrp_without.min():.1f} to {rsrp_without.max():.1f} dBm")
        print(f"  Average difference: {mean_diff:.2f} dB")
        print(f"  Max difference: {np.max(np.abs(diff)):.2f} dB")

        # Debe haber diferencia (el terreno afecta la cobertura)
        self.assertTrue(np.abs(mean_diff) > 0.1, "Terrain should affect coverage")

        print(f"\n[TEST PASSED - Terrain has measurable impact]")

    def test_performance_terrain_loading(self):
        """Verifica performance de carga de terreno"""
        import time

        print(f"\n[PERFORMANCE TEST - Terrain Loading]")

        # Test 1: Carga inicial
        start = time.time()
        loader = TerrainLoader(str(self.terrain_file))
        load_time = time.time() - start

        print(f"  Initial load: {load_time:.3f}s")
        self.assertTrue(load_time < 5.0, "Load should be < 5s")

        # Test 2: Queries individuales
        start = time.time()
        for _ in range(1000):
            loader.get_elevation(-2.9, -79.0)
        query_time = (time.time() - start) / 1000

        print(f"  Single query: {query_time*1000:.3f}ms")
        self.assertTrue(query_time < 0.01, "Query should be < 10ms")

        # Test 3: Query vectorizado (grid 100x100)
        lats = np.linspace(-2.95, -2.85, 100)
        lons = np.linspace(-79.05, -78.95, 100)
        grid_lats, grid_lons = np.meshgrid(lats, lons)

        start = time.time()
        elevations = loader.get_elevations_fast(grid_lats, grid_lons)
        vector_time = time.time() - start

        print(f"  Vectorized query (100x100): {vector_time:.3f}s")
        self.assertTrue(vector_time < 2.0, "Vectorized query should be < 2s")

        print(f"\n[PERFORMANCE ACCEPTABLE]")


if __name__ == '__main__':
    unittest.main(verbosity=2)
