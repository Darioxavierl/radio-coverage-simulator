"""
3GPP TR 38.901 Propagation Model for 5G
Urban Macro (UMa), Urban Micro (UMi), and Rural Macro (RMa) scenarios

Reference: 3GPP TR 38.901-17 (v17.0.0, 2022)
Standard: Study on Channel Model for Frequencies from 0.5 to 100 GHz

Two operational modes:
1. Probabilistic: Standard LOS/NLOS probability model (fast, comparable)
2. Probabilistic + approximate terrain correction: DEM-based additive correction
    intended as a first-order approximation (not a full ray-tracing solver)
"""

import numpy as np
import warnings
from typing import Dict, Tuple, Optional


class ThreGPP38901Model:
    """
    3GPP TR 38.901 propagation model implementation.

    Frequency Range: 0.5 GHz - 100 GHz
    Distance Range: 10 m - 10 km (UMa), 10 m - 5 km (UMi)

    Attributes:
        scenario (str): 'UMa' (Urban Macro), 'UMi' (Urban Micro), or 'RMa' (Rural Macro)
        config (dict): Configuration with h_bs, h_ue, use_dem
        xp: NumPy or CuPy module reference
    """

    # Scenario-specific parameters
    SCENARIOS = {
        'UMa': {
            'description': 'Urban Macro',
            'h_bs_range': (10, 60),  # meters
            'h_bs_typical': 25,
            'distance_range': (10, 10000),  # meters
            'los_prob_coeff1': 18,
            'los_prob_coeff2': 63,
            'los_path_loss_intercept': 28.0,
            'los_path_loss_distance_slope': 22,
            'nlos_path_loss_intercept': 13.54,
            'nlos_path_loss_distance_slope': 39.08,
            'height_correction': -0.6,
            'shadow_fading_los': 4.0,  # dB std dev
            'shadow_fading_nlos': 8.0,  # dB std dev
            'corr_distance': 37,  # meters
        },
        'UMi': {
            'description': 'Urban Micro',
            'h_bs_range': (5, 25),  # meters
            'h_bs_typical': 10,
            'distance_range': (10, 5000),  # meters
            'los_prob_coeff1': 21,
            'los_prob_coeff2': 109.5,
            'los_path_loss_intercept': 32.4,
            'los_path_loss_distance_slope': 21,
            'nlos_path_loss_intercept': 35.3,
            'nlos_path_loss_distance_slope': 40,
            'height_correction': -0.6,
            'shadow_fading_los': 3.0,
            'shadow_fading_nlos': 7.0,
            'corr_distance': 22,
        },
        'RMa': {
            'description': 'Rural Macro',
            'h_bs_range': (35, 60),
            'h_bs_typical': 35,
            'distance_range': (10, 10000),
            'los_prob_coeff1': 21,
            'los_prob_coeff2': 104,
            'los_path_loss_intercept': 20.0,
            'los_path_loss_distance_slope': 20,
            'nlos_path_loss_intercept': 25.0,
            'nlos_path_loss_distance_slope': 30,
            'height_correction': -0.6,
            'shadow_fading_los': 6.0,
            'shadow_fading_nlos': 8.0,
            'corr_distance': 30,
        },
    }

    def __init__(self, config: Optional[Dict] = None, numpy_module=None):
        """
        Initialize 3GPP TR 38.901 propagation model.

        Args:
            config (dict): Configuration dictionary with:
                - scenario (str): 'UMa', 'UMi', or 'RMa' (default: 'UMa')
                - h_bs (float): Base station height in meters (default: scenario-specific)
                - h_ue (float): User equipment height in meters (default: 1.5)
                - use_dem (bool): Enable deterministic mode with terrain (default: False)
            numpy_module: NumPy or CuPy module (auto-detected if None)
        """
        self.config = config or {}

        # Set default scenario
        self.scenario = self.config.get('scenario', 'UMa')
        if self.scenario not in self.SCENARIOS:
            raise ValueError(f"Invalid scenario: {self.scenario}. Must be 'UMa', 'UMi', or 'RMa'")

        scenario_params = self.SCENARIOS[self.scenario]

        # Set heights with defaults
        self.h_bs = self.config.get('h_bs', scenario_params['h_bs_typical'])
        self.h_ue = self.config.get('h_ue', 1.5)
        self.use_dem = self.config.get('use_dem', False)
        self._dem_warning_emitted = False

        # Validate heights
        h_bs_min, h_bs_max = scenario_params['h_bs_range']
        if not (h_bs_min <= self.h_bs <= h_bs_max):
            warnings.warn(
                f"BS height {self.h_bs}m outside typical range [{h_bs_min}, {h_bs_max}] for {self.scenario}",
                UserWarning
            )

        if not (1.0 <= self.h_ue <= 3.0):
            warnings.warn(
                f"UE height {self.h_ue}m outside typical range [1.0, 3.0]",
                UserWarning
            )

        # Set NumPy/CuPy
        if numpy_module is not None:
            self.xp = numpy_module
        else:
            # Default to NumPy (CuPy must be explicitly requested)
            self.xp = np

    def get_model_info(self) -> Dict:
        """Return model metadata."""
        scenario_params = self.SCENARIOS[self.scenario]
        return {
            'name': '3GPP TR 38.901 (v17.0.0)',
            'scenario': self.scenario,
            'description': scenario_params['description'],
            'frequency_range_ghz': (0.5, 100),
            'distance_range_m': scenario_params['distance_range'],
            'h_bs_m': self.h_bs,
            'h_ue_m': self.h_ue,
            'use_dem': self.use_dem,
            'terrain_mode': 'approximate_dem_correction' if self.use_dem else 'probabilistic_only',
            'height_correction_db': scenario_params['height_correction'],
        }

    def calculate_path_loss(
        self,
        distances: np.ndarray,
        frequency: float,
        tx_height: float = None,
        rx_height: float = None,
        terrain_heights: Optional[np.ndarray] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Calculate path loss using 3GPP TR 38.901 model.

        Args:
            distances (np.ndarray): Distance matrix in METERS (calculated by Haversine from CoverageCalculator)
                                   NO unit detection heuristic - always assume METERS
            frequency (float): Frequency in MHz
            tx_height (float): Transmitter height in meters (only used if h_bs not configured)
            rx_height (float): Receiver height in meters (only used if h_ue not configured)
            terrain_heights (np.ndarray): Terrain elevation data (for deterministic mode)
            **kwargs: Additional parameters (for consistency with other models)

        Returns:
            np.ndarray: Path loss in dB

        Raises:
            ValueError: If inputs are outside valid ranges

        Note:
            - h_bs and h_ue from initialization config have priority over tx_height/rx_height parameters
            - These configured values represent scenario-specific base station and user equipment heights
            - tx_height/rx_height parameters are only used as fallback if h_bs/h_ue are None
            - Distances are ALWAYS expected in METERS (from CoverageCalculator via Haversine)
            - Valid distance range: 10 m - 10 km (10 to 10,000 meters) depending on scenario
        """
        # Use configured heights (from config) with priority over parameters
        # Priority order:
        # 1. h_bs/h_ue passed in kwargs (from model_params via CoverageCalculator)
        # 2. self.h_bs/self.h_ue (from initialization config)
        # 3. tx_height/rx_height parameters (fallback for direct usage)
        if 'h_bs' in kwargs:
            h_bs = kwargs['h_bs']
        elif self.h_bs is not None:
            h_bs = self.h_bs
        else:
            h_bs = tx_height

        if 'h_ue' in kwargs:
            h_ue = kwargs['h_ue']
        elif self.h_ue is not None:
            h_ue = self.h_ue
        else:
            h_ue = rx_height

        # Convert frequency MHz -> GHz
        f_ghz = frequency / 1000.0

        # Validate frequency range
        if not (0.5 <= f_ghz <= 100):
            warnings.warn(
                f"Frequency {f_ghz} GHz outside standard range [0.5, 100] GHz",
                UserWarning
            )

        # Convert distances to numpy array if needed
        distances = self.xp.asarray(distances)

        # Convert distances from meters to kilometers
        # IMPORTANT: CoverageCalculator ALWAYS provides distances in METERS via Haversine
        # No heuristic detection - distances are ALWAYS expected in meters
        distances_km = distances / 1000.0
        distances_m = distances  # Already in meters from source

        # Validate distance range (check in meters)
        scenario_params = self.SCENARIOS[self.scenario]
        d_min_m, d_max_m = scenario_params['distance_range']

        max_dist_m = self.xp.max(distances_m)
        if max_dist_m > d_max_m:
            warnings.warn(
                f"Maximum distance {max_dist_m:.1f} m > {d_max_m} m (max valid range for {self.scenario})",
                UserWarning
            )

        if self.xp.min(distances_m) < d_min_m:
            warnings.warn(
                f"Minimum distance < {d_min_m} m (min valid range for {self.scenario})",
                UserWarning
            )

        # Calculate LOS probability (using meters as per formula)
        los_prob = self._calculate_los_probability(distances_m)

        # Calculate path loss for LOS and NLOS (using meters as per formula)
        pl_los = self._calculate_path_loss_los(f_ghz, distances_m, h_ue)
        pl_nlos = self._calculate_path_loss_nlos(f_ghz, distances_m, h_ue)

        # Blend based on LOS probability
        path_loss = los_prob * pl_los + (1.0 - los_prob) * pl_nlos

        # Apply deterministic terrain corrections if available
        if self.use_dem and terrain_heights is not None:
            if not self._dem_warning_emitted:
                warnings.warn(
                    "3GPP terrain correction mode is an approximate DEM-based adjustment, not full deterministic ray-tracing.",
                    UserWarning
                )
                self._dem_warning_emitted = True
            terrain_heights = self.xp.asarray(terrain_heights)
            diffraction_correction = self._apply_terrain_correction(
                distances_m, f_ghz, terrain_heights, h_bs, h_ue
            )
            path_loss = path_loss + diffraction_correction

        return path_loss

    def _calculate_los_probability(self, distances_m: np.ndarray) -> np.ndarray:
        """
        Calculate LOS probability as function of distance.

        Formula: P_LOS(d) = min(C1/d, 1) * (1 - exp(-d/C2)) + exp(-d/C2)

        where C1 and C2 are scenario-dependent constants.
        """
        scenario_params = self.SCENARIOS[self.scenario]
        C1 = scenario_params['los_prob_coeff1']
        C2 = scenario_params['los_prob_coeff2']

        # P_LOS = min(C1/d, 1) * (1 - exp(-d/C2)) + exp(-d/C2)
        term1 = self.xp.minimum(C1 / distances_m, 1.0)
        term2 = 1.0 - self.xp.exp(-distances_m / C2)
        term3 = self.xp.exp(-distances_m / C2)

        los_prob = term1 * term2 + term3

        return self.xp.clip(los_prob, 0.0, 1.0)

    def _calculate_path_loss_los(
        self,
        f_ghz: float,
        distances_m: np.ndarray,
        h_ue: float
    ) -> np.ndarray:
        """
        Calculate LOS path loss.

        Formula: PL_LOS = C0 + C1*log10(d) + 20*log10(f_GHz)

        where C0 and C1 are scenario-dependent constants.
        """
        scenario_params = self.SCENARIOS[self.scenario]
        C0 = scenario_params['los_path_loss_intercept']
        C1 = scenario_params['los_path_loss_distance_slope']

        pl_los = C0 + C1 * self.xp.log10(distances_m) + 20 * self.xp.log10(f_ghz)

        return pl_los

    def _calculate_path_loss_nlos(
        self,
        f_ghz: float,
        distances_m: np.ndarray,
        h_ue: float
    ) -> np.ndarray:
        """
        Calculate NLOS path loss with height correction.

        Formula: PL_NLOS = C0 + C1*log10(d) + 20*log10(f_GHz) + C2*(h_ue - 1.5)

        where C2 is typically -0.6 dB/meter (negative = taller UE = less loss).
        """
        scenario_params = self.SCENARIOS[self.scenario]
        C0 = scenario_params['nlos_path_loss_intercept']
        C1 = scenario_params['nlos_path_loss_distance_slope']
        C2 = scenario_params['height_correction']

        pl_nlos = (
            C0 +
            C1 * self.xp.log10(distances_m) +
            20 * self.xp.log10(f_ghz) +
            C2 * (h_ue - 1.5)
        )

        return pl_nlos

    def _apply_terrain_correction(
        self,
        distances_m: np.ndarray,
        f_ghz: float,
        terrain_heights: np.ndarray,
        h_bs: float,
        h_ue: float
    ) -> np.ndarray:
        """
        Apply terrain-based diffraction correction (approximate mode).

        Uses a simplified Fresnel-inspired heuristic to estimate additional loss.
        This is intentionally lightweight and does not reconstruct full path profiles.
        """
        # Initialize correction as zeros
        correction = self.xp.zeros_like(distances_m, dtype=float)

        if terrain_heights.size == 0:
            warnings.warn("Terrain heights array is empty, skipping terrain correction")
            return correction

        # Calculate wavelength in meters
        wavelength = 3e8 / (f_ghz * 1e9)  # speed of light / frequency

        # For simplified implementation: assume max terrain elevation as obstruction
        # Real implementation would do full LOS path profiling
        max_terrain_height = self.xp.max(terrain_heights)

        # Effective TX height AGL
        h_tx_agl = h_bs + max_terrain_height

        # Fresnel radius at distance d
        # r_fresnel = sqrt(wavelength * d1 * d2 / (d1 + d2))
        # For symmetric case: r_fresnel ≈ sqrt(wavelength * d / 4)
        fresnel_radius = self.xp.sqrt(wavelength * distances_m / 4.0)

        # Simplified: if terrain blocks significant portion of first Fresnel zone
        # Apply diffraction loss (typical 1-5 dB depending on obstruction)
        # More sophisticated: calculate exact knife-edge diffraction per point

        # Placeholder: apply modest correction when terrain is present
        terrain_present = self.xp.asarray(terrain_heights > 0, dtype=float)
        if self.xp.any(terrain_present):
            # Diffraction loss increases with frequency and decreases with distance
            diffraction_factor = 1.0 + (f_ghz / 28.0) * (1000.0 / (distances_m + 1e-6))
            correction = self.xp.minimum(5.0 * diffraction_factor, 15.0)

        return correction

    def get_breakpoint_distance(self) -> float:
        """
        Calculate breakpoint distance where path loss behavior changes.

        Formula: d_BP = 4 * h_BS * h_UT * f_GHz / c

        where c = 3e8 m/s (speed of light)
        """
        # c in m/GHz·s = 3e8 / 1e9 = 0.3
        d_bp = 4 * self.h_bs * self.h_ue * 0.3  # result in meters

        return d_bp


# Convenience functions for CLI/standalone use
def calculate_3gpp_38901_path_loss(
    distances_km: np.ndarray,
    frequency_mhz: float,
    scenario: str = 'UMa',
    h_bs: float = None,
    h_ue: float = 1.5,
    use_dem: bool = False,
    terrain_heights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Standalone function to calculate 3GPP TR 38.901 path loss.

    Args:
        distances_km (np.ndarray): Distances in km
        frequency_mhz (float): Frequency in MHz
        scenario (str): 'UMa', 'UMi', or 'RMa'
        h_bs (float): Base station height in meters
        h_ue (float): User equipment height in meters (default: 1.5)
        use_dem (bool): Enable deterministic terrain correction
        terrain_heights (np.ndarray): Terrain elevation data

    Returns:
        np.ndarray: Path loss in dB
    """
    # Use scenario-specific default h_bs if not provided
    if h_bs is None:
        h_bs = ThreGPP38901Model.SCENARIOS[scenario]['h_bs_typical']

    config = {
        'scenario': scenario,
        'h_bs': h_bs,
        'h_ue': h_ue,
        'use_dem': use_dem,
    }

    model = ThreGPP38901Model(config)

    return model.calculate_path_loss(
        distances_km,
        frequency_mhz,
        tx_height=h_bs,
        rx_height=h_ue,
        terrain_heights=terrain_heights,
    )
