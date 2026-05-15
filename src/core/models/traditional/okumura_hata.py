import numpy as np
import logging
import warnings

class OkumuraHataModel:
    """
    Implementación completa del modelo de propagación Okumura-Hata

    Modelo empírico para predicción de pérdidas de propagación en sistemas móviles.
    Basado en mediciones en ciudades japonesas por Okumura (1968) y
    formulación matemática de Hata (1980).

    Rangos de validez:
    - Frecuencia: 150 - 1500 MHz (básico), hasta 2000 MHz (COST-231 Hata)
    - Distancia: 1 - 20 km
    - Altura antena base (hb): 30 - 200 m
    - Altura móvil (hm): 1 - 10 m

    Soporta:
    - Tipos de ambiente: Urban, Suburban, Rural (Open Area)
    - Tipos de ciudad: Large City, Small/Medium City
    - Uso de elevación del terreno para altura efectiva
    - Cálculo vectorizado CPU/GPU (NumPy/CuPy)
    """

    def __init__(self, config=None, compute_module=None):
        """
        Inicializa el modelo Okumura-Hata

        Args:
            config: Diccionario de configuración (opcional)
            compute_module: numpy o cupy para CPU/GPU
        """
        self.config = config or {}
        self.logger = logging.getLogger("OkumuraHataModel")
        self.name = "Okumura-Hata"

        # Módulo de cómputo (numpy o cupy)
        self.xp = compute_module if compute_module is not None else np

        # Parámetros configurables con valores por defecto
        self.mobile_height = self.config.get('mobile_height', 1.5)  # metros
        self.environment = self.config.get('environment', 'Urban')  # Urban/Suburban/Rural
        self.city_type = self.config.get('city_type', 'medium')  # large/medium
        # Método de referencia de terreno para altura efectiva de BS.
        # global_mean mantiene compatibilidad con resultados históricos.
        self.terrain_reference_method = self.config.get('terrain_reference_method', 'global_mean')
        self.terrain_reference_inner_km = float(self.config.get('terrain_reference_inner_km', 3.0))
        self.terrain_reference_outer_km = float(self.config.get('terrain_reference_outer_km', 15.0))
        self.terrain_min_samples = int(self.config.get('terrain_min_samples', 50))

    def calculate_path_loss(self, distances, frequency, tx_height, terrain_heights,
                           tx_elevation=0.0, terrain_profiles=None, environment='Urban',
                           city_type='medium', mobile_height=None, **kwargs):
        """
        Calcula pérdida de propagación usando Okumura-Hata completo

        Args:
            distances: Array de distancias en METROS
            frequency: Frecuencia en MHz (150-2000 MHz)
            tx_height: Altura de antena transmisora sobre el suelo (AGL) en metros
            terrain_heights: Array con elevaciones del terreno en cada punto (msnm)
            tx_elevation: Elevación del terreno en la ubicación del TX (msnm)
            terrain_profiles: Array opcional de perfiles radiales por receptor para altura efectiva
            environment: Tipo de ambiente - 'Urban', 'Suburban', 'Rural'
            city_type: Tipo de ciudad - 'large' o 'medium' (solo para Urban)
            mobile_height: Altura del móvil en metros (default: 1.5m)
            **kwargs: Parámetros adicionales

        Returns:
            dict con keys: 'path_loss' (array), 'hb_effective' (array),
                          'validity_mask' (bool array), 'valid_count' (int)
        """
        self.logger.debug(f"Calculating Okumura-Hata: f={frequency}MHz, env={environment}")

        # Usar valores por defecto si no se especifican
        if mobile_height is None:
            mobile_height = self.mobile_height

        # Validar rangos del modelo
        self._validate_parameters(frequency, tx_height, mobile_height)

        # Convertir distancias a km
        d_km_real = distances / 1000.0
        
        # Distancia para modelo Hata (clamp a 1 km para estabilidad numérica)
        # Usar d_km_real para validez, d_km_model para cálculos (evita log(0))
        d_km_model = self.xp.maximum(d_km_real, 1.0)

        # ALTURA EFECTIVA DE LA ANTENA BASE
        # h_b,eff = h_tx + z_tx - z_ref
        # z_ref depende del método configurado (legacy global_mean o referencia local).
        if terrain_profiles is not None:
            # Si terrain_profiles es pasado, aplanar d_km también para coherencia
            original_shape = d_km_model.shape
            d_km_flat = d_km_model.ravel()
            self.logger.info(f"Flattening for terrain_profiles: original d_km_model.shape={original_shape}, flat shape={d_km_flat.shape}")
            
            hb_effective = self._calculate_effective_height_vectorized(
                tx_height, tx_elevation, terrain_profiles, d_km_flat
            )
            
            # Reshape hb_effective de vuelta a la forma original
            hb_effective = hb_effective.reshape(original_shape)
            self.logger.debug("Using vectorized effective height with terrain profiles")
        else:
            terrain_reference = self._compute_terrain_reference(terrain_heights, d_km_model)
            hb_effective = self.xp.full(d_km_model.shape, tx_height + tx_elevation - terrain_reference)
            self.logger.debug("Using legacy terrain reference method (global_mean)")

        # VALIDEZ DEL MODELO
        # Separar validez matemática (rango Hata) de estabilidad numérica
        # Distancia: Hata válido solo en [1-20km] (no <1km)
        validity_distance = (d_km_real >= 1.0) & (d_km_real <= 20.0)
        validity_height = (hb_effective >= 30.0) & (hb_effective <= 200.0)
        
        # Máscara de validez combinada
        validity_mask = validity_distance & validity_height
        valid_count = int(self.xp.sum(validity_mask))
        
        # Log de receptores fuera de rango
        n_out_distance = int(self.xp.sum(~validity_distance))
        n_out_height = int(self.xp.sum(~validity_height))
        if n_out_distance > 0:
            self.logger.warning(f"Receptores fuera de rango distancia (1-20km): {n_out_distance}")
        if n_out_height > 0:
            self.logger.warning(f"Receptores con h_b,eff fuera de rango (30-200m): {n_out_height}")

        hm = mobile_height

        # FACTOR DE CORRECCIÓN POR ALTURA MÓVIL a(hm) - Vectorizado explícito
        a_hm = self._calculate_mobile_height_correction_vectorized(
            frequency, hm, city_type, hb_effective
        )

        # PATH LOSS URBANO (fórmula base de Okumura-Hata)
        # L_urban = 69.55 + 26.16*log10(f) - 13.82*log10(hb) - a(hm)
        #           + (44.9 - 6.55*log10(hb))*log10(d)
        # SEPARACIÓN: FÍSICA vs ESTABILIDAD NUMÉRICA
        # hb_effective = altura física real (puede ser negativa, para validación)
        # hb_safe = clamped a 30.0 para mantener coherencia estadística Hata
        #          (no 1.0: evita singularidades y mantiene dominio válido del modelo)
        hb_safe = self.xp.maximum(hb_effective, 30.0)

        path_loss_urban = (
            69.55
            + 26.16 * self.xp.log10(frequency)
            - 13.82 * self.xp.log10(hb_safe)
            - a_hm
            + (44.9 - 6.55 * self.xp.log10(hb_safe)) * self.xp.log10(d_km_model)
        )

        # CORRECCIONES POR TIPO DE AMBIENTE Y COST-231
        # Orden correcto: Cm primero (base), luego correcciones de ambiente
        
        # 1. Calcular base con COST-231 si aplica (solo para ambiente urbano)
        if frequency > 1500 and environment.lower() == 'urban':
            # COST-231 Hata suma Cm sobre la base L_urban
            # Cm = 0 dB para ciudades medianas y áreas suburbanas
            # Cm = 3 dB para centros metropolitanos
            if city_type.lower() == 'large':
                Cm = 3.0
            else:
                Cm = 0.0
            path_loss_base = path_loss_urban + Cm
            self.logger.debug(f"Applied COST-231 extension (Cm={Cm}dB) for f>{1500}MHz in Urban environment")
        else:
            path_loss_base = path_loss_urban

        # 2. Aplicar correcciones de ambiente a la base calculada
        if environment.lower() == 'suburban':
            # Corrección para ambiente suburbano
            # L_suburban = L_base - 2*[log10(f/28)]^2 - 5.4
            correction = 2 * (self.xp.log10(frequency / 28.0))**2 + 5.4
            path_loss = path_loss_base - correction
            self.logger.debug("Applied Suburban correction")

        elif environment.lower() == 'rural':
            # Corrección para área rural abierta (open area)
            # L_rural = L_base - 4.78*[log10(f)]^2 + 18.33*log10(f) - 40.94
            f_term = self.xp.log10(frequency)
            correction = 4.78 * (f_term**2) - 18.33 * f_term + 40.94
            path_loss = path_loss_base - correction
            self.logger.debug("Applied Rural correction")

        else:  # Urban (default)
            path_loss = path_loss_base
            self.logger.debug("Using Urban (standard) model")

        # NOTA IMPORTANTE: NO usamos NaN masking agresivo
        # Hata fuera de rango [30-200m] sigue siendo calculable (solo menos preciso)
        # Mantenemos extrapolación profesional como en Atoll (no invalidamos celdas)
        # validity_mask se retorna como METADATO de confianza, no como criterio de eliminación

        # Retornar diccionario con path_loss y metadatos de validez
        return {
            'path_loss': path_loss,
            'hb_effective': hb_effective,
            'validity_mask': validity_mask,
            'valid_count': valid_count,
        }

    def _compute_terrain_reference(self, terrain_heights, distances_km):
        """
        Calcula z_ref para la altura efectiva de BS.

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
                f"Okumura-Hata local_annulus_mean fallback to global_mean: "
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
                f"Okumura-Hata tx_local_mean fallback to global_mean: "
                f"samples={sample_count}, min_required={self.terrain_min_samples}"
            )
            return terrain_global_mean

        self.logger.warning(
            f"Unknown terrain_reference_method='{self.terrain_reference_method}', using global_mean"
        )
        return terrain_global_mean

    def _calculate_mobile_height_correction(self, frequency, hm, city_type):
        """
        Calcula el factor de corrección a(hm) por altura del móvil (legacy)

        Args:
            frequency: Frecuencia en MHz
            hm: Altura móvil en metros
            city_type: 'large' o 'medium'

        Returns:
            Factor de corrección a(hm) en dB
        """
        if city_type.lower() == 'large':
            # Para ciudades grandes (metropolis)
            if frequency <= 200:
                # f <= 200 MHz
                a_hm = 8.29 * (self.xp.log10(1.54 * hm))**2 - 1.1
            else:
                # f >= 400 MHz (se usa para todo f > 200 en la práctica)
                a_hm = 3.2 * (self.xp.log10(11.75 * hm))**2 - 4.97
        else:
            # Para ciudades pequeñas/medianas (default)
            # a(hm) = (1.1*log10(f) - 0.7)*hm - (1.56*log10(f) - 0.8)
            a_hm = (1.1 * self.xp.log10(frequency) - 0.7) * hm - \
                   (1.56 * self.xp.log10(frequency) - 0.8)

        return a_hm

    def _calculate_mobile_height_correction_vectorized(self, frequency, hm, city_type, hb_eff):
        """
        Calcula el factor de corrección a(hm) de forma explícitamente vectorizada
        Asegura broadcast correcto cuando hb_eff es un array por receptor.

        Args:
            frequency: Frecuencia en MHz (escalar)
            hm: Altura móvil en metros (escalar)
            city_type: 'large' o 'medium' (escalar)
            hb_eff: Array de altura efectiva clipeada (para broadcast shape)

        Returns:
            Array de corrección a(hm) con mismo shape que hb_eff
        """
        if city_type.lower() == 'large':
            if frequency <= 200:
                a_hm = 8.29 * (self.xp.log10(1.54 * hm))**2 - 1.1
            else:
                a_hm = 3.2 * (self.xp.log10(11.75 * hm))**2 - 4.97
        else:
            a_hm = (1.1 * self.xp.log10(frequency) - 0.7) * hm - \
                   (1.56 * self.xp.log10(frequency) - 0.8)

        return self.xp.asarray(a_hm) + self.xp.zeros_like(hb_eff)

    def _calculate_effective_height_vectorized(self, tx_height, tx_elevation, terrain_profiles, d_km):
        """
        Calcula altura efectiva estadística por radial (Okumura-Hata correcto)
        
        FÍSICAMENTE CORRECTO según Hata:
        h_b,eff[i] = h_tx + z_tx - z_ref[i]
        
        donde z_ref[i] = PROMEDIO del perfil radial en rango [3-15km]
        NO la elevación del receptor individual (eso sería point-to-point)
        
        Hata es un modelo ESTADÍSTICO macrocelular, NO geométrico.
        
        Args:
            tx_height: Altura de TX (AGL) en metros (escalar)
            tx_elevation: Elevación del terreno bajo TX (msnm) (escalar)
            terrain_profiles: Array (n_receptors, n_profile_samples) de elevaciones radiales
            d_km: Array (n_receptors,) de distancias en km a cada receptor

        Returns:
            Array (n_receptors,) de altura efectiva estadística por receptor
        """
        self.logger.info(f"_calculate_effective_height_vectorized (Hata estadístico):")
        self.logger.info(f"  terrain_profiles shape={terrain_profiles.shape}, d_km shape={d_km.shape}")
        
        # Validar que terrain_profiles es 2D
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
        
        # === ESTADÍSTICA DEL TERRENO (Hata) ===
        # Crear distancias para TODO el perfil de cada receptor
        d_km_reshaped = d_km.reshape(-1, 1)  # (n_receptors, 1)
        t = self.xp.linspace(0.0, 1.0, n_samples)  # (n_samples,) desde TX(0) a RX(1)
        profile_distances = d_km_reshaped * t  # (n_receptors, n_samples) - broadcast
        
        # Máscara para rango [inner_km, outer_km] - adaptado dinámicamente para mapas pequeños
        # Para mapas pequeños donde receptores están a <15km, usar distancia máxima como límite
        # Esto evita ventana vacía y z_ref inestable en simulaciones locales
        inner_km = self.terrain_reference_inner_km
        outer_km = self.xp.minimum(self.terrain_reference_outer_km, self.xp.max(d_km_reshaped))
        
        mask_annulus = (profile_distances >= inner_km) & (profile_distances <= outer_km)
        sample_counts = self.xp.sum(mask_annulus, axis=1)  # (n_receptors,)
        
        # z_ref = promedio del terreno EN EL RANGO [3-15km] de CADA radial
        # Esto es ESTADÍSTICO (media), NO geométrico (punto individual)
        z_ref = self.xp.full(n_receptors, self.xp.nan)
        
        sufficient_mask = sample_counts >= self.terrain_min_samples
        
        if self.xp.any(sufficient_mask):
            # Donde hay suficientes muestras en [3-15km], usar esa media
            masked_profile = self.xp.where(mask_annulus, terrain_profiles, self.xp.nan)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                z_ref_annulus = self.xp.nanmean(masked_profile, axis=1)
            z_ref = self.xp.where(sufficient_mask, z_ref_annulus, self.xp.nan)
        
        # Fallback: donde NO hay suficientes muestras en [3-15km], usar todo el perfil
        insufficient_mask = ~sufficient_mask
        if self.xp.any(insufficient_mask):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                z_ref_full = self.xp.nanmean(terrain_profiles, axis=1)
            z_ref = self.xp.where(insufficient_mask, z_ref_full, z_ref)
            
            # Log de fallbacks
            n_insufficient = int(self.xp.sum(insufficient_mask))
            if n_insufficient > 0:
                insufficient_idx = self.xp.where(insufficient_mask)[0]
                for idx in insufficient_idx[::max(1, len(insufficient_idx)//3)][:2]:
                    cnt = int(sample_counts[idx])
                    self.logger.info(
                        f"  Radial {idx}: insufficient [3-15km] samples ({cnt}<{self.terrain_min_samples}), "
                        f"using full profile mean={z_ref[idx]:.1f}m"
                    )
        
        # FÍSICA: Altura efectiva según Hata
        # h_b,eff = h_tx (AGL) + z_tx (MSL) - z_ref (estadístico MSL)
        hb_effective = tx_height + tx_elevation - z_ref
        
        self.logger.info(f"  z_ref: min={self.xp.nanmin(z_ref):.1f}, max={self.xp.nanmax(z_ref):.1f}, mean={self.xp.nanmean(z_ref):.1f}m")
        self.logger.info(f"  h_b,eff: min={self.xp.nanmin(hb_effective):.1f}, max={self.xp.nanmax(hb_effective):.1f}, mean={self.xp.nanmean(hb_effective):.1f}m")
        
        return hb_effective

    def _validate_parameters(self, frequency, tx_height, mobile_height):
        """
        Valida que los parámetros estén dentro de los rangos del modelo

        Args:
            frequency: Frecuencia en MHz
            tx_height: Altura de TX en metros
            mobile_height: Altura móvil en metros

        Raises:
            Warning si los parámetros están fuera de rango
        """
        warnings = []

        if frequency < 150 or frequency > 2000:
            warnings.append(
                f"Frecuencia {frequency}MHz fuera de rango válido (150-2000 MHz)"
            )

        if tx_height < 30 or tx_height > 200:
            warnings.append(
                f"Altura de antena {tx_height}m fuera de rango válido (30-200m)"
            )

        if mobile_height < 1 or mobile_height > 10:
            warnings.append(
                f"Altura móvil {mobile_height}m fuera de rango válido (1-10m)"
            )

        if warnings:
            for warning in warnings:
                self.logger.warning(warning)
                self.logger.warning("Resultados pueden ser imprecisos fuera de rangos validados")

    def get_model_info(self):
        """Retorna información sobre el modelo"""
        return {
            'name': 'Okumura-Hata',
            'type': 'Empírico',
            'frequency_range': '150-2000 MHz',
            'distance_range': '1-20 km',
            'description': 'Modelo empírico para sistemas móviles celulares',
            'environments': ['Urban', 'Suburban', 'Rural'],
            'city_types': ['large', 'medium'],
            'terrain_reference_method': self.terrain_reference_method,
            'terrain_reference_inner_km': self.terrain_reference_inner_km,
            'terrain_reference_outer_km': self.terrain_reference_outer_km,
            'terrain_min_samples': self.terrain_min_samples,
        }