"""
ITU-R P.1546-6 Propagation Model

Modelo punto-a-área para predicciones de cobertura terrestre.

ARQUITECTURA:
1. h_eff (altura efectiva TX) — P.1546-6 §4.3
   - Con DEM: z_mean del perfil en el rango 3–15 km desde TX
   - Sin DEM o d < 15 km: h_eff = h_tx_AGL (regla §4.3)
2. Interpolación E[dBμV/m] — Tablas de referencia P.1546-6 (Figs. 1–3)
   - 3D log-lineal: frecuencia × distancia × altura efectiva
   - Tablas internas: 100 / 600 / 2000 MHz; 1–1000 km; 10–1200 m
   - Extrapolación log para frecuencias fuera de ese rango
3. TCA correction — P.1546-6 §4.5 (Annex 5 §12)
   - θ_tc = max(arctan((h_terrain − h_rx) / d_from_rx)) dentro de ±15 km del RX
   - Corrección: J(θ_tc) = 6.9 + 20·log₁₀(√((θ−0.1)²+1) + θ−0.1)  [θ en grados]
   - Aplicada solo cuando θ_tc > 0° (obstáculo sobre la horizontal del RX)
   - NOTA: curvatura terrestre no incluida en el perfil (impacto en d > 50 km)
4. Clutter loss — ITU-R P.2108-1 §3 (modelo separado, más reciente que P.1546 Annex 5)
   - L = 10.25·F_fc·exp(−d_t)·(1 − tanh(6·(h_b/h_g − 0.625))) − 0.33
   - d_t estimado desde DEM (ventana 5 km alrededor del RX) o por defecto de entorno
5. Conversión E → PL — P.1546-6 §5
   - PL = 139.3 + 20·log₁₀(f_MHz) − E + TCA_correction + clutter_loss + percentile_adj
6. Percentile correction — P.1546-6 §8.1
   - Suma algebraica de correcciones de tiempo y ubicación (tablas ITU Annex 5)
   - Percentiles disponibles en tablas: 1, 10, 50, 90, 99

RANGOS VÁLIDOS:
- Frecuencia: 30–4000 MHz (tablas internas: 100–2000 MHz; fuera de ese rango se extrapola)
- Distancia: 1–1000 km (d < 1 km clipeada a 1 km)
- h_eff TX: 10–1200 m (extrapolación log-lineal para h < 10 m)

ESTÁNDARES REFERENCIADOS:
- ITU-R P.1546-6 (August 2019): tabla base, §4.3 h_eff, §4.5 TCA, §8.1 percentiles
- ITU-R P.2108-1: corrección de clutter terrestre
https://www.itu.int/rec/R-REC-P.1546-6-201908-I/en

Autores: David Montano, Dario Portilla
Universidad de Cuenca, 2025
"""

import numpy as np
import logging
from typing import Dict, Any, Optional

from .itu_r_p1546_tables import get_reference_field_intensity, get_model_tables_info, get_percentile_correction
from .clutter_model import ClutterModel


class ITUR_P1546Model:
    """
    Implementación del modelo ITU-R P.1546-6 — predicción punto-a-área.

    COMPONENTES:
    1. Tablas ITU-R P.1546-6: Interpolación E[dBμV/m] log-lineal 3D
       (frecuencia × distancia × h_eff; 100/600/2000 MHz × 1–1000 km × 10–1200 m)
    2. TCA correction §4.5: J(θ_tc) con θ_tc en grados — definida directamente
       en el estándar P.1546-6; no involucra el parámetro Fresnel de P.526
    3. Clutter loss: ITU-R P.2108-1 §3 (modelo separado, complementario a P.1546)
    4. Percentile corrections §8.1: suma algebraica de tablas ITU Annex 5

    LIMITACIONES CONOCIDAS:
    - Curvatura terrestre no aplicada sobre los perfiles DEM (efecto relevante en d > 50 km)
    - Percentiles discretizados a {1, 10, 50, 90, 99} (únicos valores en tablas ITU)
    - Extrapolación log fuera del rango 100–2000 MHz puede introducir error
    - Perfil de difracción simplificado a 2D (trayecto radial único por receptor)
    - Validación con datos de campo: pendiente
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 compute_module=None):
        """
        Inicializa modelo ITU-R P.1546-6
        
        Args:
            config: Diccionario de configuración (opcional)
            compute_module: np (CPU) o cp (GPU CuPy). Default: np
        """
        self.name = "ITU-R P.1546"
        self.model_type = "Point-to-Area Empirical (Corrected)"
        self.config = config or {}
        
        # Abstracción CPU/GPU
        self.xp = compute_module if compute_module is not None else np
        
        # Logger
        self.logger = logging.getLogger(f"models.{self.name}")
        
        # Parámetros por defecto
        self.defaults = {
            'environment': 'Urban',        # Urban/Suburban/Rural
            'terrain_type': 'mixed',       # smooth/mixed/irregular
            'mobile_height': 1.5,         # Altura receptor (m AGL)
            'temporal_percentage': 50,    # 50% de tiempo
            'location_percentage': 50,    # 50% de ubicación
            'erp_dbm': 0.0,              # ERP normalizado (dBm)
        }
        
        self.defaults.update(self.config)
        
        # Parámetros ITU
        self.tables_info = get_model_tables_info()
        
        # Rangos de terreno para h_eff
        self.inner_radius_km = 3.0
        self.outer_radius_km = 15.0
        self.terrain_min_samples = 3  # Mínimo de muestras para h_eff
        
        # Alturas de clutter por ambiente
        self.clutter_heights_m = {
            'urban': 20.0,
            'suburban': 10.0,
            'rural': 4.0,
        }
        
        self.logger.info(f"Initialized {self.name}")
        self.logger.info(f"Compute module: {self.xp.__name__}")
        self.logger.info(f"Defaults: {self.defaults}")
    
    
    def calculate_path_loss(self,
                           distances: np.ndarray,
                           frequency: float,
                           tx_height: float,
                           terrain_heights: np.ndarray,
                           tx_elevation: float = 0.0,
                           terrain_profiles: Optional[np.ndarray] = None,
                           environment: str = 'Urban',
                           mobile_height: float = 1.5,
                           time_percentage: int = 50,
                           location_percentage: int = 50,
                           smoothed_terrain_profiles: Optional[np.ndarray] = None,
                           profile_distances: Optional[np.ndarray] = None,
                           **kwargs) -> np.ndarray:
        """
        Calcula Path Loss usando ITU-R P.1546-6.

        PIPELINE (5 pasos):
        1. h_eff por receptor — §4.3
           Si d < 15 km o sin DEM: h_eff = h_tx_AGL.
           Si d ≥ 15 km con DEM: h_eff = h_tx + z_tx − z_mean(3–15 km).
        2. E[dBμV/m] — interpolación bilineal log-lineal sobre tablas ITU.
        3. TCA correction — §4.5
           J(θ_tc) aplicada cuando θ_tc > 0° (sólo si hay perfiles DEM).
        4. Clutter loss — ITU-R P.2108-1 §3
           Basada en entorno (Urban/Suburban/Rural) y altura del receptor.
        5. Conversión E → PL — §5
           PL = 139.3 + 20·log₁₀(f_MHz) − E + TCA + clutter + percentile

        Args:
            distances: Distancias en metros (1D o 2D, n_receptors)
            frequency: Frecuencia en MHz (30–4000; tablas internas: 100–2000)
            tx_height: Altura TX en metros AGL
            terrain_heights: Elevaciones del terreno en cada receptor [m AMSL]
            tx_elevation: Elevación del sitio TX [m AMSL], default 0
            terrain_profiles: Perfiles radiales DEM (n_receptors, n_radios) [m AMSL]
            environment: 'Urban' | 'Suburban' | 'Rural'
            mobile_height: Altura receptor AGL [m], default 1.5
            time_percentage: Percentil de tiempo [1–99], default 50
            location_percentage: Percentil de ubicación [1–99], default 50
            smoothed_terrain_profiles: Perfiles suavizados (n_receptors, n_radios)
                Si se proporciona, se usa en lugar de terrain_profiles para h_eff.
            profile_distances: Distancias TX→punto en cada perfil (n_receptors, n_radios) [m]
            **kwargs: Parámetros adicionales ignorados

        Returns:
            np.ndarray: Path loss en dB, misma forma que distances
        """
        # Guardar forma original
        original_shape = distances.shape
        
        # Convertir a arrays
        distances_flat = self.xp.atleast_1d(distances).flatten().astype(float)
        terrain_heights_flat = self.xp.atleast_1d(terrain_heights).flatten().astype(float)
        
        n_receptors = len(distances_flat)
        
        # DEBUG: Mostrar qué parámetros se reciben
        has_terrain_profiles = terrain_profiles is not None
        has_profile_distances = profile_distances is not None
        has_smoothed_profiles = smoothed_terrain_profiles is not None
        
        self.logger.debug(f"calculate_path_loss: {n_receptors} receptors @ {frequency} MHz")
        self.logger.debug(f"  terrain_profiles={has_terrain_profiles}, profile_distances={has_profile_distances}")
        self.logger.debug(f"  tx: {tx_elevation:.1f} m MSL, {tx_height:.1f} m AGL")
        
        # === PASO 1: Calcular altura efectiva h_eff (FASE 2 mejorado) ===
        # FASE 2: Si se proporciona smoothed_terrain_profiles, usarlo; sino usar raw
        terrain_profiles_to_use = smoothed_terrain_profiles if smoothed_terrain_profiles is not None else terrain_profiles
        
        h_eff = self._calculate_effective_height_vectorized(
            distances=distances_flat,
            tx_height=tx_height,
            tx_elevation=tx_elevation,
            terrain_heights=terrain_heights_flat,
            terrain_profiles=terrain_profiles_to_use,
            profile_distances=profile_distances
        )
        
        # Convertir distancias a km
        distances_km = distances_flat / 1000.0
        
        # === BUG #7 FIX: Protección distancia mínima 1 km (P.1546 válido solo para d > 1 km) ===
        distances_km = self.xp.maximum(distances_km, 1.0)
        n_clipped = int(self.xp.sum(distances_km <= 1.0001))
        if n_clipped > 0:
            self.logger.debug(f"[P.1546 Boundary Fix] {n_clipped} distancias clipeadas a 1.0 km (mínimo P.1546)")
        
        # === PASO 2: Interpolar E[dBμV/m] desde tablas ITU ===
        E_field = self._interpolate_field_intensity(
            frequency=frequency,
            distances_km=distances_km,
            h_eff=h_eff
        )
        
        # === PASO 3: TCA correction — P.1546-6 §4.5 (solo si hay perfiles DEM) ===
        if terrain_profiles is not None and terrain_profiles.shape[0] == n_receptors:
            tca_correction = self._calculate_tca_correction_vectorized(
                terrain_profiles=terrain_profiles,
                distances_km=distances_km,
                tx_height=tx_height,
                tx_elevation=tx_elevation,
                terrain_heights=terrain_heights_flat,
                mobile_height=mobile_height,
                profile_distances=profile_distances,
                h_eff=h_eff,
                frequency=frequency
            )
        else:
            tca_correction = self.xp.zeros(n_receptors, dtype=float)
            self.logger.debug("TCA: sin terrain_profiles, usando 0 dB")
        
        # === PASO 4: Aplicar correcciones ===
        
        # 4a. Clutter correction realista (FASE 4 - basada en morphology ITU)
        clutter_correction = self._calculate_clutter_correction_vectorized(
            terrain_profiles=terrain_profiles,
            profile_distances=profile_distances,
            distances_km=distances_km,
            rx_height=mobile_height,
            environment=environment,
            frequency=frequency
        )
        
        # 4b. Terminal clearance: no aplicado (cubierto por TCA §4.5)
        terminal_clearance = None

        # 4c. Percentile correction — P.1546-6 §8.1 (tablas ITU Annex 5)
        percentile_correction = self._apply_percentile_correction(
            distances_km=distances_km,
            time_percentage=time_percentage,
            location_percentage=location_percentage,
            frequency=frequency
        )
        
        # === PASO 5: Convertir E → Path Loss ===
        path_loss = self._convert_field_to_path_loss(
            E_field=E_field,
            frequency=frequency,
            h_eff=h_eff,
            tca_correction=tca_correction,
            clutter_correction=clutter_correction,
            terminal_clearance=terminal_clearance,
            percentile_correction=percentile_correction
        )
        
        # Remodelar al shape original
        path_loss_shaped = path_loss.reshape(original_shape)
        
        # Validar valores finales
        validity_mask = self.xp.isfinite(path_loss_shaped) & (path_loss_shaped > 0)
        valid_count = int(self.xp.sum(validity_mask))

        self.logger.debug(f"Path loss: min={self.xp.min(path_loss_shaped):.1f} dB, "
                         f"max={self.xp.max(path_loss_shaped):.1f} dB, "
                         f"valid={valid_count}/{n_receptors}")

        return path_loss_shaped
    
    
    def _calculate_effective_height_vectorized(self,
                                               distances: np.ndarray,
                                               tx_height: float,
                                               tx_elevation: float,
                                               terrain_heights: np.ndarray,
                                               terrain_profiles: Optional[np.ndarray] = None,
                                               profile_distances: Optional[np.ndarray] = None
                                               ) -> np.ndarray:
        """
        Calcula altura efectiva h_eff para cada receptor — P.1546-6 §4.3 (vectorizado).

        h_eff = h_tx + z_tx - z_mean(3–15 km)

        Regla §4.3: si d < 15 km → h1 = h_tx_AGL (no depende del DEM).
        Si terrain_profiles es None → h1 = h_tx_AGL para todos (modo sin DEM).

        Args:
            distances: Distancias en metros (n_receptors,)
            tx_height: Altura TX en metros AGL
            tx_elevation: Elevación TX en msnm
            terrain_heights: Elevaciones puntuales (n_receptors,)
            terrain_profiles: Perfiles radiales (n_receptors, n_radios) — opcional
            profile_distances: Distancias reales en metros (n_receptors, n_radios) — opcional
        Returns:
            Array h_eff (n_receptors,), clipeado [-3000, 1200] m
        """
        xp = self.xp
        n_receptors = len(distances)

        # --- Caso sin DEM: P.1546-6 §4.3 permite h1 = h_tx_AGL ---
        if terrain_profiles is None or terrain_profiles.shape[0] != n_receptors:
            self.logger.debug("h_eff: sin perfiles DEM — usando h_tx_AGL para todos los receptores")
            return xp.full(n_receptors, float(tx_height))

        n_radios = terrain_profiles.shape[1]

        # Distancias radiales: usar profile_distances si están disponibles, sino linspace
        if profile_distances is not None:
            # profile_distances: (n_receptors, n_radios) en metros
            radial_dist_m = profile_distances   # (n_receptors, n_radios)
        else:
            inner_m = self.inner_radius_km * 1000.0  # 3000 m
            outer_m = self.outer_radius_km * 1000.0  # 15000 m
            radial_dist_m = xp.tile(
                xp.linspace(inner_m, outer_m, n_radios),
                (n_receptors, 1)
            )  # (n_receptors, n_radios)

        # --- Máscara ITU-R P.1546-6 §4.3: rango 3–15 km ---
        inner_m = self.inner_radius_km * 1000.0  # 3000 m
        outer_m = self.outer_radius_km * 1000.0  # 15000 m
        mask_range = (radial_dist_m >= inner_m) & (radial_dist_m <= outer_m)  # (n_receptors, n_radios)

        # Contar muestras en rango por receptor
        count_in_range = xp.sum(mask_range.astype(float), axis=1)  # (n_receptors,)

        # z_mean vectorizado: evitar nanmean (no disponible en CuPy)
        # Para receptores con suficientes muestras: usar promedio en rango
        # Para receptores sin muestras: usar media global del perfil
        profiles_in_range = xp.where(mask_range, terrain_profiles, 0.0)
        z_mean_range = xp.where(
            count_in_range > 0,
            profiles_in_range.sum(axis=1) / xp.maximum(count_in_range, 1.0),
            terrain_profiles.mean(axis=1)  # fallback: media global
        )  # (n_receptors,)

        # h_eff_dem = h_tx + z_tx - z_mean
        z_tx = float(tx_elevation)
        h_eff_dem = tx_height + z_tx - z_mean_range  # (n_receptors,)

        # --- P.1546-6 §4.3: si d < 15 km → h1 = h_tx_AGL ---
        short_path = distances < (self.outer_radius_km * 1000.0)  # d < 15 000 m
        h_eff_array = xp.where(short_path, float(tx_height), h_eff_dem)

        # Clipear a rango físicamente válido P.1546
        h_eff_array = xp.clip(h_eff_array, -3000.0, 1200.0)

        self.logger.debug(
            f"h_eff: min={float(xp.min(h_eff_array)):.1f} m, "
            f"max={float(xp.max(h_eff_array)):.1f} m, "
            f"mean={float(xp.mean(h_eff_array)):.1f} m"
        )
        return h_eff_array
    
    
    def _interpolate_field_intensity(self,
                                    frequency: float,
                                    distances_km: np.ndarray,
                                    h_eff: np.ndarray) -> np.ndarray:
        """
        Interpola intensidad de campo E[dBμV/m] desde tablas ITU
        
        Usa get_reference_field_intensity() que hace interpolación 3D:
        - Frecuencia: log-linear entre 100/600/2000 MHz
        - Distancia: log-linear
        - Altura: lineal
        
        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km (n_receptors,)
            h_eff: Alturas efectivas en m (n_receptors,)
            
        Returns:
            Array E[dBμV/m] (n_receptors,)
        """
        # Llamar a función de interpolación ITU
        E_field = get_reference_field_intensity(
            frequency=frequency,
            distance_km=distances_km,
            h_eff_m=h_eff,
            xp=np  # Tablas ITU siempre en NumPy
        )
        
        self.logger.debug(
            f"E_field: f={frequency} MHz, "
            f"h_eff=[{float(h_eff.min()):.1f},{float(h_eff.max()):.1f}] m, "
            f"d=[{float(distances_km.min()):.2f},{float(distances_km.max()):.2f}] km, "
            f"E=[{float(E_field.min()):.2f},{float(E_field.max()):.2f}] dBμV/m"
        )
        
        # Convertir a xp si es necesario (GPU)
        if self.xp.__name__ == 'cupy':
            E_field = self.xp.asarray(E_field)
        
        return E_field
    
    
    def _calculate_tca_correction_vectorized(self,
                                            terrain_profiles: np.ndarray,
                                            distances_km: np.ndarray,
                                            tx_height: float,
                                            tx_elevation: float,
                                            terrain_heights: np.ndarray,
                                            mobile_height: float = 1.5,
                                            profile_distances: Optional[np.ndarray] = None,
                                            h_eff: Optional[np.ndarray] = None,
                                            frequency: float = 900.0) -> np.ndarray:
        """
        Terrain Clearance Angle correction — ITU-R P.1546-6 §4.5 (Annex 5 §12).

        Procedimiento según el estándar:
        1. Para cada receptor, buscar en el perfil de terreno (ventana 0–15 km
           desde el RX) el punto que forme el mayor ángulo de elevación positivo
           con respecto a la horizontal del receptor.
        2. θ_tc = max(arctan((h_terrain − h_rx) / d_from_rx))  [grados]
        3. Si θ_tc > 0° (el terreno supera la horizontal del RX):
           J(θ_tc) = 6.9 + 20·log₁₀(√((θ_tc − 0.1)² + 1) + θ_tc − 0.1)  [dB]
        4. Si θ_tc ≤ 0°: corrección = 0 dB.

        NOTA: J(θ) es la función de corrección definida directamente en P.1546-6 §4.5
        con θ en grados. Aunque la forma matemática se asemeja a la aproximación
        knife-edge de P.526, en P.1546 el argumento es el TCA (°) y no el
        parámetro de Fresnel adimensional v.

        NOTA: Los perfiles DEM no incluyen corrección de curvatura terrestre.
        Para trayectos > 50 km esto puede subestimar la altura de obstáculos.

        Args:
            terrain_profiles: (n_receptors, n_radios) — elevación [m AMSL]
            distances_km: (n_receptors,) — distancia TX→RX [km]
            tx_height: no usado en §4.5 (conservado para firma uniforme)
            tx_elevation: no usado en §4.5 (conservado para firma uniforme)
            terrain_heights: (n_receptors,) — elevación AMSL del receptor [m]
            mobile_height: Altura receptor AGL [m], default 1.5
            profile_distances: (n_receptors, n_radios) — distancias TX→punto [m]
            h_eff: no usado en §4.5 (conservado para firma uniforme)
            frequency: no usado en §4.5 (conservado para firma uniforme)
        Returns:
            np.ndarray: correcciones TCA [dB] (n_receptors,), valores ≥ 0
        """
        xp = self.xp
        n_receptors = len(distances_km)

        # Sin perfiles de terreno: sin corrección TCA
        if terrain_profiles is None or terrain_profiles.shape[0] != n_receptors:
            return xp.zeros(n_receptors, dtype=float)

        # Sin distancias de perfil: no podemos calcular d_desde_rx
        if profile_distances is None:
            self.logger.debug("TCA §4.5: profile_distances no disponible, sin corrección")
            return xp.zeros(n_receptors, dtype=float)

        distances_m = distances_km * 1000.0  # (n_receptors,)

        # Distancia de cada punto del perfil al receptor [m]
        # d_from_rx[i, j] = distancia TX→RX[i] - distancia TX→punto[i,j]
        d_from_rx = distances_m[:, None] - profile_distances  # (n_receptors, n_radios)

        # Ventana §4.5: últimos 15 km antes del receptor
        near_rx = (d_from_rx >= 0.0) & (d_from_rx <= 15000.0)  # (n, nr)

        # Elevación absoluta del receptor [m AMSL]
        H_rx = terrain_heights + mobile_height  # (n_receptors,)

        # Diferencia de altura: terreno - receptor [m]
        delta_h = terrain_profiles - H_rx[:, None]  # (n, nr)

        # Distancia horizontal segura (evitar /0)
        d_horiz = xp.maximum(d_from_rx, 1.0)  # (n, nr)

        # Ángulo de elevación en grados para cada punto del perfil
        theta_i = xp.degrees(xp.arctan2(delta_h, d_horiz))  # (n, nr)

        # Enmascarar puntos fuera de ventana con valor muy negativo
        theta_masked = xp.where(near_rx, theta_i, xp.full_like(theta_i, -1e9))

        # TCA = máximo ángulo de elevación dentro de ventana
        theta_tc = xp.max(theta_masked, axis=1)  # (n_receptors,)
        theta_tc = xp.maximum(theta_tc, 0.0)  # solo corrección cuando hay obstáculo

        # J(θ_tc) — función de corrección definida en P.1546-6 §4.5; θ_tc en grados
        t = theta_tc - 0.1
        J_theta = 6.9 + 20.0 * xp.log10(
            xp.maximum(xp.sqrt(t * t + 1.0) + t, 1e-6)
        )
        tca_db = xp.where(theta_tc > 0.0, J_theta, 0.0)

        self.logger.debug(
            f"TCA §4.5: θ_tc min={float(xp.min(theta_tc)):.2f}° "
            f"max={float(xp.max(theta_tc)):.2f}°, "
            f"J(θ) mean={float(xp.mean(tca_db)):.2f} dB"
        )
        return tca_db
    
    
    def _calculate_clutter_correction_vectorized(self,
                                                terrain_profiles: Optional[np.ndarray] = None,
                                                profile_distances: Optional[np.ndarray] = None,
                                                environment: str = 'Urban',
                                                distances_km: np.ndarray = None,
                                                rx_height: float = 1.5,
                                                frequency: float = 900.0) -> np.ndarray:
        """
        Corrección por clutter — ITU-R P.2108-1 §3 (vectorizado, via ClutterModel).

        Args:
            terrain_profiles: Perfiles radiales (n_receptors, n_radios)
            profile_distances: Distancias Haversine reales (n_receptors, n_radios) [m]
            environment: Urban/Suburban/Rural
            distances_km: Distancias en km (n_receptors,)
            rx_height: Altura receptor AGL [m]
            frequency: Frecuencia en MHz (requerida por P.2108-1)
        Returns:
            Array de correcciones en dB (n_receptors,)
        """
        n_receptors = len(distances_km) if distances_km is not None else 0
        if n_receptors == 0:
            return self.xp.zeros(0, dtype=float)

        clutter = ClutterModel(xp=self.xp)
        distances_m = distances_km * 1000.0

        clutter_correction = clutter.calculate_clutter_correction_vectorized(
            terrain_profiles=terrain_profiles,
            profile_distances=profile_distances,
            distances_m=distances_m,
            h_rx_agl=rx_height,
            environment=environment.lower() if environment else None,
            frequency_mhz=frequency
        )

        return clutter_correction
    
    
    
    def _apply_percentile_correction(self,
                                    distances_km: np.ndarray,
                                    time_percentage: int,
                                    location_percentage: int,
                                    frequency: float) -> np.ndarray:
        """
        Corrección por percentil temporal y de ubicación — P.1546-6 §8.1.

        El estándar define que las correcciones de tiempo y ubicación se combinan
        sumándolas algebraicamente (§8.1: "adding the two corrections algebraically").

        Los factores se obtienen de las tablas del Annex 5 de P.1546-6.
        Los únicos percentiles disponibles en esas tablas son: 1, 10, 50, 90, 99.
        Percentiles intermedios se aproximan al valor de tabla más cercano disponible
        (p.ej.: 5 % → 10 %, 25 % → 10 %, 75 % → 90 %).

        Corrección total:
            corr_time     = tabla_ITU(time_percentage, 'time')
            corr_location = tabla_ITU(location_percentage, 'location')
            total = corr_time + corr_location  [dB, suma algebraica per §8.1]

        Valores de referencia (50 % = 0 dB):
            p=1 %  → +3.09 dB  (condición favorecida)
            p=99 % → −3.09 dB  (condición desfavorable)

        Args:
            distances_km: Distancias en km (n_receptors,)
            time_percentage: Percentil de tiempo [1–99], default 50
            location_percentage: Percentil de ubicación [1–99], default 50
            frequency: Frecuencia en MHz (no usado; conservado para firma uniforme)

        Returns:
            np.ndarray: corrección en dB (n_receptors,), constante por receptor
        """
        n = len(distances_km)
        
        # Si es 50/50, sin corrección
        if time_percentage == 50 and location_percentage == 50:
            return self.xp.zeros(n, dtype=float)
        
        # Obtener factores de percentil desde tablas ITU (FASE B1 FIX)
        # Usar percentiles disponibles: 1, 10, 50, 90, 99
        time_pct = max(1, min(99, time_percentage))
        loc_pct = max(1, min(99, location_percentage))
        
        # Mapear percentiles no estándar a los disponibles
        percentile_map = {1: 1, 5: 10, 10: 10, 25: 10, 50: 50, 75: 90, 90: 90, 95: 90, 99: 99}
        time_pct_mapped = percentile_map.get(time_pct, time_pct)
        loc_pct_mapped = percentile_map.get(loc_pct, loc_pct)
        
        try:
            # Obtener correcciones desde tablas ITU reales
            factor_time = get_percentile_correction(time_pct_mapped, 'time')
            factor_location = get_percentile_correction(loc_pct_mapped, 'location')
        except ValueError as e:
            self.logger.warning(f"Percentile correction error: {e}. Usando 0 dB")
            return self.xp.zeros(n, dtype=float)
        
        # P.1546-6 §8.1: "adding the two corrections algebraically"
        total_factor = factor_time + factor_location
        
        # Retornar como array (misma corrección para todos los receptores)
        adjustment = self.xp.full(n, total_factor, dtype=float)
        
        self.logger.debug(f"Percentile correction (ITU tables): time%={time_pct_mapped}, loc%={loc_pct_mapped}, "
                         f"factor_time={factor_time:.2f} dB, factor_location={factor_location:.2f} dB, "
                         f"total={total_factor:.2f} dB")
        
        return adjustment
    
    def _convert_field_to_path_loss(self,
                                   E_field: np.ndarray,
                                   frequency: float,
                                   h_eff: np.ndarray,
                                   tca_correction: np.ndarray,
                                   clutter_correction: np.ndarray,
                                   terminal_clearance: Optional[np.ndarray] = None,
                                   percentile_correction: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Convierte E[dBμV/m] a Path Loss [dB] — P.1546-6 §5.

        PL = 139.3 + 20·log₁₀(f_MHz) − E + TCA + clutter + percentile

        donde 139.3 = 20·log₁₀(10⁷) es la constante de conversión ITU.
        Todas las correcciones son aditivas y positivas cuando aumentan la pérdida.

        Args:
            E_field: E[dBμV/m] desde tablas (n_receptors,)
            frequency: Frecuencia en MHz
            h_eff: no usado en la conversión (conservado para firma uniforme)
            tca_correction: Corrección TCA §4.5 [dB] (n_receptors,)
            clutter_correction: Pérdida por clutter P.2108-1 [dB] (n_receptors,)
            terminal_clearance: No usado actualmente (siempre None)
            percentile_correction: Corrección percentil §8.1 [dB] (n_receptors,)

        Returns:
            np.ndarray: Path loss [dB] (n_receptors,)
        """
        # Fórmula base: PL = 139.3 + 20*log10(f) - E + correcciones
        freq_term = 20 * self.xp.log10(frequency)
        
        # Path loss base (conversión E → PL)
        path_loss = 139.3 + freq_term - E_field
        
        # Aplicar correcciones (todas aumentan path loss si son positivas)
        path_loss = path_loss + tca_correction + clutter_correction
        
        if terminal_clearance is not None:
            path_loss = path_loss + terminal_clearance
        
        if percentile_correction is not None:
            path_loss = path_loss + percentile_correction
        
        self.logger.debug(
            f"PL [{frequency} MHz]: base={139.3 + freq_term:.2f} dB, "
            f"E=[{float(E_field.min()):.1f},{float(E_field.max()):.1f}] dBμV/m, "
            f"TCA=[{float(tca_correction.min()):.2f},{float(tca_correction.max()):.2f}] dB, "
            f"clutter=[{float(clutter_correction.min()):.2f},{float(clutter_correction.max()):.2f}] dB, "
            f"PL=[{float(path_loss.min()):.1f},{float(path_loss.max()):.1f}] dB"
        )
        
        return path_loss
    
    
    def get_model_info(self) -> Dict[str, Any]:
        """Retorna metadatos del modelo."""
        return {
            'name': self.name,
            'type': self.model_type,
            # Rango del estándar; interpolación de tablas: 100–2000 MHz
            'frequency_range': '30-4000 MHz (tablas internas: 100-2000 MHz)',
            'distance_range': '1-1000 km',
            'tx_height_range': '10-1200 m AGL (tablas); extrapolación fuera de rango',
            'rx_height_range': '1-20 m AGL',
            'environments': ['Urban', 'Suburban', 'Rural'],
            'has_terrain_awareness': True,
            'has_tca_correction': True,      # P.1546-6 §4.5
            'has_clutter_correction': True,  # ITU-R P.2108-1 §3
            'cpu_gpu_support': True,
            # P.1546 es modelo punto-área estadístico; NO tiene estados LOS/NLOS
            'has_los_nlos': False,
            'reference': 'ITU-R P.1546-6 (August 2019) + ITU-R P.2108-1',
            'implementation': 'Table interpolation (§4.3 h_eff, §4.5 TCA, §8.1 percentiles) + P.2108-1 clutter',
            'tables_info': self.tables_info,
        }

    def _calculate_radio_horizon(self, tx_height: float, rx_height: float) -> float:
        """
        Distancia de radio horizonte combinada TX+RX [km].

        Fórmula estándar (Radio Engineering, k=4/3):
            d_km = 4.12 * (sqrt(h_tx_m) + sqrt(h_rx_m))

        Nota: este método es informativo (no se llama internamente en
        calculate_path_loss). P.1546-6 no usa el radio horizonte explícitamente
        en su procedimiento de cálculo de path loss.

        Args:
            tx_height: Altura antena TX [m AGL]
            rx_height: Altura receptor [m AGL]
        Returns:
            Distancia de radio horizonte [km]
        """
        import math
        return 4.12 * (math.sqrt(tx_height) + math.sqrt(rx_height))
