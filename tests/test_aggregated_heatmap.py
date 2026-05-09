"""
Tests for aggregated heatmap functionality (PHASE 7)

Validates that multiple antenna deployments correctly generate aggregated heatmaps
showing maximum RSRP from all antennas in each grid point.
"""

import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.coverage_calculator import CoverageCalculator
from core.compute_engine import ComputeEngine
from models.antenna import Antenna
from core.models.traditional.free_space import FreeSpacePathLossModel
from utils.heatmap_generator import HeatmapGenerator


class TestAggregatedHeatmap(unittest.TestCase):
    """Test suite for aggregated heatmap generation with multiple antennas"""

    def setUp(self):
        """Set up test fixtures"""
        # Create compute engine
        self.engine = ComputeEngine(use_gpu=False)
        self.calculator = CoverageCalculator(self.engine)

        # Create test antennas
        self.antenna1 = Antenna(
            name="Antenna 1",
            latitude=-2.900,
            longitude=-78.900,
            height_agl=30.0,
            tx_power_dbm=43.0,
            frequency_mhz=2100,
            enabled=True,
            show_coverage=True
        )

        self.antenna2 = Antenna(
            name="Antenna 2",
            latitude=-2.901,
            longitude=-78.901,
            height_agl=30.0,
            tx_power_dbm=40.0,
            frequency_mhz=2100,
            enabled=True,
            show_coverage=True
        )

        # Create test grid
        self.grid_lats = np.linspace(-2.91, -2.89, 50)
        self.grid_lons = np.linspace(-78.91, -78.89, 50)
        self.grid_lats, self.grid_lons = np.meshgrid(self.grid_lats, self.grid_lons)
        self.terrain_heights = np.zeros_like(self.grid_lats)

    def test_aggregation_computes_best_server(self):
        """
        Verify that aggregation correctly computes maximum RSRP and best server ID

        PHASE 7: Test that calculate_multi_antenna_coverage returns correct aggregation
        """
        # Create propagation model
        model = FreeSpacePathLossModel(compute_module=np)

        # Calculate aggregated coverage
        aggregated = self.calculator.calculate_multi_antenna_coverage(
            antennas=[self.antenna1, self.antenna2],
            grid_lats=self.grid_lats,
            grid_lons=self.grid_lons,
            terrain_heights=self.terrain_heights,
            model=model,
            model_params={}
        )

        # Verify structure
        self.assertIn('rsrp', aggregated)
        self.assertIn('best_server', aggregated)
        self.assertIn('individual', aggregated)

        # Verify aggregated rsrp is maximum of individual
        rsrp_1 = aggregated['individual'][self.antenna1.id]
        rsrp_2 = aggregated['individual'][self.antenna2.id]
        expected_max = np.maximum(rsrp_1, rsrp_2)

        np.testing.assert_array_almost_equal(aggregated['rsrp'], expected_max, decimal=1)

    def test_aggregated_heatmap_generated(self):
        """
        Verify that aggregated heatmap image is correctly generated

        PHASE 7: Test that HeatmapGenerator produces valid image for aggregated RSRP
        """
        # Create model
        model = FreeSpacePathLossModel(compute_module=np)

        # Calculate aggregated coverage
        aggregated = self.calculator.calculate_multi_antenna_coverage(
            antennas=[self.antenna1, self.antenna2],
            grid_lats=self.grid_lats,
            grid_lons=self.grid_lons,
            terrain_heights=self.terrain_heights,
            model=model,
            model_params={}
        )

        # Generate heatmap image
        heatmap_gen = HeatmapGenerator()
        image_url = heatmap_gen.generate_heatmap_image(
            aggregated['rsrp'],
            colormap='jet',
            vmin=-120,
            vmax=-60,
            alpha=0.6
        )

        # Verify image was generated
        self.assertIsNotNone(image_url)
        self.assertIsInstance(image_url, str)
        self.assertTrue(image_url.startswith('data:image/png'))

    def test_retrocompatibility_single_antenna(self):
        """
        Verify that single antenna deployment still works correctly
        (backwards compatibility - single antenna should use individual as aggregated)

        PHASE 7: Test that single antenna doesn't break with new aggregation logic
        """
        # Create model
        model = FreeSpacePathLossModel(compute_module=np)

        # Calculate with single antenna
        aggregated = self.calculator.calculate_multi_antenna_coverage(
            antennas=[self.antenna1],
            grid_lats=self.grid_lats,
            grid_lons=self.grid_lons,
            terrain_heights=self.terrain_heights,
            model=model,
            model_params={}
        )

        # Verify structure
        self.assertIn('rsrp', aggregated)
        self.assertIn('best_server', aggregated)
        self.assertIn('individual', aggregated)

        # Verify rsrp matches the single antenna's coverage
        rsrp_individual = aggregated['individual'][self.antenna1.id]
        np.testing.assert_array_equal(aggregated['rsrp'], rsrp_individual)

    def test_best_server_assignment(self):
        """
        Verify that best_server correctly identifies strongest antenna at each point

        PHASE 7: Test that best_server_id array correctly identifies dominant antenna
        """
        # Create model
        model = FreeSpacePathLossModel(compute_module=np)

        # Calculate aggregated coverage
        aggregated = self.calculator.calculate_multi_antenna_coverage(
            antennas=[self.antenna1, self.antenna2],
            grid_lats=self.grid_lats,
            grid_lons=self.grid_lons,
            terrain_heights=self.terrain_heights,
            model=model,
            model_params={}
        )

        # Get individual RSRP arrays
        rsrp_1 = aggregated['individual'][self.antenna1.id]
        rsrp_2 = aggregated['individual'][self.antenna2.id]
        best_server = aggregated['best_server']

        # Verify best_server correctly identifies stronger signal
        # At each point, best_server should match the antenna with higher RSRP
        for i in range(best_server.shape[0]):
            for j in range(best_server.shape[1]):
                if rsrp_1[i, j] > rsrp_2[i, j]:
                    self.assertEqual(best_server[i, j], self.antenna1.id)
                elif rsrp_2[i, j] > rsrp_1[i, j]:
                    self.assertEqual(best_server[i, j], self.antenna2.id)
                # If equal, could be either - don't assert

    def test_aggregation_preserves_shape(self):
        """
        Verify that aggregated RSRP array preserves grid shape

        PHASE 7: Test that shape consistency is maintained
        """
        # Create model
        model = FreeSpacePathLossModel(compute_module=np)

        # Calculate aggregated coverage
        aggregated = self.calculator.calculate_multi_antenna_coverage(
            antennas=[self.antenna1, self.antenna2],
            grid_lats=self.grid_lats,
            grid_lons=self.grid_lons,
            terrain_heights=self.terrain_heights,
            model=model,
            model_params={}
        )

        # Verify shapes match grid
        self.assertEqual(aggregated['rsrp'].shape, self.grid_lats.shape)
        self.assertEqual(aggregated['best_server'].shape, self.grid_lats.shape)

        # Verify individual shapes also match
        for antenna_id, rsrp_individual in aggregated['individual'].items():
            self.assertEqual(rsrp_individual.shape, self.grid_lats.shape)


class TestAggregatedHeatmapIntegration(unittest.TestCase):
    """Integration tests for aggregated heatmap with multiple models"""

    def setUp(self):
        """Set up test fixtures"""
        # Create compute engine
        self.engine = ComputeEngine(use_gpu=False)
        self.calculator = CoverageCalculator(self.engine)

        self.antenna1 = Antenna(
            name="Antenna 1",
            latitude=-2.900,
            longitude=-78.900,
            height_agl=30.0,
            tx_power_dbm=43.0,
            frequency_mhz=2100,
            enabled=True,
            show_coverage=True
        )

        self.antenna2 = Antenna(
            name="Antenna 2",
            latitude=-2.905,
            longitude=-78.905,
            height_agl=30.0,
            tx_power_dbm=40.0,
            frequency_mhz=2100,
            enabled=True,
            show_coverage=True
        )

        self.grid_lats = np.linspace(-2.91, -2.89, 30)
        self.grid_lons = np.linspace(-78.91, -78.89, 30)
        self.grid_lats, self.grid_lons = np.meshgrid(self.grid_lats, self.grid_lons)
        self.terrain_heights = np.zeros_like(self.grid_lats)

    def test_aggregation_with_okumura_hata(self):
        """Test aggregation works with Okumura-Hata model"""
        try:
            from core.models.traditional.okumura_hata import OkumuraHataModel

            model = OkumuraHataModel(
                config={'environment': 'Urban', 'city_type': 'medium'},
                compute_module=np
            )

            aggregated = self.calculator.calculate_multi_antenna_coverage(
                antennas=[self.antenna1, self.antenna2],
                grid_lats=self.grid_lats,
                grid_lons=self.grid_lons,
                terrain_heights=self.terrain_heights,
                model=model,
                model_params={'environment': 'Urban', 'city_type': 'medium'}
            )

            self.assertIn('rsrp', aggregated)
            self.assertIn('best_server', aggregated)
            self.assertEqual(aggregated['rsrp'].shape, self.grid_lats.shape)

        except ImportError:
            self.skipTest("Okumura-Hata model not available")


if __name__ == '__main__':
    unittest.main(verbosity=2)
