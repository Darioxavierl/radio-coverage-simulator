"""
ITU-R P.1546 Diffraction Model (ANNEX 5-6)

Implementación de difracción real usando:
- Knife-Edge diffraction (Fresnel parameter ν)
- Fresnel zones clearance
- Radio horizon calculation con k=4/3 (atmósfera estándar)
- LOS vs TRANSHORIZON mode detection

FASE 3: Reemplaza heurística if(TCA>2°)→+5dB con diffraction real

Referencia:
- ITU-R P.1546-6 Annex 5-6
- Rec. ITU-R P.417 Fresnel diffraction

Autor: Fase 3 Implementation
Fecha: 2025
"""

import numpy as np
import logging
from typing import Tuple, Optional


class DiffractionModel:
    """Modelo de difracción para ITU-R P.1546"""
    
    def __init__(self, xp=None):
        """
        Inicializa modelo de difracción
        
        Args:
            xp: Módulo numérico (np o cp para GPU)
        """
        self.xp = xp if xp is not None else np
        self.logger = logging.getLogger("DiffractionModel")
        
        # Constantes ITU
        self.k_factor = 4.0 / 3.0  # Factor tierra efectiva (atmósfera estándar)
        self.earth_radius_m = 6.371e6  # Radio terrestre [m]
    
    
    def calculate_radio_horizon(self, 
                               distance_m: np.ndarray,
                               h_eff_tx: np.ndarray,
                               h_eff_rx: np.ndarray,
                               k_factor: Optional[float] = None) -> np.ndarray:
        """
        Calcula distancia de radio horizonte (donde LOS breaks)
        
        Fórmula ITU:
            d_horizon = sqrt(2 * k * R_e * (h_eff_tx + h_eff_rx))
        
        donde:
            k = factor tierra efectiva (4/3 para atmósfera estándar)
            R_e = radio terrestre [m]
            h_eff = alturas efectivas [m]
        
        FÍSICA:
        - Atmósfera estándar: k = 4/3 (refracción típica)
        - Suero normal: k = 1.0 (tierra plana)
        - Ductos: k < 1.0 (refracción super-standard)
        
        Args:
            distance_m: Distancia TX-RX en metros (n_receptors,) — NO USADO, solo por compatibilidad
            h_eff_tx: Altura efectiva TX en metros (escalar o array)
            h_eff_rx: Altura efectiva RX en metros (n_receptors,)
            k_factor: Factor tierra efectiva (default: 4/3)
        
        Returns:
            Array distancia de radio horizonte en metros (n_receptors,)
        """
        if k_factor is None:
            k_factor = self.k_factor
        
        # Fórmula: d_h = sqrt(2 * k * R_e * (h_tx + h_rx))
        # Convertir ambos a arrays
        h_eff_tx_arr = self.xp.atleast_1d(h_eff_tx)
        h_eff_rx_arr = self.xp.atleast_1d(h_eff_rx)
        
        # Si h_eff_tx es escalar, expandir a tamaño de h_eff_rx
        if h_eff_tx_arr.size == 1:
            h_eff_tx_arr = self.xp.full_like(h_eff_rx_arr, h_eff_tx_arr[0])
        
        sum_heights = h_eff_tx_arr + h_eff_rx_arr
        
        # sqrt(2 * k * R_e * h) es la fórmula para radio horizon
        d_horizon = self.xp.sqrt(2.0 * k_factor * self.earth_radius_m * sum_heights)
        
        return d_horizon
    
    
    def detect_propagation_mode(self,
                               distance_m: np.ndarray,
                               d_horizon_tx: np.ndarray,
                               d_horizon_rx: np.ndarray) -> np.ndarray:
        """
        Detecta modo de propagación: LOS o TRANSHORIZON
        
        Criterio ITU:
        - LOS si: distance < (d_horizon_tx + d_horizon_rx)
        - TRANSHORIZON si: distance >= (d_horizon_tx + d_horizon_rx)
        
        FÍSICA:
        - LOS: Rayo directo puede llegar sin obstáculos (o con pequeña difracción)
        - TRANSHORIZON: Rayo debe difractarse sobre obstáculo máximo
        
        Args:
            distance_m: Distancia total TX-RX [m] (n_receptors,)
            d_horizon_tx: Radio horizonte desde TX [m] (n_receptors,)
            d_horizon_rx: Radio horizonte hacia RX [m] (n_receptors,)
        
        Returns:
            Array booleano: True = LOS, False = TRANSHORIZON
        """
        # Criterio: LOS si distancia < suma de horizontes
        is_los = distance_m < (d_horizon_tx + d_horizon_rx)
        
        return is_los
    
    
    def calculate_knife_edge_loss(self,
                                 h_obstacle: np.ndarray,
                                 d1_m: np.ndarray,
                                 d2_m: np.ndarray,
                                 frequency_hz: float) -> np.ndarray:
        """
        Calcula pérdida de difracción Knife-Edge (Fresnel)
        
        TEORÍA FRESNEL:
        Parámetro de difracción:
            ν = h_obstacle * sqrt(2 * (d1 + d2) / (λ * d1 * d2))
        
        donde:
            h_obstacle = altura del obstáculo sobre línea recta [m]
            d1 = distancia TX a obstáculo [m]
            d2 = distancia obstáculo a RX [m]
            λ = longitud de onda [m]
        
        Pérdida de difracción (Fresnel diffraction):
            L_d = 20 * log10(0.5 + 0.62 * ν) para ν > -0.78
            L_d = 0 para ν < -0.78 (sin obstáculo)
            L_d ≈ 20 * log10(0.5) ≈ -6 dB para ν = 0 (LOS crítico)
        
        IMPLEMENTACIÓN SIMPLIFICADA:
        Asumimos d1 ≈ d2 ≈ d/2 (obstáculo en medio del camino)
        Entonces: ν ≈ h * sqrt(8 / (λ * d²))
        
        Args:
            h_obstacle: Altura del obstáculo [m] (n_receptors,)
            d1_m: Distancia TX-obstáculo [m] (n_receptors,)
            d2_m: Distancia obstáculo-RX [m] (n_receptors,)
            frequency_hz: Frecuencia en Hz
        
        Returns:
            Array pérdida de difracción en dB (n_receptors,)
        """
        # Longitud de onda [m]
        c = 3e8  # Velocidad luz [m/s]
        wavelength = c / frequency_hz
        
        # Parámetro Fresnel
        numerator = 2.0 * (d1_m + d2_m)
        denominator = wavelength * d1_m * d2_m
        
        # Evitar división por cero
        denominator = self.xp.maximum(denominator, 1e-6)
        
        # Correccion por curvatura de la tierra (ITU-R P.526 §4.1, k=4/3)
        # h_corr = h_obs - (d1 x d2) / (2 x Re_eff), donde Re_eff = k x R_tierra = 8500 km
        # Para distancias cortas (<15 km) la correccion es pequeña (<3m), pero fisicamente correcta
        Re_eff = 8.5e6  # Radio efectivo terrestre con k=4/3 [m]
        earth_bulge = (d1_m * d2_m) / (2.0 * Re_eff)
        h_obstacle_corr = h_obstacle - earth_bulge  # Obstaculo parece mas bajo por curvatura terrestre
        
        nu = h_obstacle_corr * self.xp.sqrt(numerator / denominator)
        
        # Pérdida Fresnel
        # Para ν < -0.78: sin pérdida adicional (campo libre)
        # Para ν > -0.78: pérdida aumenta con ν
        
        loss_db = self.xp.zeros_like(h_obstacle)
        
        # Rango ν > -0.78 (difracción significativa)
        mask = nu > -0.78
        
        if self.xp.any(mask):
            # L_d = 20 * log10(0.5 + 0.62 * ν)
            argument = 0.5 + 0.62 * nu[mask]
            # Asegurar que argument > 0 (logaritmo)
            argument = self.xp.maximum(argument, 1e-6)
            loss_db[mask] = 20.0 * self.xp.log10(argument)
        
        # Fresnel physics CORRECTO:
        # - Para ν ∈ [-0.78, 0]: L_d ∈ [-6dB, 0] (difracción parcial, reduce atenuación)
        # - Para ν > 0: L_d > 0 (atenuación adicional por obstáculo)
        # NO usar maximum(loss_db, 0) porque destruye la física Fresnel
        # SOLO saturar máximo atenuación (20 dB realista para LOS severo)
        loss_db = self.xp.minimum(loss_db, 20.0)  # Saturar máximo a 20dB
        # loss_db puede ser negativa (válido en Fresnel physics)
        
        return loss_db
    
    
    def calculate_fresnel_clearance(self,
                                   terrain_profile: np.ndarray,
                                   distances_m: np.ndarray,
                                   frequency_hz: float,
                                   h_line_of_sight: np.ndarray,
                                   n_zones: int = 1) -> np.ndarray:
        """
        Calcula clearance de zonas de Fresnel
        
        TEORÍA FRESNEL:
        Radio de zona de Fresnel n:
            r_n = sqrt(n * λ * d1 * d2 / (d1 + d2))
        
        donde:
            λ = longitud de onda [m]
            d1, d2 = distancias a obstáculo
            n = número de zona (1, 2, 3, ...)
        
        CRITERIO:
        - Si terreno penetra zona 1: difracción significativa (>5dB)
        - Si terreno limpio zona 1: LOS probable (<2dB)
        - Si terreno limpio zonas 1-2: excelente propagación (<0dB)
        
        Args:
            terrain_profile: Elevaciones del perfil [m] (n_samples,)
            distances_m: Distancias desde TX [m] (n_samples,)
            frequency_hz: Frecuencia en Hz
            h_line_of_sight: Altura de línea recta en cada punto [m] (n_samples,)
            n_zones: Número de zonas Fresnel a considerar (default: 1)
        
        Returns:
            Array factor de clearance (0-1, donde 1=completamente libre)
        """
        # Longitud de onda
        c = 3e8
        wavelength = c / frequency_hz
        
        # Para cada punto del perfil, calcular clearance de zona 1 Fresnel
        # Asumiendo distancia total es máxima distance_m
        d_total = distances_m[-1]
        d1 = distances_m
        d2 = d_total - distances_m
        
        # Evitar división por cero
        d2 = self.xp.maximum(d2, 1.0)
        
        # Radio zona 1 Fresnel
        r_fresnel_1 = self.xp.sqrt(wavelength * d1 * d2 / (d1 + d2))
        
        # Verificar penetración
        effective_obstacle = terrain_profile - h_line_of_sight
        
        # Penetración normalizada (-1 = 1 radio Fresnel bajo línea, 0 = en línea, +1 = encima)
        penetration_normalized = effective_obstacle / (r_fresnel_1 + 1e-6)
        
        # Factor de clearance: cuán limpio está
        # Si penetration < 0.5: está claro (>0.5 altura de zona Fresnel)
        # Si penetration > 0.5: está obstruido
        clearance_factor = self.xp.maximum(1.0 - penetration_normalized, 0.0)
        clearance_factor = self.xp.minimum(clearance_factor, 1.0)
        
        # Retornar clearance promedio
        mean_clearance = self.xp.mean(clearance_factor)
        
        return mean_clearance
    
    
    def calculate_diffraction_correction(self,
                                        terrain_profiles: np.ndarray,
                                        distances_km: np.ndarray,
                                        frequency_hz: float,
                                        h_eff_tx: float,
                                        h_eff_rx: np.ndarray,
                                        tx_elevation: float,
                                        terrain_heights: np.ndarray) -> np.ndarray:
        """
        Calcula corrección de difracción usando modelo real P.1546 Annex 5-6
        
        PIPELINE:
        1. Calcular radio horizonte (k=4/3)
        2. Detectar LOS vs TRANSHORIZON
        3. Calcular pérdida Knife-Edge en obstáculo máximo
        4. Calcular clearance zona Fresnel
        5. Combinar correcciones
        
        REEMPLAZA:
        if(TCA > 2°) → +5dB [HEURÍSTICA INVENTADA]
        
        CON:
        Difracción Fresnel real con parámetro ν [ESTÁNDAR P.1546]
        
        Args:
            terrain_profiles: Perfiles radiales (n_receptors, n_radios) [m msnm]
            distances_km: Distancias finales [km]
            frequency_hz: Frecuencia en Hz
            h_eff_tx: Altura efectiva TX [m AGL]
            h_eff_rx: Alturas efectivas RX [m AGL] (n_receptors,)
            tx_elevation: Elevación TX [m msnm]
            terrain_heights: Elevaciones en receptores [m msnm] (n_receptors,)
        
        Returns:
            Array correcciones difracción en dB (n_receptors,)
        """
        n_receptors = terrain_profiles.shape[0]
        distances_m = distances_km * 1000.0
        
        # PASO 1-2: En terrain montañoso, ignorar radio horizonte simple
        # Radio horizonte (25-50 km) es INCORRECTO en montaña con obstáculos reales
        # En su lugar: SIEMPRE calcular perfil real para detectar obstáculos
        # (El check de radio horizonte solo es válido en terrain plano)
        
        # PASO 3-5: Calcular correcciones por receptor
        diffraction_correction = self.xp.zeros(n_receptors)
        
        for i in range(n_receptors):
            # SIEMPRE calcular el perfil (no usar radio horizonte plano en montaña)
            # Motivo: en terrain montañoso, hay obstáculos reales aunque "radio horizonte" > distancia
            
# SIEMPRE calcular el perfil (no usar radio horizonte plano en montaña)
            # Motivo: en terrain montañoso, hay obstáculos reales aunque "radio horizonte" > distancia
            
            # Determinar si hay obstáculo REAL en el perfil
            # (En lugar de confiar en radio horizonte que falla en montaña)
            profile = terrain_profiles[i]
            h_tx_absolute = tx_elevation + h_eff_tx
            h_rx_absolute = terrain_heights[i]
            
            # Línea recta TX→RX
            # Muestreo lineal en distancia
            n_radios = len(profile)
            radial_distances = self.xp.linspace(0, distances_m[i], n_radios)
            h_line = h_tx_absolute + (h_rx_absolute - h_tx_absolute) * (radial_distances / distances_m[i])
            
            # Obstáculo máximo
            effective_obstacle = profile - h_line
            max_obstacle_idx = self.xp.argmax(effective_obstacle)
            max_obstacle = effective_obstacle[max_obstacle_idx]
            
            if max_obstacle > 0:
                # Hay obstáculo: calcular Knife-Edge
                d1 = radial_distances[max_obstacle_idx]
                d2 = distances_m[i] - d1
                
                loss = self.calculate_knife_edge_loss(
                    h_obstacle=self.xp.array([max_obstacle]),
                    d1_m=self.xp.array([d1]),
                    d2_m=self.xp.array([d2]),
                    frequency_hz=frequency_hz
                )
                diffraction_correction[i] = loss[0]
            else:
                # Sin obstáculo: LOS (no hay difracción)
                diffraction_correction[i] = 0.0
        
        self.logger.debug(f"Diffraction: mean_loss={float(self.xp.mean(diffraction_correction)):.2f} dB")
        
        return diffraction_correction
