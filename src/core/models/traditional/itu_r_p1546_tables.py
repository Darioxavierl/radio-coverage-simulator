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
TABLE_100_MHZ = {
    1: {10: 124.3, 20: 131.1, 37.5: 137.5, 75: 143.4, 150: 148.1, 300: 151.0, 600: 152.5, 1200: 152.8},
    2: {10: 118.2, 20: 125.0, 37.5: 131.4, 75: 137.3, 150: 142.0, 300: 144.9, 600: 146.4, 1200: 146.7},
    5: {10: 110.5, 20: 117.3, 37.5: 123.7, 75: 129.6, 150: 134.3, 300: 137.2, 600: 138.7, 1200: 139.0},
    10: {10: 104.9, 20: 111.7, 37.5: 118.1, 75: 124.0, 150: 128.7, 300: 131.6, 600: 133.1, 1200: 133.4},
    15: {10: 101.2, 20: 108.0, 37.5: 114.4, 75: 120.3, 150: 125.0, 300: 127.9, 600: 129.4, 1200: 129.7},
    20: {10: 98.3, 20: 105.1, 37.5: 111.5, 75: 117.4, 150: 122.1, 300: 125.0, 600: 126.5, 1200: 126.8},
    30: {10: 93.0, 20: 99.8, 37.5: 106.2, 75: 112.1, 150: 116.8, 300: 119.7, 600: 121.2, 1200: 121.5},
    50: {10: 86.5, 20: 93.3, 37.5: 99.7, 75: 105.6, 150: 110.3, 300: 113.2, 600: 114.7, 1200: 115.0},
    100: {10: 77.5, 20: 84.3, 37.5: 90.7, 75: 96.6, 150: 101.3, 300: 104.2, 600: 105.7, 1200: 106.0},
    200: {10: 67.3, 20: 74.1, 37.5: 80.5, 75: 86.4, 150: 91.1, 300: 94.0, 600: 95.5, 1200: 95.8},
    300: {10: 61.4, 20: 68.2, 37.5: 74.6, 75: 80.5, 150: 85.2, 300: 88.1, 600: 89.6, 1200: 89.9},
    500: {10: 52.2, 20: 59.0, 37.5: 65.4, 75: 71.3, 150: 76.0, 300: 78.9, 600: 80.4, 1200: 80.7},
    1000: {10: 41.2, 20: 48.0, 37.5: 54.4, 75: 60.3, 150: 65.0, 300: 67.9, 600: 69.4, 1200: 69.7},
}

# Tabla 600 MHz (UHF)
# Valores E[dBμV/m] para 50% tiempo, 50% ubicación
TABLE_600_MHZ = {
    1: {10: 130.9, 20: 137.7, 37.5: 144.1, 75: 149.8, 150: 154.2, 300: 157.0, 600: 158.4, 1200: 158.7},
    2: {10: 124.8, 20: 131.6, 37.5: 138.0, 75: 143.7, 150: 148.1, 300: 150.9, 600: 152.3, 1200: 152.6},
    5: {10: 117.1, 20: 123.9, 37.5: 130.3, 75: 136.0, 150: 140.4, 300: 143.2, 600: 144.6, 1200: 144.9},
    10: {10: 111.5, 20: 118.3, 37.5: 124.7, 75: 130.4, 150: 134.8, 300: 137.6, 600: 139.0, 1200: 139.3},
    15: {10: 107.8, 20: 114.6, 37.5: 121.0, 75: 126.7, 150: 131.1, 300: 133.9, 600: 135.3, 1200: 135.6},
    20: {10: 104.9, 20: 111.7, 37.5: 118.1, 75: 123.8, 150: 128.2, 300: 131.0, 600: 132.4, 1200: 132.7},
    30: {10: 99.6, 20: 106.4, 37.5: 112.8, 75: 118.5, 150: 122.9, 300: 125.7, 600: 127.1, 1200: 127.4},
    50: {10: 93.1, 20: 99.9, 37.5: 106.3, 75: 112.0, 150: 116.4, 300: 119.2, 600: 120.6, 1200: 120.9},
    100: {10: 84.1, 20: 90.9, 37.5: 97.3, 75: 103.0, 150: 107.4, 300: 110.2, 600: 111.6, 1200: 111.9},
    200: {10: 73.9, 20: 80.7, 37.5: 87.1, 75: 92.8, 150: 97.2, 300: 100.0, 600: 101.4, 1200: 101.7},
    300: {10: 68.0, 20: 74.8, 37.5: 81.2, 75: 86.9, 150: 91.3, 300: 94.1, 600: 95.5, 1200: 95.8},
    500: {10: 58.8, 20: 65.6, 37.5: 72.0, 75: 77.7, 150: 82.1, 300: 84.9, 600: 86.3, 1200: 86.6},
    1000: {10: 47.8, 20: 54.6, 37.5: 61.0, 75: 66.7, 150: 71.1, 300: 73.9, 600: 75.3, 1200: 75.6},
}

# Tabla 2000 MHz (SHF - 2G/3G/4G)
# Valores E[dBμV/m] para 50% tiempo, 50% ubicación
TABLE_2000_MHZ = {
    1: {10: 140.5, 20: 147.3, 37.5: 153.7, 75: 159.4, 150: 163.8, 300: 166.6, 600: 168.0, 1200: 168.3},
    2: {10: 134.4, 20: 141.2, 37.5: 147.6, 75: 153.3, 150: 157.7, 300: 160.5, 600: 161.9, 1200: 162.2},
    5: {10: 126.7, 20: 133.5, 37.5: 139.9, 75: 145.6, 150: 150.0, 300: 152.8, 600: 154.2, 1200: 154.5},
    10: {10: 121.1, 20: 127.9, 37.5: 134.3, 75: 140.0, 150: 144.4, 300: 147.2, 600: 148.6, 1200: 148.9},
    15: {10: 117.4, 20: 124.2, 37.5: 130.6, 75: 136.3, 150: 140.7, 300: 143.5, 600: 144.9, 1200: 145.2},
    20: {10: 114.5, 20: 121.3, 37.5: 127.7, 75: 133.4, 150: 137.8, 300: 140.6, 600: 142.0, 1200: 142.3},
    30: {10: 109.2, 20: 116.0, 37.5: 122.4, 75: 128.1, 150: 132.5, 300: 135.3, 600: 136.7, 1200: 137.0},
    50: {10: 102.7, 20: 109.5, 37.5: 115.9, 75: 121.6, 150: 126.0, 300: 128.8, 600: 130.2, 1200: 130.5},
    100: {10: 93.7, 20: 100.5, 37.5: 106.9, 75: 112.6, 150: 117.0, 300: 119.8, 600: 121.2, 1200: 121.5},
    200: {10: 83.5, 20: 90.3, 37.5: 96.7, 75: 102.4, 150: 106.8, 300: 109.6, 600: 111.0, 1200: 111.3},
    300: {10: 77.6, 20: 84.4, 37.5: 90.8, 75: 96.5, 150: 100.9, 300: 103.7, 600: 105.1, 1200: 105.4},
    500: {10: 68.4, 20: 75.2, 37.5: 81.6, 75: 87.3, 150: 91.7, 300: 94.5, 600: 95.9, 1200: 96.2},
    1000: {10: 57.4, 20: 64.2, 37.5: 70.6, 75: 76.3, 150: 80.7, 300: 83.5, 600: 84.9, 1200: 85.2},
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
    if frequency <= 100:
        E_result = _interp_vectorized(E_TABLE_100, dist_clipped, h_clipped)
    elif frequency >= 2000:
        E_result = _interp_vectorized(E_TABLE_2000, dist_clipped, h_clipped)
    elif frequency <= 600:
        fw = (np.log(frequency) - np.log(100.0)) / (np.log(600.0) - np.log(100.0))
        E_result = (_interp_vectorized(E_TABLE_100, dist_clipped, h_clipped) * (1.0 - fw) +
                    _interp_vectorized(E_TABLE_600, dist_clipped, h_clipped) * fw)
    else:
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
