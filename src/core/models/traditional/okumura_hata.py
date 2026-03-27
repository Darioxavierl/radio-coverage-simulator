import numpy as np
import logging

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

    def calculate_path_loss(self, distances, frequency, tx_height, terrain_heights,
                           tx_elevation=0.0, environment='Urban', city_type='medium',
                           mobile_height=None, **kwargs):
        """
        Calcula pérdida de propagación usando Okumura-Hata completo

        Args:
            distances: Array de distancias en METROS
            frequency: Frecuencia en MHz (150-2000 MHz)
            tx_height: Altura de antena transmisora sobre el suelo (AGL) en metros
            terrain_heights: Array con elevaciones del terreno en cada punto (msnm)
            tx_elevation: Elevación del terreno en la ubicación del TX (msnm)
            environment: Tipo de ambiente - 'Urban', 'Suburban', 'Rural'
            city_type: Tipo de ciudad - 'large' o 'medium' (solo para Urban)
            mobile_height: Altura del móvil en metros (default: 1.5m)
            **kwargs: Parámetros adicionales

        Returns:
            Array con path loss en dB
        """
        self.logger.debug(f"Calculating Okumura-Hata: f={frequency}MHz, env={environment}")

        # Usar valores por defecto si no se especifican
        if mobile_height is None:
            mobile_height = self.mobile_height

        # Validar rangos del modelo
        self._validate_parameters(frequency, tx_height, mobile_height)

        # Convertir distancias a km
        d_km = distances / 1000.0

        # Evitar log de 0 (distancia mínima 1 metro = 0.001 km)
        d_km = self.xp.maximum(d_km, 0.001)

        # ALTURA EFECTIVA DE LA ANTENA BASE
        # Considera la elevación del terreno en TX y elevación promedio del área
        # hb_effective = altura_antena + elevacion_tx - elevacion_promedio_area
        terrain_avg = self.xp.mean(terrain_heights)
        hb_effective = tx_height + tx_elevation - terrain_avg

        # Asegurar que hb esté dentro de rangos válidos
        hb_effective = self.xp.maximum(hb_effective, 30.0)  # Mínimo 30m
        hb_effective = self.xp.minimum(hb_effective, 200.0)  # Máximo 200m

        hm = mobile_height

        # FACTOR DE CORRECCIÓN POR ALTURA MÓVIL a(hm)
        a_hm = self._calculate_mobile_height_correction(frequency, hm, city_type)

        # PATH LOSS URBANO (fórmula base de Okumura-Hata)
        # L_urban = 69.55 + 26.16*log10(f) - 13.82*log10(hb) - a(hm)
        #           + (44.9 - 6.55*log10(hb))*log10(d)

        path_loss_urban = (
            69.55
            + 26.16 * self.xp.log10(frequency)
            - 13.82 * self.xp.log10(hb_effective)
            - a_hm
            + (44.9 - 6.55 * self.xp.log10(hb_effective)) * self.xp.log10(d_km)
        )

        # CORRECCIONES POR TIPO DE AMBIENTE
        if environment.lower() == 'suburban':
            # Corrección para ambiente suburbano
            # L_suburban = L_urban - 2*[log10(f/28)]^2 - 5.4
            correction = 2 * (self.xp.log10(frequency / 28.0))**2 + 5.4
            path_loss = path_loss_urban - correction
            self.logger.debug("Applied Suburban correction")

        elif environment.lower() == 'rural':
            # Corrección para área rural abierta (open area)
            # L_rural = L_urban - 4.78*[log10(f)]^2 + 18.33*log10(f) - 40.94
            f_term = self.xp.log10(frequency)
            correction = 4.78 * (f_term**2) - 18.33 * f_term + 40.94
            path_loss = path_loss_urban - correction
            self.logger.debug("Applied Rural correction")

        else:  # Urban (default)
            path_loss = path_loss_urban
            self.logger.debug("Using Urban (standard) model")

        # EXTENSIÓN COST-231 para frecuencias > 1500 MHz
        if frequency > 1500:
            # COST-231 Hata añade un factor de corrección
            # Cm = 0 dB para ciudades medianas y áreas suburbanas
            # Cm = 3 dB para centros metropolitanos
            if environment.lower() == 'urban' and city_type.lower() == 'large':
                Cm = 3.0
            else:
                Cm = 0.0

            path_loss = path_loss + Cm
            self.logger.debug(f"Applied COST-231 extension (Cm={Cm}dB) for f>{1500}MHz")

        return path_loss

    def _calculate_mobile_height_correction(self, frequency, hm, city_type):
        """
        Calcula el factor de corrección a(hm) por altura del móvil

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
            'city_types': ['large', 'medium']
        }