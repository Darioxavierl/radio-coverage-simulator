"""
ITU-R P.1546 Clutter Model (ANNEX 5)

Implementación de corrección por clutter (ambiente/morfología):
- Detección automática de morphology (urban/suburban/rural) desde DEM
- Height gain correction basada en tablas ITU Annex 5
- Aplicación distancia-dependiente
- Categorías representativas de altura de clutter

FASE 4: Reemplaza fórmula exp() inventada con modelo realista ITU

Referencia:
- ITU-R P.1546-6 Annex 5 (Clutter losses)

Autor: Fase 4 Implementation
Fecha: 2025
"""

import numpy as np
import logging
from typing import Tuple, Optional


class ClutterModel:
    """Modelo de clutter para ITU-R P.1546"""
    
    # Tablas ITU Annex 5: Alturas representativas de clutter
    CLUTTER_CATEGORIES = {
        'urban': {
            'h_clutter': 25.0,          # Altura representativa clutter [m]
            'max_loss_db': 8.5,         # Pérdida máxima [dB]
            'd_apply_m': 1000.0,        # Distancia máxima aplicación [m]
            'variability_threshold': 50.0,  # Variabilidad terreno para detectar [m]
        },
        'suburban': {
            'h_clutter': 12.0,
            'max_loss_db': 5.0,
            'd_apply_m': 2000.0,
            'variability_threshold': 20.0,
        },
        'rural': {
            'h_clutter': 4.0,
            'max_loss_db': 2.0,
            'd_apply_m': 3000.0,
            'variability_threshold': 5.0,
        },
    }
    
    def __init__(self, xp=None):
        """
        Inicializa modelo de clutter
        
        Args:
            xp: Módulo numérico (np o cp para GPU)
        """
        self.xp = xp if xp is not None else np
        self.logger = logging.getLogger("ClutterModel")
    
    
    def classify_clutter_from_dem(self,
                                  terrain_profile: np.ndarray,
                                  profile_distances: np.ndarray,
                                  rx_location_distance_m: float,
                                  local_window_m: float = 2000.0) -> str:
        """
        Clasifica morphology (clutter) del terreno usando DEM
        
        Análisis de topografía local (primeros ~2km del receptor):
        - URBAN: Variabilidad >50m en rango corto → construcciones, edificios
        - SUBURBAN: Variabilidad 20-50m → mixto urbano-rural
        - RURAL: Variabilidad <20m → plano, agricultura
        
        FÍSICA:
        - Áreas urbanas tienen variación rápida (canyones, toits)
        - Áreas rurales tienen variación suave (agricultura, montaña suave)
        
        Args:
            terrain_profile: Elevaciones del perfil radial [m] (n_samples,)
            profile_distances: Distancias del perfil [m] (n_samples,)
            rx_location_distance_m: Distancia del receptor desde TX [m]
            local_window_m: Ventana de análisis local [m] (default: 2km)
        
        Returns:
            String: 'urban' | 'suburban' | 'rural'
        """
        # Ventana local alrededor del receptor
        window_start = max(0, rx_location_distance_m - local_window_m/2)
        window_end = rx_location_distance_m + local_window_m/2
        
        # Seleccionar puntos en ventana
        mask = (profile_distances >= window_start) & (profile_distances <= window_end)
        
        if self.xp.sum(mask) < 5:
            # Ventana vacía o muy pequeña: usar perfil completo
            local_profile = terrain_profile
        else:
            local_profile = terrain_profile[mask]
        
        # Calcular variabilidad
        z_min = self.xp.min(local_profile)
        z_max = self.xp.max(local_profile)
        variability = z_max - z_min
        
        # Clasificación por umbral de variabilidad
        if variability > 50.0:
            category = 'urban'
        elif variability > 20.0:
            category = 'suburban'
        else:
            category = 'rural'
        
        return category
    
    
    def calculate_height_gain_correction(self,
                                        h_rx_agl: float,
                                        category: str = 'suburban') -> float:
        """
        Calcula corrección por ganancia de altura (height gain)
        
        Fórmula ITU P.1546 Annex 5:
            L_clutter = L_max * (1 - exp(-(h_rx - h_0) / h_c)) para h_rx < h_clutter
            L_clutter = 0 para h_rx >= h_clutter
        
        donde:
            L_max = pérdida máxima [dB] del clutter
            h_clutter = altura representativa de clutter [m]
            h_rx = altura del receptor [m AGL]
            h_c ≈ h_clutter (altura característica, escala exponencial)
        
        FÍSICA:
        - RX alto (sobre clutter) → sin pérdida
        - RX bajo (bajo clutter) → pérdida máxima
        - Transición suave exponencial entre ambos
        
        Args:
            h_rx_agl: Altura del receptor [m AGL]
            category: 'urban' | 'suburban' | 'rural'
        
        Returns:
            Pérdida por clutter [dB]
        """
        if category not in self.CLUTTER_CATEGORIES:
            self.logger.warning(f"Categoría desconocida: {category}, usando suburban")
            category = 'suburban'
        
        params = self.CLUTTER_CATEGORIES[category]
        h_clutter = params['h_clutter']
        max_loss = params['max_loss_db']
        
        # Si RX está alto sobre clutter, sin pérdida
        if h_rx_agl >= h_clutter:
            loss_db = 0.0
        else:
            # RX está bajo clutter: aplicar corrección exponencial
            # Formula: L = L_max * (1 - exp(-(h_clutter - h_rx) / h_clutter))
            height_diff = h_clutter - h_rx_agl
            
            # Exponencial: penaliza receptores bajo clutter
            exp_factor = self.xp.exp(-height_diff / h_clutter)
            loss_db = max_loss * (1.0 - exp_factor)
        
        return loss_db
    
    
    def calculate_clutter_loss(self,
                              terrain_profile: np.ndarray,
                              profile_distances: np.ndarray,
                              distance_rx_m: float,
                              h_rx_agl: float,
                              environment: str = 'suburban') -> float:
        """
        Calcula pérdida total de clutter con aplicación distancia-dependiente
        
        PIPELINE:
        1. Clasificar clutter (si no se proporciona environment)
        2. Calcular height gain correction
        3. Aplicar factor distancia (decae con distancia)
        4. Retornar corrección en dB
        
        REEMPLAZA:
        exp() formula inventada + regla <1km
        
        CON:
        ITU Annex 5 model + distancia-dependiente realista
        
        Args:
            terrain_profile: Elevaciones del perfil [m] (n_samples,)
            profile_distances: Distancias del perfil [m] (n_samples,)
            distance_rx_m: Distancia final del receptor [m]
            h_rx_agl: Altura receptor [m AGL]
            environment: 'urban' | 'suburban' | 'rural' (si es None, auto-detecta)
        
        Returns:
            Pérdida de clutter [dB]
        """
        # Determinar categoría
        if environment is None or environment.lower() == 'auto':
            category = self.classify_clutter_from_dem(
                terrain_profile, profile_distances, distance_rx_m
            )
        else:
            category = environment.lower()
        
        # Obtener parámetros
        params = self.CLUTTER_CATEGORIES.get(category, self.CLUTTER_CATEGORIES['suburban'])
        h_clutter = params['h_clutter']
        max_loss = params['max_loss_db']
        d_apply = params['d_apply_m']
        
        # PASO 1: Height gain correction
        height_correction = self.calculate_height_gain_correction(h_rx_agl, category)
        
        # PASO 2: Distance-dependent factor
        # Clutter es relevante solo en distancias cercanas (< d_apply)
        # Decae suavemente con distancia más allá de ese rango
        if distance_rx_m < d_apply:
            # Cercano: usar corrección completa
            distance_factor = 1.0
        else:
            # Lejano: decaimiento lineal
            # factor = 1 at d_apply, 0 at 2*d_apply
            distance_factor = max(0.0, 1.0 - (distance_rx_m - d_apply) / d_apply)
        
        # PASO 3: Pérdida total
        clutter_loss = height_correction * distance_factor
        
        return clutter_loss
    
    
    def calculate_clutter_correction_vectorized(self,
                                               terrain_profiles: np.ndarray,
                                               profile_distances: np.ndarray,
                                               distances_m: np.ndarray,
                                               h_rx_agl: float,
                                               environment: Optional[str] = None,
                                               frequency_mhz: float = 900.0) -> np.ndarray:
        """
        Corrección de clutter vectorizada — ITU-R P.2108-1 §3 (Terrestrial Clutter Loss).

        Fórmula P.2108-1 §3:
            F_fc = exp(-0.0689/f_GHz - 0.0298)        # factor de frecuencia
            L = 10.25 × F_fc × exp(-d_t) × (1 - tanh(6 × (h_b/h_g - 0.625))) - 0.33
            L = max(L, 0)

        donde:
            f_GHz : frecuencia en GHz
            d_t   : distancia desde receptor hasta primera obstrucción de clutter [km]
            h_b   : altura del receptor AGL [m]
            h_g   : altura representativa de clutter según entorno [m]

        Args:
            terrain_profiles: (n_receptors, n_samples) — elevación AMSL [m]
            profile_distances: (n_receptors, n_samples) — distancia desde TX [m]
            distances_m: (n_receptors,) — distancia TX→RX [m]
            h_rx_agl: Altura receptor AGL [m]
            environment: 'urban' | 'suburban' | 'rural' | None (auto-detect desde DEM)
            frequency_mhz: Frecuencia en MHz (requerida para F_fc)
        Returns:
            Array (n_receptors,) de pérdida por clutter [dB]
        """
        xp = self.xp
        n_receptors = len(distances_m)

        # --- Altura de clutter por entorno (h_g) ---
        H_G = {'urban': 25.0, 'suburban': 10.0, 'rural': 4.0}
        D_T_DEFAULT = {'urban': 0.0, 'suburban': 0.5, 'rural': 2.0}  # km sin DEM

        # Determinar entorno (single value: se aplica igual a todos los receptores)
        if environment is None or environment.strip().lower() == 'auto':
            env = 'suburban'  # default conservador
        else:
            env = environment.strip().lower()
        if env not in H_G:
            env = 'suburban'

        h_g = H_G[env]
        h_b = float(h_rx_agl)

        # --- Factor de frecuencia P.2108-1 §3 ---
        f_GHz = max(frequency_mhz / 1000.0, 0.01)  # evitar div/0
        F_fc = float(np.exp(-0.0689 / f_GHz - 0.0298))

        # --- d_t: distancia receptor → primera obstrucción de clutter [km] ---
        if terrain_profiles is not None and profile_distances is not None:
            # d_from_rx[i, j] = distancia desde RX al punto j del perfil [m]
            d_from_rx = distances_m[:, None] - profile_distances  # (n, nr)

            # Ventana: 0..5000 m desde el receptor (región de clutter local)
            near_rx = (d_from_rx >= 0.0) & (d_from_rx <= 5000.0)

            # Elevación absoluta de la cima de clutter en cada punto
            clutter_top = terrain_profiles + h_g  # (n, nr) — techo del clutter [m AMSL]

            # Elevación absoluta del receptor
            # terrain_heights no disponible aquí; se estima desde terrain_profiles[:, -1]
            H_rx_amsl = terrain_profiles[:, -1] + h_b  # (n,) — aproximación RX

            # Punto obstruido: cima de clutter supera la elevación del receptor
            obstructed = clutter_top > H_rx_amsl[:, None]  # (n, nr)

            # Asignar d_from_rx solo para puntos obstruidos y en ventana; inf en los demás
            big = xp.full_like(d_from_rx, xp.inf)
            d_t_m = xp.where(obstructed & near_rx, d_from_rx, big)
            d_t_min_m = d_t_m.min(axis=1)  # (n,) primera obstrucción [m]

            # Si no hay obstrucción dentro de 5 km → d_t grande → pérdida ≈ 0
            d_t_km = xp.where(
                xp.isinf(d_t_min_m),
                xp.full(n_receptors, D_T_DEFAULT[env]),
                d_t_min_m / 1000.0
            )
        else:
            # Sin DEM: usar valores por defecto por entorno
            d_t_km = xp.full(n_receptors, D_T_DEFAULT[env])

        # --- Fórmula P.2108-1 §3 (vectorizada) ---
        h_ratio = h_b / max(h_g, 0.1)  # h_b / h_g
        tanh_term = xp.tanh(6.0 * (h_ratio - 0.625))
        exp_dt = xp.exp(-d_t_km)

        L_raw = 10.25 * F_fc * exp_dt * (1.0 - tanh_term) - 0.33
        clutter_array = xp.maximum(L_raw, 0.0)

        self.logger.debug(
            f"Clutter P.2108-1: env={env}, f={frequency_mhz:.0f} MHz, "
            f"F_fc={F_fc:.4f}, h_g={h_g}m, h_b={h_b}m, "
            f"mean_L={float(xp.mean(clutter_array)):.2f} dB, "
            f"max_L={float(xp.max(clutter_array)):.2f} dB"
        )
        return clutter_array
