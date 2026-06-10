"""
ITU-R P.1546-6 Reference Tables

Tablas digitalizadas de intensidad de campo E[dBμV/m] para:
- Frecuencias: 100 MHz, 600 MHz, 2000 MHz
- Distancias: 1, 2, 5, 10, 15, 20, 30, 50, 100, 200, 300, 500, 1000 km
- Alturas efectivas TX: 10, 20, 37.5, 75, 150, 300, 600, 1200 m AGL

Fuente: ITU-R Recommendation P.1546-6 (August 2019)
"Method for point-to-area predictions for terrestrial services in the frequency range 30 MHz to 4 000 MHz"
Ref: https://www.itu.int/rec/R-REC-P.1546-6-201908-I/en

Conversión realizada desde gráficos de referencia del estándar ITU.
Valores en dBμV/m para 50% de tiempo, 50% de ubicación.

Autores: David Montano, Dario Portilla
Universidad de Cuenca, 2025
"""

import numpy as np
from typing import Dict, Tuple
import logging

log = logging.getLogger(__name__)


# =============================================================================
# TABLAS DE REFERENCIA ITU-R P.1546-6
# =============================================================================
# Estructura: tables[freq_mhz][distance_km][h_eff_m] = E_field[dBμV/m]

# Distancias de referencia en km
DISTANCES_KM = np.array([1, 2, 5, 10, 15, 20, 30, 50, 100, 200, 300, 500, 1000])

# Alturas efectivas de referencia en metros AGL
HEIGHTS_M = np.array([10, 20, 37.5, 75, 150, 300, 600, 1200])


# Tabla 100 MHz (VHF Bajo)
# Valores E[dBμV/m] para 50% tiempo, 50% ubicación
# FUENTE: exceltables{1} de P1546FieldStrMixed.m (MATLAB oficial ITU-R P.1546-6 v6.2)
TABLE_100_MHZ = {
    1: {10: 89.9759, 20: 92.1812, 37.5: 94.6355, 75: 97.3845, 150: 100.3181, 300: 103.1205, 600: 105.2426, 1200: 106.3566},
    2: {10: 80.2751, 20: 83.0908, 37.5: 86.0014, 75: 89.2076, 150: 92.6742, 300: 96.1197, 600: 98.8577, 1200: 100.2846},
    5: {10: 65.6994, 20: 69.9206, 37.5: 73.9248, 75: 78.0214, 150: 82.3137, 300: 86.6601, 600: 90.3203, 1200: 92.2498},
    10: {10: 52.6796, 20: 57.8377, 37.5: 62.9896, 75: 68.2548, 150: 73.6382, 300: 79.0175, 600: 83.6656, 1200: 86.1477},
    15: {10: 44.4715, 20: 49.8704, 37.5: 55.4448, 75: 61.3035, 150: 67.4365, 300: 73.7034, 600: 79.3576, 1200: 82.5061},
    20: {10: 38.5237, 20: 43.9806, 37.5: 49.6950, 75: 55.7889, 150: 62.2910, 300: 69.1285, 600: 75.7029, 1200: 79.7742},
    30: {10: 30.1811, 20: 35.5753, 37.5: 41.2901, 75: 47.4593, 150: 54.1611, 300: 61.4361, 600: 69.0821, 1200: 75.2470},
    50: {10: 20.4457, 20: 25.2917, 37.5: 30.5082, 75: 36.2563, 150: 42.6853, 300: 49.9783, 600: 58.3013, 1200: 67.1390},
    100: {10: 10.3885, 20: 12.7552, 37.5: 15.5241, 75: 18.9127, 150: 23.2014, 300: 28.8839, 600: 36.8766, 1200: 48.5226},
    200: {10: 0.0578, 20: 0.5723, 37.5: 1.4312, 75: 2.7879, 150: 4.7814, 300: 7.6290, 600: 11.8338, 1200: 18.9592},
    300: {10: -10.0034, 20: -9.7747, 37.5: -9.1991, 75: -8.1543, 150: -6.5478, 300: -4.2726, 600: -1.1303, 1200: 3.4955},
    500: {10: -27.5473, 20: -27.4133, 37.5: -26.9281, 75: -25.9832, 150: -24.5028, 300: -22.4197, 600: -19.6550, 1200: -16.0441},
    1000: {10: -68.8933, 20: -68.7783, 37.5: -68.3123, 75: -67.3889, 150: -65.9357, 300: -63.8945, 600: -61.2136, 1200: -57.8373},
}

# Tabla 600 MHz (UHF)
# Valores E[dBμV/m] para 50% tiempo, 50% ubicación
# FUENTE: exceltables{9} de P1546FieldStrMixed.m (MATLAB oficial ITU-R P.1546-6 v6.2)
TABLE_600_MHZ = {
    1: {10: 92.6814, 20: 94.8678, 37.5: 97.0716, 75: 99.6994, 150: 102.3451, 300: 104.5908, 600: 106.0069, 1200: 106.6288},
    2: {10: 81.1075, 20: 84.2913, 37.5: 87.0917, 75: 90.3564, 150: 93.8030, 300: 97.0711, 600: 99.4170, 1200: 100.4837},
    5: {10: 63.0644, 20: 68.5558, 37.5: 72.9417, 75: 77.4212, 150: 81.9203, 300: 86.4566, 600: 90.2897, 1200: 92.2753},
    10: {10: 48.3932, 20: 54.7013, 37.5: 60.3695, 75: 66.3867, 150: 72.1670, 300: 77.8385, 600: 82.9613, 1200: 85.9648},
    15: {10: 39.8831, 20: 46.2375, 37.5: 52.1924, 75: 58.8881, 150: 65.5898, 300: 72.2089, 600: 78.3267, 1200: 82.1870},
    20: {10: 34.0384, 20: 40.2540, 37.5: 46.1852, 75: 53.0662, 150: 60.2499, 300: 67.6074, 600: 74.6552, 1200: 79.4083},
    30: {10: 26.3388, 20: 31.9987, 37.5: 37.5205, 75: 44.1618, 150: 51.5007, 300: 59.6175, 600: 68.2366, 1200: 75.1080},
    50: {10: 17.9101, 20: 21.9864, 37.5: 26.1506, 75: 31.4639, 150: 37.8342, 300: 45.7341, 600: 55.7392, 1200: 67.2133},
    100: {10: 7.6124, 20: 9.0947, 37.5: 10.8740, 75: 13.4888, 150: 17.0613, 300: 22.1381, 600: 29.9285, 1200: 42.9635},
    200: {10: -6.7408, 20: -6.3048, 37.5: -5.5340, 75: -4.1661, 150: -2.1408, 300: 0.7361, 600: 4.9375, 1200: 12.0271},
    300: {10: -18.8095, 20: -18.5409, 37.5: -17.9339, 75: -16.7744, 150: -15.0228, 300: -12.5771, 600: -9.2274, 1200: -4.2749},
    500: {10: -38.4639, 20: -38.2640, 37.5: -37.7242, 75: -36.6507, 150: -35.0135, 300: -32.7518, 600: -29.7800, 1200: -25.8715},
    1000: {10: -80.3400, 20: -80.1611, 37.5: -79.6421, 75: -78.5950, 150: -76.9932, 300: -74.7888, 600: -71.9365, 1200: -68.3711},
}

# Tabla 2000 MHz (SHF - 2G/3G/4G)
# Valores E[dBμV/m] para 50% tiempo, 50% ubicación
# FUENTE: exceltables{17} de P1546FieldStrMixed.m (MATLAB oficial ITU-R P.1546-6 v6.2)
TABLE_2000_MHZ = {
    1: {10: 94.2335, 20: 96.5092, 37.5: 98.6617, 75: 101.1481, 150: 103.5091, 300: 105.3192, 600: 106.3279, 1200: 106.7319},
    2: {10: 82.4269, 20: 85.9102, 37.5: 88.7578, 75: 91.9714, 150: 95.2440, 300: 98.1155, 600: 99.9163, 1200: 100.6325},
    5: {10: 63.3850, 20: 69.4120, 37.5: 74.2531, 75: 79.0061, 150: 83.5363, 300: 87.8513, 600: 91.0987, 1200: 92.5131},
    10: {10: 47.2358, 20: 54.1160, 37.5: 60.4064, 75: 67.1694, 150: 73.5071, 300: 79.3308, 600: 84.0345, 1200: 86.3036},
    15: {10: 37.6531, 20: 44.6185, 37.5: 51.1909, 75: 58.6772, 150: 66.2105, 300: 73.4287, 600: 79.4970, 1200: 82.6078},
    20: {10: 30.9451, 20: 37.8324, 37.5: 44.4072, 75: 52.0723, 150: 60.1211, 300: 68.3030, 600: 75.7285, 1200: 79.8926},
    30: {10: 21.9215, 20: 28.3545, 37.5: 34.5993, 75: 42.0806, 150: 50.3064, 300: 59.3175, 600: 68.7063, 1200: 75.6036},
    50: {10: 12.1083, 20: 16.7663, 37.5: 21.5263, 75: 27.6336, 150: 34.9988, 300: 44.0853, 600: 55.2520, 1200: 67.3877},
    100: {10: 2.3266, 20: 3.6623, 37.5: 5.3391, 75: 7.9327, 150: 11.6691, 300: 17.2619, 600: 26.2303, 1200: 41.3695},
    200: {10: -9.8312, 20: -9.5150, 37.5: -8.8612, 75: -7.6140, 150: -5.6918, 300: -2.9009, 600: 1.2164, 1200: 8.2075},
    300: {10: -21.7708, 20: -21.5668, 37.5: -21.0261, 75: -19.9329, 150: -18.2323, 300: -15.8265, 600: -12.5416, 1200: -7.8339},
    500: {10: -41.7978, 20: -41.6287, 37.5: -41.1235, 75: -40.0787, 150: -38.4485, 300: -36.1669, 600: -33.1595, 1200: -29.2785},
    1000: {10: -84.4853, 20: -84.3239, 37.5: -83.8264, 75: -82.7923, 150: -81.1778, 300: -78.9238, 600: -75.9787, 1200: -72.2882},
}

# Mapa de frecuencias → tablas
TABLES = {
    100: TABLE_100_MHZ,
    600: TABLE_600_MHZ,
    2000: TABLE_2000_MHZ,
}

# Frecuencias de interpolación
REFERENCE_FREQUENCIES = np.array([100, 600, 2000])


# =============================================================================
# PRE-COMPUTED MATRIX CONSTANTS (nivel módulo, calculadas una vez al importar)
# Evitan reconstruir las tablas en cada llamada — clave para vectorización
# =============================================================================

# Claves de distancia y altura como arrays NumPy
_DIST_KEYS = np.array([1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0, 200.0, 300.0, 500.0, 1000.0])  # (13,)
_HEIGHT_KEYS = np.array([10.0, 20.0, 37.5, 75.0, 150.0, 300.0, 600.0, 1200.0])  # (8,)
_LOG_DIST_KEYS = np.log(_DIST_KEYS)    # (13,) — precomputado para interpolación log
_LOG_HEIGHT_KEYS = np.log(_HEIGHT_KEYS)  # (8,)


def _build_table_matrix(table_dict: dict) -> np.ndarray:
    """Construye matriz (13, 8) desde dict anidado {distancia: {altura: valor}}"""
    return np.array([[table_dict[d][h] for h in _HEIGHT_KEYS] for d in _DIST_KEYS])


# Matrices de referencia ITU-R P.1546-6 pre-compiladas
E_TABLE_100 = _build_table_matrix(TABLE_100_MHZ)   # (13, 8) [dBμV/m]
E_TABLE_600 = _build_table_matrix(TABLE_600_MHZ)   # (13, 8) [dBμV/m]
E_TABLE_2000 = _build_table_matrix(TABLE_2000_MHZ)  # (13, 8) [dBμV/m]


def _interp_vectorized(E_matrix: np.ndarray,
                       dist_clipped: np.ndarray,
                       h_clipped: np.ndarray) -> np.ndarray:
    """
    Interpolación bilineal log-lineal vectorizada desde matriz ITU (13, 8).
    Reemplaza el bucle for i in range(n) — sin iteraciones Python.

    Ejes:
      - Distancia: log-lineal entre _DIST_KEYS (1–1000 km)
      - Altura: log-lineal entre _HEIGHT_KEYS (10–1200 m), extrapolación h < 10m

    Args:
        E_matrix: shape (13, 8) — valores E[dBμV/m]
        dist_clipped: shape (n,) — distancias en km, ya clipeadas [1, 1000]
        h_clipped: shape (n,) — alturas en m, ya clipeadas [-3000, 1200]

    Returns:
        Array (n,) de valores E interpolados [dBμV/m]
    """
    # --- Eje Distancia: log-lineal ---
    log_d = np.log(np.maximum(dist_clipped, 1e-9))
    idx_d = np.searchsorted(_LOG_DIST_KEYS, log_d, side='right') - 1
    idx_d = np.clip(idx_d, 0, len(_DIST_KEYS) - 2)  # [0, 11]
    log_d_lo = _LOG_DIST_KEYS[idx_d]
    log_d_hi = _LOG_DIST_KEYS[idx_d + 1]
    span_d = log_d_hi - log_d_lo  # siempre > 0 (claves distintas)
    alpha_d = np.clip((log_d - log_d_lo) / span_d, 0.0, 1.0)  # (n,)

    # --- Eje Altura: log-lineal con extrapolación para h < 10m ---
    below_min = h_clipped < _HEIGHT_KEYS[0]   # h < 10 m
    above_max = h_clipped >= _HEIGHT_KEYS[-1]  # h >= 1200 m

    # log de altura seguro (evitar log(0) o log(negativo))
    log_h = np.log(np.maximum(np.abs(h_clipped), 0.1))

    # Índice estándar (para h en rango)
    idx_h = np.searchsorted(_LOG_HEIGHT_KEYS, log_h, side='right') - 1
    idx_h = np.clip(idx_h, 0, len(_HEIGHT_KEYS) - 2)  # [0, 6]
    log_h_lo = _LOG_HEIGHT_KEYS[idx_h]
    log_h_hi = _LOG_HEIGHT_KEYS[idx_h + 1]
    span_h = log_h_hi - log_h_lo
    alpha_h_std = np.where(span_h > 0, (log_h - log_h_lo) / span_h, 0.0)

    # Extrapolación h < 10m: pendiente del segmento log(10m)→log(20m)
    # alpha_h_extrap negativo → E menor → PL mayor (físicamente correcto para TX en valle)
    span_extrap = _LOG_HEIGHT_KEYS[1] - _LOG_HEIGHT_KEYS[0]  # log(20) - log(10)
    alpha_h_extrap = np.clip(
        (log_h - _LOG_HEIGHT_KEYS[0]) / span_extrap,
        -3.0, 0.0  # máximo ~20 dB de extrapolación adicional
    )

    # Combinar casos
    idx_h_final = np.where(below_min, 0, idx_h)
    idx_h_final = np.where(above_max, len(_HEIGHT_KEYS) - 2, idx_h_final).astype(int)
    idx_h1_final = np.minimum(idx_h_final + 1, len(_HEIGHT_KEYS) - 1)

    alpha_h = np.where(below_min, alpha_h_extrap, alpha_h_std)
    alpha_h = np.where(above_max, 1.0, alpha_h)
    alpha_h = np.clip(alpha_h, -3.0, 1.0)  # permitir negativo para extrapolación

    # --- Interpolación bilineal (indexing avanzado, sin for loop) ---
    idx_d1 = np.minimum(idx_d + 1, len(_DIST_KEYS) - 1).astype(int)
    idx_d = idx_d.astype(int)

    E11 = E_matrix[idx_d,  idx_h_final]   # d_lo, h_lo
    E12 = E_matrix[idx_d,  idx_h1_final]  # d_lo, h_hi
    E21 = E_matrix[idx_d1, idx_h_final]   # d_hi, h_lo
    E22 = E_matrix[idx_d1, idx_h1_final]  # d_hi, h_hi

    E_at_d_lo = E11 * (1.0 - alpha_h) + E12 * alpha_h
    E_at_d_hi = E21 * (1.0 - alpha_h) + E22 * alpha_h
    return E_at_d_lo * (1.0 - alpha_d) + E_at_d_hi * alpha_d  # (n,)


def get_reference_field_intensity(frequency: float, distance_km: float, 
                                 h_eff_m: float, xp=None) -> np.ndarray:
    """
    Interpola intensidad de campo E[dBμV/m] a partir de tablas ITU-R P.1546-6
    
    Implementa interpolación 3D vectorizada:
    - Frecuencia: entre 100, 600, 2000 MHz (lineal en log(f))
    - Distancia: entre valores tabulados (lineal en log(d))
    - Altura efectiva: entre valores tabulados (lineal en h_eff)
    
    Args:
        frequency: Frecuencia en MHz (100-2000)
        distance_km: Distancia en km (1-1000) - array o escalar
        h_eff_m: Altura efectiva en m (10-1200) - array o escalar
        xp: Módulo numérico (np o cp). Default: np
        
    Returns:
        Array E[dBμV/m] con mismo shape que distancia/altura
    """
    import numpy as np
    if xp is None:
        xp = np
    
    # Convertir a arrays
    distance_km = xp.atleast_1d(distance_km).astype(float)
    h_eff_m = xp.atleast_1d(h_eff_m).astype(float)
    
    # Broadcast a mismo shape
    if distance_km.shape != h_eff_m.shape:
        distance_km, h_eff_m = xp.broadcast_arrays(distance_km, h_eff_m)
    
    original_shape = distance_km.shape
    n = distance_km.size
    
    # Aplanar y convertir a NumPy (tablas ITU siempre en NumPy)
    distance_flat = distance_km.flatten()
    h_eff_flat = h_eff_m.flatten()
    if hasattr(distance_flat, 'get'):  # CuPy → NumPy
        distance_flat = distance_flat.get()
        h_eff_flat = h_eff_flat.get()
    else:
        distance_flat = np.asarray(distance_flat)
        h_eff_flat = np.asarray(h_eff_flat)

    # Clampear a rango válido (NumPy)
    dist_clipped = np.clip(distance_flat, 1.0, 1000.0)
    # P.1546-6 §4.3: h_eff puede ser negativa (TX en valle) — no clipear a 10m mínimo
    h_clipped = np.clip(h_eff_flat, -3000.0, 1200.0)

    # === INTERPOLACIÓN VECTORIZADA — sin bucle for === #
    # Fórmula de interpolación log-log en frecuencia (§3 de P.1546-6 ecuación 14):
    #   E(f) = E(f_lo) + [E(f_hi) - E(f_lo)] * log10(f/f_lo) / log10(f_hi/f_lo)
    # Para f > 2000 MHz se extrapola con f_lo=600, f_hi=2000 (fw > 1)
    if frequency <= 100:
        E_result = _interp_vectorized(E_TABLE_100, dist_clipped, h_clipped)
    elif frequency <= 600:
        fw = (np.log(frequency) - np.log(100.0)) / (np.log(600.0) - np.log(100.0))
        E_result = (_interp_vectorized(E_TABLE_100, dist_clipped, h_clipped) * (1.0 - fw) +
                    _interp_vectorized(E_TABLE_600, dist_clipped, h_clipped) * fw)
    else:
        # f entre 600 y 2000 MHz (interpolación), o f > 2000 MHz (extrapolación)
        fw = (np.log(frequency) - np.log(600.0)) / (np.log(2000.0) - np.log(600.0))
        E_result = (_interp_vectorized(E_TABLE_600, dist_clipped, h_clipped) * (1.0 - fw) +
                    _interp_vectorized(E_TABLE_2000, dist_clipped, h_clipped) * fw)

    # Remodelar a forma original
    return E_result.reshape(original_shape)


# =============================================================================
# TABLA PERCENTILES - VARIACIÓN TEMPORAL
# =============================================================================
# ITU P.1546 Annex 5: Correcciones para diferentes percentiles de tiempo
# Valores en dB relativos a 50% de tiempo (referencia = 0 dB)
#
# Significado:
# - 1%   = Peor caso (campo más fuerte) → Receptor recibe +3.09 dB más que median
# - 10%  = Peor que median → +1.28 dB
# - 50%  = Mediana (referencia) → 0.0 dB
# - 90%  = Mejor que median → -1.28 dB
# - 99%  = Mejor caso (campo más débil) → -3.09 dB menos

PERCENTILE_TIME_VARIATION = {
    1: 3.09,      # 1% de tiempo (peor propagación)
    10: 1.28,     # 10% de tiempo
    50: 0.0,      # 50% de tiempo (referencia)
    90: -1.28,    # 90% de tiempo
    99: -3.09,    # 99% de tiempo (mejor propagación)
}

# =============================================================================
# TABLA PERCENTILES - VARIACIÓN ESPACIAL (UBICACIÓN)
# =============================================================================
# ITU P.1546 Annex 5: Correcciones para diferentes percentiles de ubicación
# Los valores son similares a variación temporal (aproximación ITU)

PERCENTILE_LOCATION_VARIATION = {
    1: 3.09,      # 1% de ubicaciones (peor)
    10: 1.28,     # 10% de ubicaciones
    50: 0.0,      # 50% de ubicaciones (referencia)
    90: -1.28,    # 90% de ubicaciones
    99: -3.09,    # 99% de ubicaciones (mejor)
}

# Percentiles disponibles (para validación)
AVAILABLE_PERCENTILES = [1, 10, 50, 90, 99]


def get_percentile_correction(percentile: int, variability_type: str = 'time') -> float:
    """
    Obtiene corrección de percentil de ITU Annex 5
    
    Implementa tablas de variabilidad:
    - Temporal: Describe variabilidad en tiempo (fading, shadowing)
    - Espacial: Describe variabilidad en ubicación (terrain variations)
    
    FÍSICA:
    Propagación variable en el tiempo y espacio. Percentiles describen
    probabilidad acumulada de encontrar ese campo en condiciones normales:
    
    - P1 (1%): Condiciones anómalas/raras (~mejor propagación)
    - P50 (50%): Mediana (referencia)
    - P99 (99%): Condiciones anómalas/raras (~peor propagación)
    
    Args:
        percentile: 1, 10, 50, 90, 99
        variability_type: 'time' (temporal) o 'location' (espacial)
    
    Returns:
        Corrección en dB (puede ser positiva o negativa)
    """
    if variability_type.lower() == 'time':
        table = PERCENTILE_TIME_VARIATION
    elif variability_type.lower() == 'location':
        table = PERCENTILE_LOCATION_VARIATION
    else:
        raise ValueError(f"Tipo de variabilidad desconocido: {variability_type}")
    
    if percentile not in table:
        raise ValueError(f"Percentil no disponible: {percentile}. "
                        f"Disponibles: {list(table.keys())}")
    
    return float(table[percentile])


def apply_percentile_correction(E_50_dbuv: float, 
                               percentile: int,
                               variability_type: str = 'time') -> float:
    """
    Aplica corrección de percentil a campo de referencia (50%)
    
    Fórmula: E_p = E_50 + correction_p
    
    Args:
        E_50_dbuv: Campo en dBμV/m para 50% (referencia)
        percentile: 1, 10, 50, 90, 99
        variability_type: 'time' o 'location'
    
    Returns:
        Campo en dBμV/m para percentil especificado
    """
    correction = get_percentile_correction(percentile, variability_type)
    
    return E_50_dbuv + correction


def get_model_tables_info() -> Dict:
    """
    Retorna información sobre tablas disponibles
    
    Returns:
        Diccionario con metadatos
    """
    return {
        'reference_frequencies_mhz': [100, 600, 2000],
        'distances_km': DISTANCES_KM.tolist(),
        'heights_m_agl': HEIGHTS_M.tolist(),
        'temporal_percentage': 50,  # 50% de tiempo
        'location_percentage': 50,  # 50% de ubicación
        'reference': 'ITU-R P.1546-6 (August 2019)',
        'available_percentiles': AVAILABLE_PERCENTILES,
        'percentile_time_variation_db': dict(PERCENTILE_TIME_VARIATION),
        'percentile_location_variation_db': dict(PERCENTILE_LOCATION_VARIATION),
    }


if __name__ == "__main__":
    # Test básico
    print("ITU-R P.1546-6 Tables Module")
    print(f"Reference frequencies: {REFERENCE_FREQUENCIES} MHz")
    print(f"Distance range: {DISTANCES_KM[0]} - {DISTANCES_KM[-1]} km")
    print(f"Height range: {HEIGHTS_M[0]} - {HEIGHTS_M[-1]} m AGL")
    
    # Ejemplo: E a 800 MHz, 10 km, altura efectiva 75 m
    E = get_reference_field_intensity(800, 10.0, 75.0)
    print(f"\nEjemplo: f=800MHz, d=10km, h_eff=75m → E={E[0]:.1f} dBμV/m")
