"""
COST-231 Walfisch-Ikegami Model - Completo

Modelo semi-determinístico para propagación radioeléctrica en urban canyon
ITU-R P.1411-8 (Walfisch-Ikegami)

Caracteristicas:
- Valido: 800-2000 MHz, 0.02-5 km
- LOS/NLOS determinado dinamicamente del perfil de terreno
- CPU/GPU con abstraccion self.xp (NumPy/CuPy)
- Difraccion rooftop-to-street (Lrtd)
- Difraccion multi-pantalla (Lrts)
- Factor de orientacion calle (Lori)

Autores: David Montano, Dario Portilla
Universidad de Cuenca, 2025
"""

import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional


class COST231WalfischIkegamiModel:
    """
    Modelo COST-231 Walfisch-Ikegami completo

    Escenarios de aplicacion:
    - Simulaciones urbanas densas (urban canyon)
    - Frecuencias: 800-2000 MHz
    - Distancias: 20m a 5km
    - Cuando Okumura-Hata no es suficientemente preciso
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 compute_module=None):
        """
        Inicializa modelo COST-231

        Args:
            config: Diccionario de configuracion (opcional)
            compute_module: np (CPU) o cp (GPU CuPy). Default: np
        """
        self.name = "COST-231 Walfisch-Ikegami"
        self.model_type = "Semi-Empirical"
        self.config = config or {}

        # Abstraccion CPU/GPU
        self.xp = compute_module if compute_module is not None else np

        # Logger
        self.logger = logging.getLogger(f"models.{self.name}")

        # Parametros por defecto Cuenca
        self.defaults = {
            'environment': 'Urban',
            'building_height': 15.0,              # Altura tipica edificios (m)
            'street_width': 12.0,                 # Ancho tipico calles (m)
            'street_orientation': 0.0,            # Orientacion calle (grados)
            'mobile_height': 1.5,                 # Altura movil (m)
        }

        # Actualizables con config
        self.defaults.update(self.config)

        self.logger.info(f"Initialized {self.name}")
        self.logger.info(f"Compute module: {self.xp.__name__}")
        self.logger.info(f"Defaults: {self.defaults}")


    def calculate_path_loss(self,
                           distances: np.ndarray,
                           frequency: float,
                           tx_height: float,
                           terrain_heights: np.ndarray,
                           tx_elevation: float = 0.0,
                           environment: str = 'Urban',
                           mobile_height: float = 1.5,
                           building_height: float = 15.0,
                           street_width: float = 12.0,
                           street_orientation: float = 0.0,
                           **kwargs) -> np.ndarray:
        """
        Calcula Path Loss usando COST-231 Walfisch-Ikegami

        Ecuacion:
            PL_LOS = PL_free_space + Lrtd + Cf
            PL_NLOS = PL_free_space + Lrtd + Lmsd + Cf

        donde:
            PL_free_space: Perdida en espacio libre (32.45 + 20*log10(f) + 20*log10(d))
            Lrtd: Difraccion rooftop-to-street
            Lmsd: Difraccion multi-pantalla (solo NLOS)
            Cf: Correccion por ambiente
            Lori: Factor de orientacion calle

        Args:
            distances: Array distancias en metros (1D o 2D)
            frequency: Frecuencia en MHz (800-2000)
            tx_height: Altura antena TX en metros AGL (30-200m)
            terrain_heights: Array elevaciones terreno en msnm
            tx_elevation: Elevacion TX en msnm
            environment: 'Urban', 'Suburban', 'Rural'
            mobile_height: Altura movil en metros (1-10m)
            building_height: Altura tipica edificios (m)
            street_width: Ancho tipico calles (m)
            street_orientation: Orientacion calle vs TX (grados)

        Returns:
            Path Loss en dB (array de mismo shape que distances)
        """
        # Guardar shape original para remodelar al final
        original_shape = distances.shape
        distances_flat = self.xp.ravel(distances)
        terrain_heights_flat = self.xp.ravel(terrain_heights)

        # Validacion
        self._validate_parameters(frequency, distances_flat, tx_height, mobile_height)

        # Convertir distancias a km
        distances_km = distances_flat / 1000.0
        distances_km = self.xp.maximum(distances_km, 0.00001)  # Evitar log(0)

        # Altura efectiva TX
        terrain_avg = self.xp.mean(terrain_heights_flat)
        h_bs_eff = tx_height + tx_elevation - terrain_avg
        h_bs_eff = self.xp.maximum(h_bs_eff, 30.0)   # Minimo 30m
        h_bs_eff = self.xp.minimum(h_bs_eff, 200.0)  # Maximo 200m

        # Determinar LOS/NLOS
        los_mask = self._determine_los_nlos(
            distances_flat,
            tx_height,
            terrain_heights_flat,
            tx_elevation,
            mobile_height
        )

        # Path Loss base (Free Space)
        pl_base = self._calculate_base_path_loss(frequency, distances_km)

        # NOTA: Todas las alturas deben estar en AGL (Above Ground Level), no msnm
        # h_bs_eff: altura TX sobre terreno promedio (AGL)
        # building_height: altura tipica edificios (AGL)
        # mobile_height: altura movil (AGL)

        # En COST-231, todas las alturas son relativas:
        # delta_h_rm: altura TX - altura roof (ambas AGL)
        # delta_h_ms: altura roof - altura receptor (ambas AGL)

        # Convertir a arrays para cálculo vectorizado
        delta_h_rm_array = self.xp.full_like(distances_km, h_bs_eff - building_height)
        delta_h_ms_array = self.xp.full_like(distances_km, building_height - mobile_height)

        # Calcular Lrtd (Diffraction Loss Rooftop-to-Street)
        lrtd = self._calculate_lrtd(
            frequency,
            street_width,
            delta_h_rm_array,
            delta_h_ms_array,
            street_orientation
        )

        # Calcular Lmsd (Multi-Screen Diffraction) - solo NLOS
        lmsd = self.xp.zeros_like(distances_km)
        if self.xp.any(~los_mask):
            lmsd[~los_mask] = self._calculate_lmsd(
                frequency,
                distances_km[~los_mask],
                delta_h_ms_array[~los_mask],
                environment
            )

        # Correccion por ambiente
        cf = self._calculate_environment_correction(frequency, environment)

        # Path Loss final
        # LOS: PL = PL_base + Lrtd + Cf
        # NLOS: PL = PL_base + Lrtd + Lmsd + Cf
        pl_loss = pl_base + lrtd + lmsd + cf

        # Remodelar al shape original
        pl_loss = self.xp.reshape(pl_loss, original_shape)

        return pl_loss


    def _validate_parameters(self, frequency: float, distances: np.ndarray,
                            tx_height: float, mobile_height: float):
        """
        Valida parametros de entrada segun rango COST-231

        Rangos validos:
        - Frecuencia: 800-2000 MHz
        - Distancia: 0.02-5 km
        - Altura TX: 30-200m
        - Altura movil: 1-10m
        """
        # Frecuencia
        if frequency < 800 or frequency > 2000:
            self.logger.warning(
                f"Frequency {frequency} MHz outside valid range (800-2000 MHz)"
            )

        # Distancia
        d_min = self.xp.min(distances)
        d_max = self.xp.max(distances)
        d_min_km = d_min / 1000.0
        d_max_km = d_max / 1000.0

        if d_min_km < 0.02:
            self.logger.warning(
                f"Minimum distance {d_min_km:.4f} km below range (0.02 km min)"
            )
        if d_max_km > 5.0:
            self.logger.warning(
                f"Maximum distance {d_max_km:.2f} km above range (5.0 km max)"
            )

        # Altura TX
        if tx_height < 30 or tx_height > 200:
            self.logger.warning(
                f"TX height {tx_height}m outside valid range (30-200m)"
            )

        # Altura movil
        if mobile_height < 1 or mobile_height > 10:
            self.logger.warning(
                f"Mobile height {mobile_height}m outside valid range (1-10m)"
            )


    def _determine_los_nlos(self, distances: np.ndarray, tx_height: float,
                           terrain_heights: np.ndarray, tx_elevation: float,
                           mobile_height: float) -> np.ndarray:
        """
        Determina LOS/NLOS basado en heuristica de altura efectiva

        Algoritmo (Heuristica ITU-R P.1411):
        1. Calcular altura efectiva TX: h_eff = tx_height + tx_elevation
        2. Calcular altura promedio del terreno: h_avg = mean(terrain_heights)
        3. Diferencia de altura: delta_h = h_eff - h_avg

        Decision:
        - LOS si delta_h > 30m (TX suficientemente elevado sobre terreno)
        - NLOS si delta_h <= 30m (TX bajo relativo al terreno promedio)

        Justificacion:
        En areas urbanas montanosas (como Cuenca), la linea de vista entre
        TX y RX esta obstruida si ambos estan a alturas comparables.
        Solo cuando TX esta significativamente elevado (>30m) sobre el terreno
        se puede asumir LOS para la mayoria de receptores.

        Args:
            distances: Array distancias en metros
            tx_height: Altura TX AGL en metros
            terrain_heights: Array elevaciones en msnm
            tx_elevation: Elevacion TX en msnm
            mobile_height: Altura movil en metros

        Returns:
            Array booleano: True=LOS, False=NLOS
        """
        # Altura efectiva TX sobre datum (nivel del mar)
        h_tx_eff = tx_height + tx_elevation

        # Altura promedio del terreno en el area
        terrain_avg = self.xp.mean(terrain_heights)

        # Diferencia de elevacion: TX vs terreno
        delta_h = h_tx_eff - terrain_avg

        # Criterio de LOS/NLOS: 30m es threshold tipico para urban canyon
        # Si TX esta >30m sobre terreno promedio, hay LOS probable
        # Si TX esta <= 30m sobre terreno, hay NLOS probable (obstaculos)
        los_mask = self.xp.full(distances.shape, delta_h > 30.0, dtype=bool)

        return los_mask


    def _calculate_base_path_loss(self, frequency: float,
                                 distances_km: np.ndarray) -> np.ndarray:
        """
        Calcula Path Loss base (Free Space adaptado COST-231)

        Formula:
        PL(f,d) = 32.45 + 20*log10(f[MHz]) + 20*log10(d[km])

        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km (array)

        Returns:
            Path Loss base en dB
        """
        pl = (32.45 +
              20.0 * self.xp.log10(frequency) +
              20.0 * self.xp.log10(distances_km))

        return pl


    def _calculate_lrtd(self, frequency: float, street_width: float,
                       delta_h_rm: np.ndarray, delta_h_ms: np.ndarray,
                       street_orientation: float) -> np.ndarray:
        """
        Calcula Lrtd - Difraccion Rooftop-to-Street

        Formula COST-231:
        Lrtd = -16.9 - 10*log10(w) + 10*log10(f)
               + 20*log10(delta_h_rm) + Lori

        Pero cuando delta_h_rm <= 0 (RX mas alto que roof):
        Lrtd = -16.9 - 10*log10(w) + 10*log10(f)
               + 20*log10(|delta_h_rm|) - 5

        Args:
            frequency: Frecuencia en MHz
            street_width: Ancho calle en metros
            delta_h_rm: Diferencia altura (TX - roof) en metros (array)
            delta_h_ms: Diferencia altura (roof - MS) en metros (array)
            street_orientation: Orientacion calle en grados

        Returns:
            Lrtd en dB (array)
        """
        # Calcular factor de orientacion Lori
        lori = self._calculate_orientation_factor(street_orientation)

        # Asegurar valores positivos para log
        delta_h_rm = self.xp.maximum(delta_h_rm, 0.1)  # Minimo 0.1m
        street_width = self.xp.maximum(street_width, 0.5)  # Minimo 0.5m

        # Calcular Lrtd
        lrtd = (-16.9 -
                10.0 * self.xp.log10(street_width) +
                10.0 * self.xp.log10(frequency) +
                20.0 * self.xp.log10(delta_h_rm) +
                lori)

        return lrtd


    def _calculate_lmsd(self, frequency: float, distances_km: np.ndarray,
                       delta_h_ms: np.ndarray, environment: str) -> np.ndarray:
        """
        Calcula Lmsd - Difraccion Multi-Pantalla (solo NLOS)

        Formula:
        Lmsd = -18*log10(1 + delta_h_ms) + 10*log10(f) +
               10*log10(d) + C_env

        donde C_env depende del ambiente:
        - Urban: -4 dB
        - Suburban: -8 dB
        - Rural: -12 dB

        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km (array)
            delta_h_ms: Diferencia altura (roof - MS) en metros (array)
            environment: 'Urban', 'Suburban', 'Rural'

        Returns:
            Lmsd en dB (array)
        """
        # Correccion por ambiente
        c_env_dict = {
            'Urban': -4.0,
            'Suburban': -8.0,
            'Rural': -12.0
        }
        c_env = c_env_dict.get(environment, -4.0)

        # Asegurar valores positivos
        delta_h_ms = self.xp.maximum(delta_h_ms, 0.1)
        distances_km = self.xp.maximum(distances_km, 0.001)

        # Calcular Lmsd
        lmsd = (-18.0 * self.xp.log10(1.0 + delta_h_ms) +
                10.0 * self.xp.log10(frequency) +
                10.0 * self.xp.log10(distances_km) +
                c_env)

        return lmsd


    def _calculate_orientation_factor(self, street_orientation: float) -> float:
        """
        Calcula Lori - Factor de orientacion calle

        Formula:
        Lori = -10 + 0.354*phi              si   0 < phi <= 35
        Lori = 2.5 + 0.075*(phi - 35)       si  35 < phi <= 55
        Lori = 4 - 0.114*(phi - 55)         si  55 < phi <= 90

        Args:
            street_orientation: Orientacion de calle en grados (0-90)

        Returns:
            Lori en dB
        """
        # Normalizar a rango 0-90 grados (simetria)
        phi = abs(street_orientation) % 90.0

        if phi <= 35.0:
            lori = -10.0 + 0.354 * phi
        elif phi <= 55.0:
            lori = 2.5 + 0.075 * (phi - 35.0)
        else:  # phi <= 90.0
            lori = 4.0 - 0.114 * (phi - 55.0)

        return lori


    def _calculate_environment_correction(self, frequency: float,
                                         environment: str) -> float:
        """
        Calcula Cf - Correccion por tipo de ambiente

        Formula:
        Cf = 0 dB                                    (Urban)
        Cf = -2 - 5.4*log10(f)                       (Suburban)
        Cf = -4.78*(log10(f))^2 + 18.33*log10(f) - 40.94  (Rural)

        Args:
            frequency: Frecuencia en MHz
            environment: 'Urban', 'Suburban', 'Rural'

        Returns:
            Cf en dB
        """
        log_f = np.log10(frequency)

        if environment == 'Urban':
            cf = 0.0
        elif environment == 'Suburban':
            cf = -2.0 - 5.4 * log_f
        elif environment == 'Rural':
            cf = -4.78 * (log_f ** 2) + 18.33 * log_f - 40.94
        else:
            self.logger.warning(f"Unknown environment {environment}. Using Urban.")
            cf = 0.0

        return cf


    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna informacion del modelo

        Returns:
            Diccionario con metadatos del modelo
        """
        return {
            'name': self.name,
            'type': self.model_type,
            'frequency_range': '800-2000 MHz',
            'distance_range': '20m - 5km',
            'tx_height_range': '30-200m',
            'environments': ['Urban', 'Suburban', 'Rural'],
            'has_terrain_awareness': True,
            'default_parameters': self.defaults,
            'references': [
                'ITU-R P.1411-8 (Walfisch-Ikegami)',
                'COST-231 (European Cooperation in Science and Technology)'
            ]
        }
