"""
COST-231 Hata Model - Extensión de Okumura-Hata para 1500-2000 MHz

Modelo empírico para propagación en sistemas móviles 4G/LTE.
Extensión de Okumura-Hata optimizada para frecuencias 1500-2000 MHz.

Basado en: ITU-R P.1411, COST Action 231 ("Digital Mobile Radio Towards Future Generation Systems")

Rangos de validez:
- Frecuencia: 1500 - 2000 MHz (requerido)
- Distancia: 0.02 - 5 km (óptimo), extrapolable hasta 20 km
- Altura antena base: 30 - 200 m AGL
- Altura móvil: 1 - 10 m
- Ambiente: Urban (Suburban/Rural fuera de rango)

Ecuación base:
L = 46.3 + 33.9·log₁₀(f) − 13.82·log₁₀(h_b) − a(h_m)
    + [44.9 − 6.55·log₁₀(h_b)]·log₁₀(d) + C_m

Autores: David Montano, Dario Portilla
Universidad de Cuenca, 2025
"""

import numpy as np
import logging
from typing import Dict, Any, Optional


class COST231HataModel:
    """
    Modelo COST-231 Hata completo

    Extensión de Okumura-Hata para 1500-2000 MHz.
    Usado en simulaciones 4G/LTE con frecuencias intermedias.

    Diferencias vs Okumura-Hata:
    - Término base: 46.3 dB (vs 69.55 dB)
    - Coeficiente frecuencia: 33.9 (vs 26.16)
    - Rango frecuencia requerido: 1500-2000 MHz
    - Corrección C_m: +0 dB (medium) o +3 dB (large city)
    - Otros componentes: idénticos a Okumura-Hata
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, compute_module=None):
        """
        Inicializa modelo COST-231 Hata

        Args:
            config: Diccionario de configuración (opcional)
            compute_module: numpy o cupy para CPU/GPU
        """
        self.config = config or {}
        self.logger = logging.getLogger("COST231HataModel")
        self.name = "COST-231 Hata"

        # Módulo de cómputo (numpy o cupy)
        self.xp = compute_module if compute_module is not None else np

        # Parámetros configurables (idénticos a Okumura-Hata)
        self.mobile_height = self.config.get('mobile_height', 1.5)  # metros
        self.environment = self.config.get('environment', 'Urban')  # Solo Urban válido
        self.city_type = self.config.get('city_type', 'medium')  # 'large' → C_m=3, 'medium' → C_m=0

        # Método de referencia de terreno para altura efectiva de BS
        self.terrain_reference_method = self.config.get('terrain_reference_method', 'global_mean')
        self.terrain_reference_inner_km = float(self.config.get('terrain_reference_inner_km', 3.0))
        self.terrain_reference_outer_km = float(self.config.get('terrain_reference_outer_km', 15.0))
        self.terrain_min_samples = int(self.config.get('terrain_min_samples', 50))

        self.logger.info(f"Initialized {self.name}")
        self.logger.info(f"Compute module: {self.xp.__name__}")
        self.logger.info(f"Environment: {self.environment}, City type: {self.city_type}")

    def calculate_path_loss(self, distances: np.ndarray, frequency: float, tx_height: float,
                           terrain_heights: np.ndarray, tx_elevation: float = 0.0,
                           terrain_profiles: Optional[np.ndarray] = None,
                           environment: str = 'Urban',
                           city_type: str = 'medium', mobile_height: Optional[float] = None,
                           **kwargs) -> Dict[str, np.ndarray]:
        """
        Calcula pérdida de propagación usando COST-231 Hata

        Ecuación:
        L = 46.3 + 33.9·log₁₀(f) − 13.82·log₁₀(h_b) − a(h_m)
            + [44.9 − 6.55·log₁₀(h_b)]·log₁₀(d) + C_m

        Args:
            distances: Array de distancias en METROS (1D o 2D)
            frequency: Frecuencia en MHz (1500-2000 válido)
            tx_height: Altura de antena TX en metros AGL (30-200m)
            terrain_heights: Array elevaciones terreno en msnm
            tx_elevation: Elevación del terreno en TX en msnm
            terrain_profiles: Array opcional (n_receptors, n_samples) con perfiles radiales
            environment: 'Urban' (solo Urban válido en COST-231 Hata)
            city_type: 'large' (C_m=3 dB) o 'medium' (C_m=0 dB)
            mobile_height: Altura móvil en metros (default: 1.5m)
            **kwargs: Parámetros adicionales

        Returns:
            Dict con:
            - 'path_loss': Array pérdida en dB (mismo shape que distances)
            - 'hb_effective': Array altura efectiva TX en metros
            - 'validity_mask': Array bool (metadato de confianza)
            - 'valid_count': int (receptores en rango válido)
        """
        self.logger.debug(f"Calculating COST-231 Hata: f={frequency}MHz, env={environment}")

        # Usar valores por defecto si no se especifican
        if mobile_height is None:
            mobile_height = self.mobile_height

        # Validar rangos del modelo
        self._validate_parameters(frequency, tx_height, mobile_height)

        # Convertir distancias a km
        d_km_real = distances / 1000.0

        # Distancia para modelo (clamp a 0.001 km para evitar log(0))
        d_km_model = self.xp.maximum(d_km_real, 0.001)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ALTURA EFECTIVA DE LA ANTENA BASE
        # h_b,eff = h_tx + z_tx - z_ref
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if terrain_profiles is not None:
            # Si terrain_profiles disponible, usar análisis estadístico
            original_shape = d_km_model.shape
            d_km_flat = d_km_model.ravel()

            hb_effective = self._calculate_effective_height_vectorized(
                tx_height, tx_elevation, terrain_profiles, d_km_flat
            )

            # Reshape de vuelta a forma original
            hb_effective = hb_effective.reshape(original_shape)
            self.logger.debug("Using vectorized effective height with terrain profiles")
        else:
            # Fallback: usar referencia global del terreno
            terrain_reference = self._compute_terrain_reference(terrain_heights, d_km_model)
            hb_effective = self.xp.full(d_km_model.shape, tx_height + tx_elevation - terrain_reference)
            self.logger.debug("Using terrain reference method (global_mean)")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VALIDEZ DEL MODELO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Rango COST-231 Hata: f ∈ [1500-2000], d ∈ [0.02-5]
        validity_frequency = (frequency >= 1500) and (frequency <= 2000)
        validity_distance = (d_km_real >= 0.02) & (d_km_real <= 5.0)
        validity_height = (hb_effective >= 30.0) & (hb_effective <= 200.0)

        # Máscara de validez combinada
        validity_mask = validity_distance & validity_height
        valid_count = int(self.xp.sum(validity_mask))

        # Log de receptores fuera de rango
        if not validity_frequency:
            self.logger.warning(
                f"Frequency {frequency}MHz fuera de rango COST-231 Hata (1500-2000 MHz)"
            )

        n_out_distance = int(self.xp.sum(~validity_distance))
        n_out_height = int(self.xp.sum(~validity_height))
        if n_out_distance > 0:
            self.logger.warning(f"Receptores fuera de rango distancia (0.02-5km): {n_out_distance}")
        if n_out_height > 0:
            self.logger.warning(f"Receptores con h_b,eff fuera de rango (30-200m): {n_out_height}")

        hm = mobile_height

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # FACTOR DE CORRECCIÓN POR ALTURA MÓVIL a(h_m)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        a_hm = self._calculate_mobile_height_correction_vectorized(
            frequency, hm, city_type, hb_effective
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ECUACIÓN BASE COST-231 HATA
        # L = 46.3 + 33.9·log₁₀(f) − 13.82·log₁₀(h_b) − a(h_m)
        #     + [44.9 − 6.55·log₁₀(h_b)]·log₁₀(d) + C_m
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Usar h_b_safe con clamp a 30m para estabilidad numérica (no 1m)
        hb_safe = self.xp.maximum(hb_effective, 30.0)

        path_loss_base = (
            46.3  # COST-231 constante base (diferencia clave vs Okumura-Hata)
            + 33.9 * self.xp.log10(frequency)  # Coeficiente frecuencia (vs 26.16 en OH)
            - 13.82 * self.xp.log10(hb_safe)
            - a_hm
            + (44.9 - 6.55 * self.xp.log10(hb_safe)) * self.xp.log10(d_km_model)
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # CORRECCIÓN POR TIPO DE CIUDAD C_m
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if city_type.lower() == 'large':
            Cm = 3.0  # Centro metropolitano
            self.logger.debug("Applied C_m = 3 dB for large city")
        else:
            Cm = 0.0  # Ciudad mediana (default)
            self.logger.debug("Applied C_m = 0 dB for medium/small city")

        path_loss = path_loss_base + Cm

        self.logger.info(
            f"COST-231 Hata: base={path_loss_base.mean():.1f} dB, "
            f"C_m={Cm} dB, valid={valid_count}/{distances.size}"
        )

        # Retornar diccionario con path_loss y metadatos de validez
        return {
            'path_loss': path_loss,
            'hb_effective': hb_effective,
            'validity_mask': validity_mask,
            'valid_count': valid_count,
        }

    def _validate_parameters(self, frequency: float, tx_height: float, mobile_height: float):
        """
        Valida parametros de entrada según rango COST-231 Hata

        Rangos:
        - Frecuencia: 1500-2000 MHz (requerido)
        - Distancia: 0.02-5 km (óptimo)
        - Altura TX: 30-200m
        - Altura móvil: 1-10m
        """
        # Frecuencia
        if frequency < 1500 or frequency > 2000:
            self.logger.warning(
                f"Frequency {frequency} MHz outside COST-231 Hata range (1500-2000 MHz)"
            )

        # Altura TX
        if tx_height < 30 or tx_height > 200:
            self.logger.warning(
                f"TX height {tx_height}m outside valid range (30-200m)"
            )

        # Altura móvil
        if mobile_height < 1 or mobile_height > 10:
            self.logger.warning(
                f"Mobile height {mobile_height}m outside valid range (1-10m)"
            )

    def _compute_terrain_reference(self, terrain_heights: np.ndarray,
                                   distances_km: np.ndarray) -> float:
        """
        Calcula z_ref para altura efectiva de BS

        Métodos:
        - global_mean: media de todo el grid (legacy)
        - local_annulus_mean: media en anillo [inner_km, outer_km]
        - tx_local_mean: media local en radio <= inner_km
        """
        method = str(self.terrain_reference_method or 'global_mean').lower()
        terrain_global_mean = self.xp.mean(terrain_heights)

        if method == 'global_mean':
            return terrain_global_mean

        if method == 'local_annulus_mean':
            inner = max(self.terrain_reference_inner_km, 0.0)
            outer = max(self.terrain_reference_outer_km, inner)
            mask = (distances_km >= inner) & (distances_km <= outer)
            sample_count = int(self.xp.sum(mask))

            if sample_count >= self.terrain_min_samples:
                return self.xp.mean(terrain_heights[mask])

            self.logger.warning(
                f"COST-231 Hata local_annulus_mean fallback to global_mean: "
                f"samples={sample_count}, min_required={self.terrain_min_samples}"
            )
            return terrain_global_mean

        if method == 'tx_local_mean':
            radius_km = max(self.terrain_reference_inner_km, 0.0)
            mask = distances_km <= radius_km
            sample_count = int(self.xp.sum(mask))

            if sample_count >= self.terrain_min_samples:
                return self.xp.mean(terrain_heights[mask])

            self.logger.warning(
                f"COST-231 Hata tx_local_mean fallback to global_mean: "
                f"samples={sample_count}, min_required={self.terrain_min_samples}"
            )
            return terrain_global_mean

        self.logger.warning(
            f"Unknown terrain_reference_method='{self.terrain_reference_method}', using global_mean"
        )
        return terrain_global_mean

    def _calculate_mobile_height_correction_vectorized(self, frequency: float,
                                                       hm: float, city_type: str,
                                                       hb_eff: np.ndarray) -> np.ndarray:
        """
        Calcula factor corrección a(h_m) de forma vectorizada

        Idéntica a Okumura-Hata - se mantiene para coherencia

        Args:
            frequency: Frecuencia en MHz (escalar)
            hm: Altura móvil en metros (escalar)
            city_type: 'large' o 'medium' (escalar)
            hb_eff: Array altura efectiva (para broadcast shape)

        Returns:
            Array de corrección a(h_m) con mismo shape que hb_eff
        """
        if city_type.lower() == 'large':
            # Ciudades grandes (metropolis)
            if frequency <= 200:
                a_hm = 8.29 * (self.xp.log10(1.54 * hm))**2 - 1.1
            else:
                a_hm = 3.2 * (self.xp.log10(11.75 * hm))**2 - 4.97
        else:
            # Ciudades medianas (default)
            a_hm = (1.1 * self.xp.log10(frequency) - 0.7) * hm - \
                   (1.56 * self.xp.log10(frequency) - 0.8)

        # Broadcast a shape de hb_eff
        return self.xp.asarray(a_hm) + self.xp.zeros_like(hb_eff)

    def _calculate_effective_height_vectorized(self, tx_height: float, tx_elevation: float,
                                               terrain_profiles: np.ndarray,
                                               d_km: np.ndarray) -> np.ndarray:
        """
        Calcula altura efectiva estadística por radial (Hata correcto)

        h_b,eff[i] = h_tx + z_tx - z_ref[i]

        donde z_ref[i] = PROMEDIO del perfil radial en rango [3-15km]

        Hata es un modelo ESTADÍSTICO macrocelular, NO geométrico.

        Args:
            tx_height: Altura de TX (AGL) en metros (escalar)
            tx_elevation: Elevación del terreno bajo TX (msnm) (escalar)
            terrain_profiles: Array (n_receptors, n_profile_samples) de elevaciones radiales
            d_km: Array (n_receptors,) de distancias en km

        Returns:
            Array (n_receptors,) de altura efectiva estadística
        """
        self.logger.debug(f"_calculate_effective_height_vectorized:")
        self.logger.debug(f"  terrain_profiles shape={terrain_profiles.shape}, d_km shape={d_km.shape}")

        # Validar terrain_profiles es 2D
        if len(terrain_profiles.shape) != 2:
            self.logger.error(f"terrain_profiles shape {terrain_profiles.shape}, se espera (n_receptors, n_samples)")
            if len(terrain_profiles.shape) == 1:
                n_receptors = len(d_km)
                if len(terrain_profiles) == n_receptors * 50:
                    terrain_profiles = terrain_profiles.reshape(n_receptors, 50)
                    self.logger.warning(f"Reshaped terrain_profiles a {terrain_profiles.shape}")
                else:
                    raise ValueError(f"Cannot reshape terrain_profiles from {len(terrain_profiles)}")

        n_receptors, n_samples = terrain_profiles.shape

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ESTADÍSTICA DEL TERRENO (Hata)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Crear distancias para TODO el perfil de cada receptor
        d_km_reshaped = d_km.reshape(-1, 1)  # (n_receptors, 1)
        t = self.xp.linspace(0.0, 1.0, n_samples)  # (n_samples,)
        profile_distances = d_km_reshaped * t  # (n_receptors, n_samples)

        # Rango [inner, outer] adaptado dinámicamente para mapas pequeños
        inner_km = max(self.terrain_reference_inner_km, 0.0)
        outer_km = max(self.terrain_reference_outer_km, inner_km)
        max_d = self.xp.max(d_km_reshaped)

        if max_d < outer_km:
            outer_km = max_d
            self.logger.debug(f"Adapted outer_km to {outer_km:.2f}km (map too small)")

        # Máscara para rango [inner, outer]
        mask = (profile_distances >= inner_km) & (profile_distances <= outer_km)  # (n_receptors, n_samples)

        # Contar muestras por receptor
        sample_counts = self.xp.sum(mask, axis=1)  # (n_receptors,)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # VECTORIZED z_ref calculation (SIN for loop) - 100x más rápido
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # 1. Media global por receptor (por fila)
        z_ref_global = self.xp.mean(terrain_profiles, axis=1)  # (n_receptors,)
        
        # 2. Media en rango [inner, outer] - usar nanmean con máscara
        terrain_masked = terrain_profiles.copy()
        terrain_masked[~mask] = self.xp.nan
        z_ref_annulus = self.xp.nanmean(terrain_masked, axis=1)  # (n_receptors,)
        
        # Reemplazar NaN con media global (fallback automático)
        z_ref_annulus = self.xp.where(
            self.xp.isnan(z_ref_annulus),
            z_ref_global,
            z_ref_annulus
        )
        
        # 3. Seleccionar según sample_count (VECTORIZADO)
        z_ref = self.xp.where(
            sample_counts >= self.terrain_min_samples,
            z_ref_annulus,
            z_ref_global
        )  # (n_receptors,)
        
        # Log de receptores con fallback (muestreo)
        n_fallback = int(self.xp.sum(sample_counts < self.terrain_min_samples))
        if n_fallback > 0 and n_fallback <= 10:
            fallback_indices = self.xp.where(sample_counts < self.terrain_min_samples)[0]
            for idx in fallback_indices[:5]:
                self.logger.debug(
                    f"Receptor {idx}: only {sample_counts[idx]} samples in [3-15km], using global mean"
                )
            if n_fallback > 5:
                self.logger.debug(f"... and {n_fallback - 5} more receptors with fallback")
        elif n_fallback > 10:
            self.logger.debug(f"Receptores con fallback (sin muestras suficientes): {n_fallback}")

        # Altura efectiva: h_b,eff = h_tx + z_tx - z_ref
        hb_effective = tx_height + tx_elevation - z_ref

        return hb_effective

    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna información del modelo

        Returns:
            Diccionario con metadatos del modelo
        """
        return {
            'name': self.name,
            'type': 'Semi-Empirical',
            'frequency_range': '1500-2000 MHz (COST-231)',
            'distance_range': '0.02-5 km (óptimo), extrapolable hasta 20 km',
            'tx_height_range': '30-200 m AGL',
            'mobile_height_range': '1-10 m',
            'environment': 'Urban (Suburban/Rural fuera de rango)',
            'city_types': ['large', 'medium'],
            'terrain_awareness': True,
            'vectorized': True,
            'gpu_compatible': True,
            'default_parameters': {
                'environment': 'Urban',
                'city_type': 'medium',
                'mobile_height': 1.5,
                'terrain_reference_method': 'global_mean',
            },
            'references': [
                'ITU-R P.1411 (Walfisch-Ikegami Urban)',
                'COST Action 231: "Digital Mobile Radio Towards Future Generation Systems"',
                'Hata, M. (1980), "Empirical Formula for Propagation Loss in Land Mobile Radio Services"',
            ]
        }
