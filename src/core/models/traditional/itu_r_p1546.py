"""
ITU-R P.1546-6 Propagation Model - Completo

Modelo punto-to-area para predicciones de cobertura terrestre
Rango de frecuencias: 30 MHz a 4000 MHz

Referencia: ITU-R P.1546-6 (August 2019)
"Method for point-to-area predictions for terrestrial services
in the frequency range 30 MHz to 4 000 MHz"

Caracteristicas:
- Valido: 30-4000 MHz, 1-1000 km
- LOS/NLOS determinado por radio horizon distance
- CPU/GPU con abstraccion self.xp (NumPy/CuPy)
- Correcciones por altura, frecuencia, ambiente y terreno
- Point-to-area model (coverage planning)

Autores: David Montano, Dario Portilla
Universidad de Cuenca, 2025
"""

import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional


class ITUR_P1546Model:
    """
    Modelo ITU-R P.1546-6 completo

    Escenarios de aplicacion:
    - Planificacion de cobertura en bandas VHF/UHF/SHF
    - Frecuencias: 30 MHz a 4000 MHz
    - Distancias: 1 km a 1000 km
    - Aplicable a sistemas moviles, radiodifusion, punto fijo
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 compute_module=None):
        """
        Inicializa modelo ITU-R P.1546

        Args:
            config: Diccionario de configuracion (opcional)
            compute_module: np (CPU) o cp (GPU CuPy). Default: np
        """
        self.name = "ITU-R P.1546"
        self.model_type = "Point-to-Area Empirical"
        self.config = config or {}

        # Abstraccion CPU/GPU
        self.xp = compute_module if compute_module is not None else np

        # Logger
        self.logger = logging.getLogger(f"models.{self.name}")

        # Parametros por defecto
        self.defaults = {
            'environment': 'Urban',           # Urban/Suburban/Rural
            'terrain_type': 'mixed',          # smooth/mixed/irregular
            'earth_radius_factor': 4/3,       # k factor, standard atmosphere
            'frequency_correction': True,     # Apply f > 300 MHz correction
            'mobile_height': 1.5,             # Altura movil (m)
        }

        # Actualizable con config
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
                           terrain_type: str = 'mixed',
                           mobile_height: float = 1.5,
                           **kwargs) -> np.ndarray:
        """
        Calcula Path Loss usando ITU-R P.1546

        Ecuacion:
            PL = L0 + Δh + Δf + Δenv

        donde:
            L0: Free space baseline
            Δh: Height correction (TX + RX height dependent)
            Δf: Frequency correction (para f > 300 MHz)
            Δenv: Environment/terrain correction

        Args:
            distances: Array distancias en metros (1D o 2D)
            frequency: Frecuencia en MHz (30-4000)
            tx_height: Altura antena TX en metros AGL (10-3000m)
            terrain_heights: Array elevaciones del terreno (msnm)
            tx_elevation: Elevacion del sitio TX en msnm (default 0)
            environment: Tipo ambiente (Urban/Suburban/Rural)
            terrain_type: Tipo terreno (smooth/mixed/irregular)
            mobile_height: Altura receptor en metros AGL (1-20m)
            **kwargs: Parametros adicionales ignorados

        Returns:
            Array path loss en dB (mismo shape que distances)
        """
        # Guardar shape original
        original_shape = distances.shape

        # Convertir a arrays si no lo son
        distances_flat = self.xp.atleast_1d(distances).flatten().astype(float)
        terrain_heights_flat = self.xp.atleast_1d(terrain_heights).flatten().astype(float)

        # Validar rangos de entrada
        self._validate_parameters(frequency, distances_flat, tx_height,
                                 mobile_height, environment, terrain_type)

        # Convertir distancias de metros a km
        distances_km = distances_flat / 1000.0

        # 1. Calcular path loss en espacio libre (baseline)
        pl_base = self._calculate_base_path_loss(frequency, distances_km)

        # 2. Determinar LOS/NLOS
        radio_horizon_km = self._calculate_radio_horizon(tx_height, mobile_height)
        is_los = distances_km <= radio_horizon_km

        # 3. Calcular altura efectiva del TX
        tx_height_eff = tx_height + tx_elevation - self.xp.mean(terrain_heights_flat)

        # 4. Calcular correcciones por altura
        height_correction = self._calculate_height_correction(
            frequency, tx_height, mobile_height, distances_km, is_los
        )

        # 5. Calcular correcciones por frecuencia (f > 300 MHz)
        freq_correction = self._calculate_frequency_correction(
            frequency, distances_km
        )

        # 6. Calcular correcciones por ambiente y terreno
        env_correction = self._calculate_environment_correction(
            frequency, distances_km, environment, terrain_type, is_los
        )

        # 7. Sumar componentes
        path_loss = pl_base + height_correction + freq_correction + env_correction

        # Remodelar al shape original
        path_loss_shaped = path_loss.reshape(original_shape)

        self.logger.debug(f"Path loss calculated: min={self.xp.min(path_loss_shaped):.1f} dB, "
                         f"max={self.xp.max(path_loss_shaped):.1f} dB, "
                         f"LOS points: {self.xp.sum(is_los)}/{len(is_los)}")

        return path_loss_shaped


    def _calculate_base_path_loss(self, frequency: float, distances_km: np.ndarray) -> np.ndarray:
        """
        Calcula path loss en espacio libre (Free Space baseline)

        Formula:
            L0 = 20·log10(f[MHz]) + 20·log10(d[km]) + 32.45

        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km

        Returns:
            Array de L0 en dB
        """
        # Proteger contra log(0)
        distances_km_safe = self.xp.maximum(distances_km, 0.001)

        l0 = (20 * self.xp.log10(frequency) +
              20 * self.xp.log10(distances_km_safe) +
              32.45)

        return l0


    def _calculate_radio_horizon(self, tx_height: float, rx_height: float) -> float:
        """
        Calcula distancia de radio horizon (LOS/NLOS boundary)

        Formula:
            d_ho = 4.12 · √(h_tx · h_rx) / 100  [km]

        donde:
            h_tx: Altura TX en metros
            h_rx: Altura RX en metros
            k = 4/3 (standard atmosphere)

        Args:
            tx_height: Altura TX en metros AGL
            rx_height: Altura RX en metros AGL

        Returns:
            Radio horizon en km
        """
        # Formula: 4.12 * sqrt(h_tx * h_rx) / 100 = distancia en km
        d_ho = 4.12 * self.xp.sqrt(tx_height * rx_height) / 100.0
        return float(d_ho) if hasattr(d_ho, '__float__') else float(d_ho.item()) if len(d_ho) == 1 else float(d_ho)


    def _calculate_height_correction(self, frequency: float, tx_height: float,
                                    rx_height: float, distances_km: np.ndarray,
                                    is_los: np.ndarray) -> np.ndarray:
        """
        Calcula correccion por altura (Δh)

        Depende de:
        - TX height (10-3000 m): altura mayor → menor path loss
        - RX height (1-20 m): altura mayor → menor path loss
        - Distance
        - LOS/NLOS condition

        Convención: Valores NEGATIVOS = ganancia (reduce path loss)
                    Valores POSITIVOS = atenuación (aumenta path loss)

        Args:
            frequency: Frecuencia en MHz
            tx_height: Altura TX en metros
            rx_height: Altura RX en metros
            distances_km: Distancias en km
            is_los: Array booleano LOS/NLOS

        Returns:
            Array de correcciones en dB (negativos = ganancia)
        """
        # Correccion RX: mayor altura RX → ganancia (negativo)
        # Normalizado a 10m como referencia
        rx_correction = -20 * self.xp.log10(rx_height / 10.0)

        # Correccion TX: mayor altura TX → ganancia (negativo)
        # Normalizado a 200m como referencia
        # En LOS: efecto completo de altura
        # En NLOS: efecto reducido por difracción
        tx_factor = self.xp.log10(tx_height / 200.0)

        # Factor por distancia
        distance_factor = 10 * self.xp.log10(self.xp.maximum(distances_km, 1.0)) / 10.0

        # Combinar: LOS tiene efecto completo, NLOS tiene efecto reducido
        tx_correction = self.xp.where(
            is_los,
            -20 * tx_factor - distance_factor,          # LOS: ganancia completa (negativo)
            -10 * tx_factor - 0.5 * distance_factor     # NLOS: ganancia reducida (negativo)
        )

        # Total: combinación de ganancias (valores negativos)
        delta_h = rx_correction + tx_correction

        return delta_h


    def _calculate_frequency_correction(self, frequency: float,
                                       distances_km: np.ndarray) -> np.ndarray:
        """
        Calcula correccion por frecuencia (Δf)

        Solo aplica para f > 300 MHz

        Aproximacion:
            Δf = 10·log10(f/1000)  para f > 300 MHz
            Δf = 0 dB               para f ≤ 300 MHz

        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km (para shape)

        Returns:
            Array de correcciones en dB
        """
        if frequency > 300:
            delta_f = 10 * self.xp.log10(max(frequency, 100) / 1000.0)
        else:
            delta_f = 0.0

        # Retornar array del tamaño correcto
        delta_f_array = self.xp.full_like(distances_km, delta_f, dtype=float)

        return delta_f_array


    def _calculate_environment_correction(self, frequency: float,
                                         distances_km: np.ndarray,
                                         environment: str,
                                         terrain_type: str,
                                         is_los: np.ndarray) -> np.ndarray:
        """
        Calcula correccion por ambiente y terreno (Δenv)

        Combina:
        - Tipo de ambiente (Urban/Suburban/Rural)
        - Tipo de terreno (Smooth/Mixed/Irregular)
        - Condicion LOS/NLOS

        Baseline: Urban/Mixed es 0 dB
        Suburban/Smooth: ganancia (menos atenuacion)
        Rural/Irregular: penalizacion (mas atenuacion)

        Args:
            frequency: Frecuencia en MHz
            distances_km: Distancias en km
            environment: Urban/Suburban/Rural
            terrain_type: smooth/mixed/irregular
            is_los: Array booleano LOS/NLOS

        Returns:
            Array de correcciones en dB
        """
        delta_env = self.xp.zeros_like(distances_km)

        # Correccion por ambiente (frecuencia dependiente)
        # A mayor frecuencia, mayor diferencia entre ambientes
        freq_factor = self.xp.log10(max(frequency, 50) / 1000.0)

        # Baseline: Urban
        if environment.lower() == 'urban':
            env_correction = 0.0
        elif environment.lower() == 'suburban':
            # Ganancia: menos edificios, mejor propagacion
            env_correction = -2.0 - 3.0 * freq_factor
        elif environment.lower() == 'rural':
            # Mayor ganancia: propagacion mejor
            env_correction = -4.0 - 5.0 * freq_factor
        else:
            env_correction = 0.0

        # Correccion por tipo de terreno
        # Baseline: Mixed
        if terrain_type.lower() == 'smooth':
            terrain_correction = -2.0      # Agua, llanura plana
        elif terrain_type.lower() == 'mixed':
            terrain_correction = 0.0       # Baseline
        elif terrain_type.lower() == 'irregular':
            terrain_correction = 3.0       # Montanas, bosques
        else:
            terrain_correction = 0.0

        # En NLOS, el efecto ambiente y terreno es mas importante
        correction_factor = self.xp.where(is_los, 0.7, 1.0)

        delta_env = (env_correction + terrain_correction) * correction_factor

        return self.xp.full_like(distances_km, delta_env, dtype=float)


    def _validate_parameters(self, frequency: float, distances: np.ndarray,
                            tx_height: float, rx_height: float,
                            environment: str, terrain_type: str):
        """
        Valida parametros de entrada

        Args:
            frequency: Frecuencia en MHz
            distances: Array distancias en km
            tx_height: Altura TX en metros
            rx_height: Altura RX en metros
            environment: Tipo ambiente
            terrain_type: Tipo terreno
        """
        # Validar frecuencia
        if frequency < 30 or frequency > 4000:
            self.logger.warning(f"Frequency {frequency} MHz outside valid range "
                              f"(30-4000 MHz). Results may be inaccurate.")

        # Validar distancia
        if self.xp.min(distances) < 1:
            self.logger.warning(f"Minimum distance {self.xp.min(distances):.1f} km "
                              f"< 1 km (minimum valid range)")
        if self.xp.max(distances) > 1000:
            self.logger.warning(f"Maximum distance {self.xp.max(distances):.1f} km "
                              f"> 1000 km (maximum valid range)")

        # Validar altura TX
        if tx_height < 10 or tx_height > 3000:
            self.logger.warning(f"TX height {tx_height} m outside valid range "
                              f"(10-3000 m)")

        # Validar altura RX
        if rx_height < 1 or rx_height > 20:
            self.logger.warning(f"RX height {rx_height} m outside valid range "
                              f"(1-20 m)")

        # Validar ambiente
        valid_env = ['urban', 'suburban', 'rural']
        if environment.lower() not in valid_env:
            self.logger.warning(f"Unknown environment '{environment}'. "
                              f"Using 'Urban'")

        # Validar terreno
        valid_terrain = ['smooth', 'mixed', 'irregular']
        if terrain_type.lower() not in valid_terrain:
            self.logger.warning(f"Unknown terrain type '{terrain_type}'. "
                              f"Using 'mixed'")


    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna informacion del modelo

        Returns:
            Diccionario con metadatos
        """
        return {
            'name': self.name,
            'type': self.model_type,
            'frequency_range': '30-4000 MHz',
            'distance_range': '1-1000 km',
            'tx_height_range': '10-3000 m AGL',
            'rx_height_range': '1-20 m AGL',
            'environments': ['Urban', 'Suburban', 'Rural'],
            'terrain_types': ['Smooth', 'Mixed', 'Irregular'],
            'has_terrain_awareness': True,
            'has_los_nlos': True,
            'cpu_gpu_support': True,
            'reference': 'ITU-R P.1546-6 (August 2019)',
        }
