"""
3GPP TR 38.901 Propagation Model for 5G
Urban Macro (UMa), Urban Micro (UMi), and Rural Macro (RMa) scenarios

Reference: 3GPP TR 38.901 v16.1.0
Standard: Study on Channel Model for Frequencies from 0.5 to 100 GHz

Modos de operacion:
1. Probabilistico: modelo estadistico puro 3GPP
2. Probabilistico + correccion DEM (knife-edge ITU-R P.526, aditivo)

CORRECCIONES v2 (vs implementacion anterior):
  C1: Dual-slope LOS con breakpoint real: d_BP = 4 h_BS h_UT fc/c
  C2: d3D = sqrt(d2D^2 + (h_BS - h_UT)^2) en todas las formulas
  C3: PL_NLOS = max(PL_LOS, PL_NLOS')  -- no doble penalizacion
  C4: LOS probability correcto: UMa C2=63m, UMi C2=36m, RMa exp decay
  C5: RMa con ecuaciones reales del estandar (W, h_avg)
  C6: DEM: correccion aditiva PL += L_diff sin multiplicar por (1-P_LOS)
  C7: Breakpoint incluye frecuencia (antes no la incluia)
"""

import numpy as np
import warnings
from typing import Dict, Tuple, Optional


class ThreGPP38901Model:
    """
    3GPP TR 38.901 v16.1.0 -- implementacion matematicamente correcta.

    Frequency Range: 0.5 GHz - 100 GHz
    Distance Range:  10 m - 10 km (UMa/RMa), 10 m - 5 km (UMi)

    Modos:
        use_dem=False : modelo estadistico puro 3GPP
        use_dem=True  : 3GPP + correccion knife-edge aditiva sobre perfil DEM real
    """

    SCENARIOS = {
        'UMa': {
            'description': 'Urban Macro',
            'h_bs_range': (10, 150),
            'h_bs_typical': 25,
            'distance_range': (10, 10000),
            'shadow_fading_los_db': 4.0,
            'shadow_fading_nlos_db': 6.0,
        },
        'UMi': {
            'description': 'Urban Micro (Street Canyon)',
            'h_bs_range': (10, 150),
            'h_bs_typical': 10,
            'distance_range': (10, 5000),
            'shadow_fading_los_db': 4.0,
            'shadow_fading_nlos_db': 7.82,
        },
        'RMa': {
            'description': 'Rural Macro',
            'h_bs_range': (10, 150),
            'h_bs_typical': 35,
            'distance_range': (10, 10000),
            'shadow_fading_los_db': 4.0,
            'shadow_fading_nlos_db': 8.0,
            'avg_building_height_m': 5.0,
            'street_width_m': 20.0,
        },
    }

    def __init__(self, config: Optional[Dict] = None, numpy_module=None):
        """
        Args:
            config: Diccionario con:
                scenario (str)              : 'UMa', 'UMi' o 'RMa'    [default: 'UMa']
                h_bs (float)                : Altura BS en metros       [default: scenario-specific]
                h_ue (float)                : Altura UE en metros       [default: 1.5]
                use_dem (bool)              : Usar correccion DEM       [default: False]
                max_terrain_correction_db   : Limite difraccion dB      [default: 40]
                dem_profile_samples         : Muestras perfil DEM       [default: 16]
                avg_building_height_m (RMa) : Altura media edificios    [default: 5.0]
                street_width_m (RMa)        : Ancho de calle            [default: 20.0]
        """
        self.config = config or {}
        self.scenario = self.config.get('scenario', 'UMa')

        if self.scenario not in self.SCENARIOS:
            raise ValueError(
                f"Escenario invalido '{self.scenario}'. Validos: {list(self.SCENARIOS)}"
            )

        sp = self.SCENARIOS[self.scenario]
        self.h_bs = float(self.config.get('h_bs', sp['h_bs_typical']))
        self.h_ue = float(self.config.get('h_ue', 1.5))
        self.use_dem = bool(self.config.get('use_dem', False))
        self.max_terrain_correction_db = float(
            self.config.get('max_terrain_correction_db', 40.0)
        )
        self.dem_profile_samples = int(self.config.get('dem_profile_samples', 16))

        # Parametros RMa (pueden sobreescribirse)
        self.h_avg = float(self.config.get(
            'avg_building_height_m', sp.get('avg_building_height_m', 5.0)
        ))
        self.W = float(self.config.get(
            'street_width_m', sp.get('street_width_m', 20.0)
        ))

        self._dem_warning_emitted = False
        self.xp = numpy_module if numpy_module is not None else np

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict:
        """Retorna metadatos del modelo."""
        sp = self.SCENARIOS[self.scenario]
        return {
            'name': '3GPP TR 38.901 (v17.0.0)',
            'scenario': self.scenario,
            'description': sp['description'],
            'frequency_range_ghz': (0.5, 100),
            'distance_range_m': sp['distance_range'],
            'h_bs_m': self.h_bs,
            'h_ue_m': self.h_ue,
            'use_dem': self.use_dem,
            'terrain_mode': (
                'knife_edge_additive' if self.use_dem else 'probabilistic_only'
            ),
            'shadow_fading_los_db': sp['shadow_fading_los_db'],
            'shadow_fading_nlos_db': sp['shadow_fading_nlos_db'],
            'dem_profile_samples': self.dem_profile_samples,
            'max_terrain_correction_db': self.max_terrain_correction_db,
        }

    def calculate_path_loss(
        self,
        distances: np.ndarray,
        frequency: float,
        tx_height: float = None,
        rx_height: float = None,
        terrain_heights: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict:
        """
        Calcula path loss 3GPP TR 38.901.

        Args:
            distances      : Distancias en METROS (array 1D o 2D)
            frequency      : Frecuencia en MHz
            tx_height      : Altura TX en metros (fallback si h_bs no configurado)
            rx_height      : Altura RX en metros (fallback si h_ue no configurado)
            terrain_heights: Elevaciones del terreno 2D [m] (para use_dem=True)
            **kwargs       : h_bs, h_ue (prioridad > tx_height/rx_height),
                             tx_elevation [m MSL]

        Returns:
            dict con 'path_loss' (ndarray), 'validity_mask' (ndarray), 'valid_count' (int)
        """
        # Prioridad: kwargs > parametros > self
        h_bs = float(kwargs.get('h_bs', tx_height if tx_height is not None else self.h_bs))
        h_ue = float(kwargs.get('h_ue', rx_height if rx_height is not None else self.h_ue))

        f_ghz = float(frequency) / 1000.0
        if not (0.5 <= f_ghz <= 100.0):
            warnings.warn(
                f"Frecuencia {f_ghz:.3f} GHz fuera del rango TR 38.901 [0.5, 100] GHz",
                UserWarning,
            )

        xp = self.xp
        d2D = xp.asarray(distances, dtype=float)
        d2D = xp.maximum(d2D, 10.0)  # minimo valido del estandar = 10 m

        # d3D: distancia 3D incluyendo separacion vertical TX-RX
        delta_h = float(h_bs - h_ue)
        d3D = xp.sqrt(d2D ** 2 + delta_h ** 2)

        # Breakpoint (depende de frecuencia y alturas)
        d_bp = self._calculate_breakpoint(h_bs, h_ue, f_ghz)

        # PL_LOS (dual-slope) y PL_NLOS = max(PL_LOS, PL_NLOS')
        pl_los, pl_nlos = self._calculate_los_nlos(d2D, d3D, d_bp, f_ghz, h_bs, h_ue)

        # Probabilidad LOS estadistica
        p_los = self._calculate_los_probability(d2D)

        # Path loss esperado: mezcla P_LOS*PL_LOS + (1-P_LOS)*PL_NLOS
        # PL_NLOS >= PL_LOS por construccion => valor fisicamente intermedio correcto
        path_loss = p_los * pl_los + (1.0 - p_los) * pl_nlos

        # Correccion DEM aditiva (solo cuando h_obs > 0, sin multiplicar por 1-P_LOS)
        if self.use_dem and terrain_heights is not None:
            if not self._dem_warning_emitted:
                warnings.warn(
                    "Modo DEM 3GPP: correccion knife-edge aditiva (ITU-R P.526). "
                    "Solo se aplica cuando h_obstaculo > 0 sobre la linea de vision.",
                    UserWarning,
                )
                self._dem_warning_emitted = True

            terrain_xp = xp.asarray(terrain_heights, dtype=float)
            diffraction = self._apply_terrain_correction(
                d2D, f_ghz, terrain_xp, h_bs, h_ue,
                kwargs.get('tx_elevation', None),
            )
            path_loss = path_loss + diffraction

        validity_mask = xp.isfinite(path_loss)
        return {
            'path_loss': path_loss,
            'validity_mask': validity_mask,
            'valid_count': int(xp.sum(validity_mask)),
        }

    def get_breakpoint_distance(self, frequency_ghz: float = 2.0) -> float:
        """
        Distancia de breakpoint d_BP para la configuracion actual.

        UMa/UMi: d_BP' = 4 * h_BS' * h_UT' * fc / c   (alturas virtuales h' = h - 1 m)
        RMa:     d_BP  = 2*pi * h_BS * h_UT * fc / c   (alturas reales)

        Args:
            frequency_ghz: Frecuencia de referencia [GHz]. Default 2.0 GHz.
        """
        return self._calculate_breakpoint(self.h_bs, self.h_ue, frequency_ghz)

    # ------------------------------------------------------------------
    # Breakpoint distance (TR 38.901 para 7.4.1)
    # ------------------------------------------------------------------

    def _calculate_breakpoint(self, h_bs: float, h_ue: float, f_ghz: float) -> float:
        """
        d_BP segun TR 38.901 7.4.1.

        UMa/UMi: 4 * h_BS' * h_UT' * fc[Hz] / c
                 donde h' = h - 1 m (alturas virtuales, minimo 0.5 m)
        RMa:     2*pi * h_BS * h_UT * fc[Hz] / c
        """
        f_hz = f_ghz * 1e9
        c = 3e8
        if self.scenario == 'RMa':
            return 2.0 * np.pi * h_bs * h_ue * f_hz / c
        else:
            h_bs_v = max(h_bs - 1.0, 0.5)
            h_ue_v = max(h_ue - 1.0, 0.5)
            return 4.0 * h_bs_v * h_ue_v * f_hz / c

    # ------------------------------------------------------------------
    # LOS Probability (TR 38.901 Tabla 7.4.2-1)
    # ------------------------------------------------------------------

    def _calculate_los_probability(self, d2D: np.ndarray) -> np.ndarray:
        """
        Probabilidad de LOS segun TR 38.901 Tabla 7.4.2-1.

        UMa: min(18/d, 1)*(1-exp(-d/63)) + exp(-d/63)
        UMi: min(18/d, 1)*(1-exp(-d/36)) + exp(-d/36)
        RMa: exp(-(d2D - 10) / 1000)
        """
        xp = self.xp
        d = xp.maximum(d2D, 1.0)

        if self.scenario == 'UMa':
            exp_term = xp.exp(-d / 63.0)
            return xp.clip(xp.minimum(18.0 / d, 1.0) * (1.0 - exp_term) + exp_term, 0.0, 1.0)
        elif self.scenario == 'UMi':
            exp_term = xp.exp(-d / 36.0)
            return xp.clip(xp.minimum(18.0 / d, 1.0) * (1.0 - exp_term) + exp_term, 0.0, 1.0)
        else:  # RMa
            return xp.clip(xp.exp(-(d - 10.0) / 1000.0), 0.0, 1.0)

    # ------------------------------------------------------------------
    # Path Loss LOS / NLOS (TR 38.901 Tabla 7.4.1-1)
    # ------------------------------------------------------------------

    def _calculate_los_nlos(
        self,
        d2D: np.ndarray,
        d3D: np.ndarray,
        d_bp: float,
        f_ghz: float,
        h_bs: float,
        h_ue: float,
    ):
        """Calcula (PL_LOS, PL_NLOS) para el escenario configurado."""
        if self.scenario == 'UMa':
            return self._uma_los_nlos(d2D, d3D, d_bp, f_ghz, h_bs, h_ue)
        elif self.scenario == 'UMi':
            return self._umi_los_nlos(d2D, d3D, d_bp, f_ghz, h_bs, h_ue)
        else:
            return self._rma_los_nlos(d2D, d3D, d_bp, f_ghz, h_bs, h_ue)

    def _uma_los_nlos(self, d2D, d3D, d_bp, f_ghz, h_bs, h_ue):
        """
        UMa LOS/NLOS -- TR 38.901 Tabla 7.4.1-1

        LOS dual-slope:
          PL1 = 28.0 + 22*log10(d3D) + 20*log10(fc)    [10m <= d2D <= d_BP']
          PL2 = 28.0 + 40*log10(d3D) + 20*log10(fc)
                - 9*log10(d_BP'^2 + (h_BS-h_UT)^2)     [d_BP' < d2D <= 5000m]

        NLOS:
          PL' = 13.54 + 39.08*log10(d3D) + 20*log10(fc) - 0.6*(h_UT-1.5)
          PL_NLOS = max(PL_LOS, PL')
        """
        xp = self.xp
        log10_d3D = xp.log10(xp.maximum(d3D, 1.0))
        log10_f = float(np.log10(max(f_ghz, 1e-9)))

        # LOS
        pl1 = 28.0 + 22.0 * log10_d3D + 20.0 * log10_f
        pl2 = (28.0 + 40.0 * log10_d3D + 20.0 * log10_f
               - 9.0 * float(np.log10(max(d_bp ** 2 + (h_bs - h_ue) ** 2, 1e-9))))
        pl_los = xp.where(d2D <= d_bp, pl1, pl2)

        # NLOS' y NLOS = max(LOS, NLOS')
        pl_prime = (13.54 + 39.08 * log10_d3D + 20.0 * log10_f - 0.6 * (h_ue - 1.5))
        pl_nlos = xp.maximum(pl_los, pl_prime)

        return pl_los, pl_nlos

    def _umi_los_nlos(self, d2D, d3D, d_bp, f_ghz, h_bs, h_ue):
        """
        UMi Street Canyon LOS/NLOS -- TR 38.901 Tabla 7.4.1-1

        LOS dual-slope:
          PL1 = 32.4 + 21*log10(d3D) + 20*log10(fc)
          PL2 = 32.4 + 40*log10(d3D) + 20*log10(fc)
                - 9.5*log10(d_BP'^2 + (h_BS-h_UT)^2)

        NLOS:
          PL' = 35.3*log10(d3D) + 22.4 + 21.3*log10(fc) - 0.3*(h_UT-1.5)
          PL_NLOS = max(PL_LOS, PL')
        """
        xp = self.xp
        log10_d3D = xp.log10(xp.maximum(d3D, 1.0))
        log10_f = float(np.log10(max(f_ghz, 1e-9)))

        # LOS
        pl1 = 32.4 + 21.0 * log10_d3D + 20.0 * log10_f
        pl2 = (32.4 + 40.0 * log10_d3D + 20.0 * log10_f
               - 9.5 * float(np.log10(max(d_bp ** 2 + (h_bs - h_ue) ** 2, 1e-9))))
        pl_los = xp.where(d2D <= d_bp, pl1, pl2)

        # NLOS' y NLOS = max(LOS, NLOS')
        pl_prime = (35.3 * log10_d3D + 22.4 + 21.3 * log10_f - 0.3 * (h_ue - 1.5))
        pl_nlos = xp.maximum(pl_los, pl_prime)

        return pl_los, pl_nlos

    def _rma_los_nlos(self, d2D, d3D, d_bp, f_ghz, h_bs, h_ue):
        """
        RMa LOS/NLOS -- TR 38.901 Tabla 7.4.1-1

        Coeficientes:
          A = min(0.03*h^1.72, 10)
          B = min(0.044*h^1.72, 14.77)
          C = 0.002*log10(h)
          (h = altura media de edificios en metros)

        LOS dual-slope:
          PL1 = 20*log10(40*pi*d3D*fc/3) + A*log10(d3D) - B + C*d3D
          PL2 = PL1(d_BP) + 40*log10(d3D/d3D_BP)

        NLOS:
          PL' = 161.04 - 7.1*log10(W) + 7.5*log10(h)
                - (24.37 - 3.7*(h/h_BS)^2)*log10(h_BS)
                + (43.42 - 3.1*log10(h_BS))*(log10(d3D) - 3)
                + 20*log10(fc) - (3.2*(log10(11.75*h_UT))^2 - 4.97)
          PL_NLOS = max(PL_LOS, PL')
        """
        xp = self.xp
        h = max(self.h_avg, 0.1)
        W = max(self.W, 1.0)

        A = min(0.03 * h ** 1.72, 10.0)
        B = min(0.044 * h ** 1.72, 14.77)
        C = 0.002 * np.log10(h)

        d3D_safe = xp.maximum(d3D, 1.0)
        log10_f = float(np.log10(max(f_ghz, 1e-9)))

        # PL1
        pl1 = (20.0 * xp.log10(40.0 * np.pi * d3D_safe * f_ghz / 3.0)
               + A * xp.log10(d3D_safe) - B + C * d3D_safe)

        # PL2: PL1 en d_BP + 40*log10(d3D/d3D_BP)
        d_bp_safe = max(float(d_bp), 1.0)
        d3D_bp = float(np.sqrt(d_bp_safe ** 2 + (h_bs - h_ue) ** 2))
        pl1_at_bp = (20.0 * np.log10(40.0 * np.pi * d3D_bp * f_ghz / 3.0)
                     + A * np.log10(d3D_bp) - B + C * d3D_bp)
        pl2 = pl1_at_bp + 40.0 * xp.log10(xp.maximum(d3D_safe / d3D_bp, 1e-9))

        pl_los = xp.where(d2D <= d_bp, pl1, pl2)

        # NLOS' y NLOS = max(LOS, NLOS')
        pl_prime = (
            161.04
            - 7.1 * np.log10(W)
            + 7.5 * np.log10(h)
            - (24.37 - 3.7 * (h / h_bs) ** 2) * np.log10(h_bs)
            + (43.42 - 3.1 * np.log10(h_bs)) * (xp.log10(d3D_safe) - 3.0)
            + 20.0 * log10_f
            - (3.2 * (np.log10(11.75 * h_ue)) ** 2 - 4.97)
        )
        pl_nlos = xp.maximum(pl_los, pl_prime)

        return pl_los, pl_nlos

    # ------------------------------------------------------------------
    # Helpers de compatibilidad (usados en tests existentes)
    # ------------------------------------------------------------------

    def _calculate_path_loss_los(
        self, f_ghz: float, distances_m: np.ndarray, h_ue: float
    ) -> np.ndarray:
        """PL_LOS (metros). Mantenido por compatibilidad con tests."""
        d2D = self.xp.maximum(self.xp.asarray(distances_m, dtype=float), 10.0)
        d3D = self.xp.sqrt(d2D ** 2 + (self.h_bs - h_ue) ** 2)
        d_bp = self._calculate_breakpoint(self.h_bs, h_ue, f_ghz)
        pl_los, _ = self._calculate_los_nlos(d2D, d3D, d_bp, f_ghz, self.h_bs, h_ue)
        return pl_los

    def _calculate_path_loss_nlos(
        self, f_ghz: float, distances_m: np.ndarray, h_ue: float
    ) -> np.ndarray:
        """PL_NLOS (metros). Mantenido por compatibilidad con tests."""
        d2D = self.xp.maximum(self.xp.asarray(distances_m, dtype=float), 10.0)
        d3D = self.xp.sqrt(d2D ** 2 + (self.h_bs - h_ue) ** 2)
        d_bp = self._calculate_breakpoint(self.h_bs, h_ue, f_ghz)
        _, pl_nlos = self._calculate_los_nlos(d2D, d3D, d_bp, f_ghz, self.h_bs, h_ue)
        return pl_nlos

    # ------------------------------------------------------------------
    # Correccion de terreno DEM (modo use_dem=True)
    # ------------------------------------------------------------------

    def _apply_terrain_correction(
        self,
        d2D: np.ndarray,
        f_ghz: float,
        terrain_heights: np.ndarray,
        h_bs: float,
        h_ue: float,
        tx_elevation: Optional[float] = None,
    ) -> np.ndarray:
        """
        Correccion knife-edge ITU-R P.526 sobre perfil DEM.

        Diferencias vs implementacion anterior:
          - Correccion ADITIVA: PL += L_diff
          - L_diff > 0 solo cuando h_obs > 0 (obstaculo real sobre linea de vision)
          - NO se multiplica por (1-P_LOS): terreno y estadistica urbana son ortogonales
        """
        xp = self.xp
        correction = xp.zeros_like(d2D, dtype=float)

        if terrain_heights.size == 0:
            return correction

        if terrain_heights.ndim != 2 or d2D.ndim != 2:
            warnings.warn("Correccion DEM requiere arrays 2D. Omitiendo.", UserWarning)
            return correction

        rows, cols = terrain_heights.shape
        samples = max(self.dem_profile_samples, 4)

        tx_flat_idx = int(xp.argmin(d2D))
        tx_row = tx_flat_idx // cols
        tx_col = tx_flat_idx % cols

        t = xp.linspace(0.0, 1.0, samples)
        row_idx = xp.arange(rows).reshape(rows, 1)
        col_idx = xp.arange(cols).reshape(1, cols)

        sample_rows = xp.clip(
            xp.rint(tx_row + t[:, None, None] * (row_idx[None] - tx_row)).astype(np.int64),
            0, rows - 1,
        )
        sample_cols = xp.clip(
            xp.rint(tx_col + t[:, None, None] * (col_idx[None] - tx_col)).astype(np.int64),
            0, cols - 1,
        )

        terrain_profile = terrain_heights[sample_rows, sample_cols]

        tx_ground = (
            float(terrain_heights[tx_row, tx_col])
            if tx_elevation is None
            else float(tx_elevation)
        )
        tx_abs = tx_ground + h_bs
        rx_abs = terrain_heights + h_ue
        los_line = tx_abs + t[:, None, None] * (rx_abs[None] - tx_abs)

        clearance = terrain_profile - los_line
        clearance[0, :, :] = -1e9
        clearance[-1, :, :] = -1e9

        h_obs = xp.max(clearance, axis=0)
        t_obs = xp.take(t, xp.argmax(clearance, axis=0))

        wavelength_m = 3e8 / (f_ghz * 1e9)
        d = xp.maximum(d2D, 1.0)
        d1 = xp.maximum(t_obs * d, 1.0)
        d2_seg = xp.maximum((1.0 - t_obs) * d, 1.0)

        # Parametro knife-edge ITU-R P.526
        v = h_obs * xp.sqrt(2.0 * (d1 + d2_seg) / (wavelength_m * d1 * d2_seg))

        knife_loss = xp.where(
            v <= -0.78,
            0.0,
            6.9 + 20.0 * xp.log10(xp.sqrt((v - 0.1) ** 2 + 1.0) + v - 0.1),
        )

        # Solo aplicar donde hay obstruccion real (h_obs > 0)
        knife_loss = xp.where(h_obs > 0.0, xp.maximum(knife_loss, 0.0), 0.0)
        return xp.minimum(knife_loss, self.max_terrain_correction_db)


# ------------------------------------------------------------------
# Funcion de conveniencia standalone
# ------------------------------------------------------------------

def calculate_3gpp_38901_path_loss(
    distances_m: np.ndarray,
    frequency_mhz: float,
    scenario: str = 'UMa',
    h_bs: float = None,
    h_ue: float = 1.5,
    use_dem: bool = False,
    terrain_heights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Calcula path loss 3GPP TR 38.901.

    Args:
        distances_m   : Distancias en METROS
        frequency_mhz : Frecuencia en MHz
        scenario      : 'UMa', 'UMi' o 'RMa'
        h_bs          : Altura BS metros (default: scenario-specific)
        h_ue          : Altura UE metros (default: 1.5)
        use_dem       : Activar correccion DEM
        terrain_heights: Elevaciones del terreno 2D [m]

    Returns:
        np.ndarray: Path loss en dB
    """
    if h_bs is None:
        h_bs = ThreGPP38901Model.SCENARIOS[scenario]['h_bs_typical']

    model = ThreGPP38901Model(
        config={'scenario': scenario, 'h_bs': h_bs, 'h_ue': h_ue, 'use_dem': use_dem}
    )
    result = model.calculate_path_loss(
        distances_m, frequency_mhz,
        terrain_heights=terrain_heights,
    )
    return result['path_loss']
