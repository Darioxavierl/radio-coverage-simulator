"""
Validación de la implementación ITU-R P.1546 contra los ejemplos de referencia oficiales.

Compara la intensidad de campo E[dBμV/m] calculada por la función de interpolación
de tablas del modelo Python contra los valores de referencia publicados por la UIT
en la carpeta itu/Validation examples for Recommendation ITU-R P.1546-6 - Ver 6.2/

METODOLOGÍA (dos niveles de validación):

  NIVEL 1 — Interpolación de tablas pura (paso 11 del algoritmo ITU):
    Se compara get_reference_field_intensity() contra el valor intermedio del
    paso 11 (E_step11) extraído de los archivos *_log.csv de la ITU.
    El paso 11 incluye interpolación en distancia, altura y frecuencia (pasos 3–10)
    pero NO incluye correcciones de h2, TCA ni clutter.
    Tolerancia: ±1 dB.

  NIVEL 2 — E final (con todas las correcciones):
    Se compara contra combined_results.csv (E después de h2, TCA, clutter).
    Solo informativo — valida el modelo completo, fuera del alcance de este script.

PARÁMETROS USADOS EN NIVEL 1:
    - h1 según log ITU (puede diferir de h1_m del perfil por reglas §3)
    - d_km del perfil
    - f_mhz del perfil
    - Comparación directa sin corrección de tiempo (step 11 ya incluye tiempo)

SRC NO MODIFICADO: ningún método de src/ se altera.

Uso:
    cd G:\\My Drive\\Universidad\\Tesis
    validaciones\\.venv\\Scripts\\python.exe validaciones\\validate_itu_p1546_standard.py

Salidas en validaciones/resultados/ITU_standard/
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path setup: hacer visible src/ sin modificar el venv
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.models.traditional.itu_r_p1546_tables import (
    get_reference_field_intensity,
    get_percentile_correction,
    AVAILABLE_PERCENTILES,
)
from src.core.models.traditional.itu_r_p1546 import ITUR_P1546Model

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ITU_PROFILES_DIR = (
    ROOT / "itu"
    / "Validation examples for Recommendation ITU-R P.1546-6 - Ver 6.2"
    / "validation_profiles"
)
ITU_COMBINED_RESULTS = (
    ROOT / "itu"
    / "Validation examples for Recommendation ITU-R P.1546-6 - Ver 6.2"
    / "validation_results"
    / "combined_results.csv"
)
OUTPUT_DIR = ROOT / "validaciones" / "resultados" / "ITU_standard"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Perfiles a validar: solo terreno plano (h_eff = h1 exacta)
# Excluidos: rburg_*, b2iseac_*, misc_*, srg_*, land_flat_adjsea_*
# (tienen TCA real o clutter de Annex5 que difieren del modelo Python)
# Perfiles de validacion: solo escenarios con condiciones comparables al modelo Python.
# Excluidos deliberadamente:
#   flat_annex5_para1.1_100km — requiere R1/R2 explicitos del Annex5 §1.1 (no derivables)
#   flat_p1km                 — d=0.1km, fuera del rango de aplicabilidad P.1546 (d>=1km)
#   land_neg_h1_urban_10km    — h1 negativa, caso degenerado sin correspondencia real
FLAT_PROFILES = [
    "flat_1km.csv",
    "flat_10km.csv",
    "flat_100km.csv",
    "flat_100km_denseurban.csv",
    "flat_100km_suburban.csv",
    "flat_100km_urban.csv",
]

PASS_THRESHOLD_DB = 1.0   # ±1 dB — tolerancia aceptable para tablas digitalizadas (Nivel 1)
PASS_THRESHOLD_L2 = 2.0   # ±2 dB — tolerancia Nivel 2 (diferencias clutter son esperadas)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parser del formato de perfil ITU
# ---------------------------------------------------------------------------

def parse_itu_profile(filepath: Path) -> dict:
    """
    Lee un perfil de validación ITU-R P.1546 en formato CSV propietario.

    Returns:
        dict con claves:
            name               : str
            path_length_km     : float
            tx_clutter_height_m: float | None  — R1 (cover height en punto TX, d=0)
            rx_clutter_height_m: float | None  — R2 (cover height en punto RX, d=max)
            measurements       : list of dicts {freq_mhz, h1_m, h2_m, time_pct,
                                                location_pct, E_ref_dbuvm, PL_ref_db}
    """
    result = {
        "name": filepath.stem,
        "path_length_km": None,
        "tx_clutter_height_m": None,
        "rx_clutter_height_m": None,
        "measurements": [],
    }

    with filepath.open(encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    in_measurements = False
    in_profile      = False
    terrain_rows    = []  # filas de datos del bloque {Begin of Profile}

    for line in lines:
        stripped = line.strip()

        # Path length
        if stripped.startswith("Tot. Path Length(km):"):
            parts = stripped.split(",")
            if len(parts) >= 2 and parts[1].strip():
                try:
                    result["path_length_km"] = float(parts[1].strip())
                except ValueError:
                    pass

        # Bloque de perfil de terreno
        if stripped == "{Begin of Profile}":
            in_profile = True
            continue
        if stripped == "{End of Profile}":
            in_profile = False
            continue
        if in_profile:
            if stripped.startswith("Number of Points") or stripped.startswith("Distance") or stripped.startswith("["):
                continue
            parts_t = [p.strip() for p in stripped.split(",")]
            # Formato: dist_km, elevation, coverage_code, ground_cover_height, radiomet
            if len(parts_t) >= 4:
                try:
                    terrain_rows.append({
                        "d_km":   float(parts_t[0]),
                        "cover":  float(parts_t[3]) if parts_t[3] else 0.0,
                    })
                except ValueError:
                    pass
            continue

        # Entrada a sección de mediciones
        if stripped == "{Begin of Measurements}":
            in_measurements = True
            continue
        if stripped == "{End of Measurements}":
            in_measurements = False
            continue

        # Saltar encabezados y unidades
        if in_measurements and stripped.startswith("["):
            continue
        if in_measurements and stripped.startswith("Frequency"):
            continue

        # Fila de datos de medición
        if in_measurements and stripped and not stripped.startswith("#"):
            parts = [p.strip() for p in stripped.split(",")]
            if len(parts) < 17:
                continue  # fila incompleta

            def safe_float(idx, default=None):
                try:
                    v = parts[idx].strip()
                    return float(v) if v else default
                except (ValueError, IndexError):
                    return default

            freq_mhz  = safe_float(0)
            h1_m      = safe_float(1)
            h2_m      = safe_float(3)
            time_pct  = safe_float(14, 50.0)
            E_ref     = safe_float(16)
            PL_ref    = safe_float(17)

            if freq_mhz is None or h1_m is None or E_ref is None:
                continue

            result["measurements"].append({
                "freq_mhz":     freq_mhz,
                "h1_m":         h1_m,
                "h2_m":         h2_m if h2_m is not None else 1.5,
                "time_pct":     time_pct,
                "location_pct": 50.0,
                "E_ref_dbuvm":  E_ref,
                "PL_ref_db":    PL_ref,
            })

    # R1 = cover height en el primer punto del terreno (TX)
    # R2 = cover height en el último punto del terreno (RX)
    if terrain_rows:
        result["tx_clutter_height_m"] = terrain_rows[0]["cover"]
        result["rx_clutter_height_m"] = terrain_rows[-1]["cover"]

    return result


def load_combined_results(filepath: Path) -> pd.DataFrame:
    """Lee combined_results.csv de la ITU (la fuente de verdad)."""
    df = pd.read_csv(
        filepath,
        comment="%",
        header=None,
        names=["folder", "filename", "dataset", "reference", "predicted", "deviation"],
        skipinitialspace=True,
    )
    df["filename"] = df["filename"].str.strip()
    return df


def parse_itu_log(log_path: Path) -> dict:
    """
    Lee el archivo de log ITU-R P.1546-6 y extrae valores clave.

    Returns dict con:
        h1_log      : float — altura efectiva h1 usada en cálculo (§3)
        E_step11    : float — campo E del paso 11 (tabla pura, antes de h2/TCA/clutter)
        time_pct    : float — percentil de tiempo usado
        E_final     : float — campo E final (incluye todas las correcciones)
        PL_final    : float — pérdida de transmisión final [dB]
    """
    result = {
        "h1_log": None, "E_step11": None,
        "time_pct": None, "E_final": None, "PL_final": None
    }
    if not log_path.exists():
        return result

    with log_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            parts = [p.strip() for p in stripped.split(",")]
            if len(parts) < 4:
                continue

            key = parts[0]
            try:
                val = float(parts[3]) if parts[3] else None
            except ValueError:
                val = None

            if "Tx antenna height h1 (m)" in key:
                result["h1_log"] = val
            elif "Field strength (dBuV/m)" in key and parts[2] == "11":
                result["E_step11"] = val
            elif "Percentage time t" in key:
                result["time_pct"] = val
            elif "Resulting field strength for Ptx = 1kW" in key:
                result["E_final"] = val
            elif "Resulting basic transmission loss" in key:
                result["PL_final"] = val

    return result





def nearest_available_percentile(pct: float) -> int:
    """Discretiza un percentil continuo al más cercano en la tabla ITU."""
    return min(AVAILABLE_PERCENTILES, key=lambda p: abs(p - pct))


def get_environment_from_profile(profile_name: str) -> str:
    """
    Infiere el entorno de propagación desde el nombre del perfil ITU.

    Returns: 'Dense Urban' | 'Urban' | 'Suburban' | 'Rural'
    """
    name_lower = profile_name.lower()
    if 'denseurban' in name_lower or 'dense_urban' in name_lower:
        return 'Dense Urban'
    if 'suburban' in name_lower:   # debe ir ANTES de 'urban' (suburban contiene 'urban')
        return 'Suburban'
    if 'urban' in name_lower:
        return 'Urban'
    return 'Rural'


def compute_full_model_pl(d_km: float,
                          h1_m: float,
                          h2_m: float,
                          freq_mhz: float,
                          time_pct: float,
                          environment: str,
                          clutter_model: str = 'p2108',
                          tx_clutter_height_m: float = None,
                          rx_clutter_height_m: float = None) -> float:
    """
    Calcula el path loss completo usando ITUR_P1546Model con terreno plano.

    Terreno plano: terrain_profiles=None (TCA=0), terrain_heights=0 m.
    Incluye: tabla ITU + h2 correction §9 + clutter (p2108 o itu_annex5) + percentil.

    Args:
        d_km:               Distancia TX→RX [km]
        h1_m:               Altura efectiva TX h_eff [m] (obtenida del log ITU)
        h2_m:               Altura receptora AGL [m]
        freq_mhz:           Frecuencia [MHz]
        time_pct:           Percentil de tiempo [%]
        environment:        'Urban' | 'Suburban' | 'Rural' | 'Dense Urban'
        clutter_model:      'p2108' (P.2108-1) | 'itu_annex5' (P.1546 §10)
        tx_clutter_height_m: R1 explícito [m] leído del perfil (solo para itu_annex5);
                             None = derivar del entorno        rx_clutter_height_m: R2 explícito [m] leído del perfil para §9 h2;
                             None = derivar del entorno
    Returns:
        Path loss [dB]
    """
    model = ITUR_P1546Model()

    d_eff = max(d_km, 1.0)
    distances_m = np.array([d_eff * 1000.0])
    terrain_heights = np.array([0.0])

    pl_arr = model.calculate_path_loss(
        distances=distances_m,
        frequency=freq_mhz,
        tx_height=h1_m,
        terrain_heights=terrain_heights,
        tx_elevation=0.0,
        terrain_profiles=None,
        environment=environment,
        mobile_height=max(h2_m, 1.0),
        time_percentage=int(round(time_pct)),
        location_percentage=50,
        profile_distances=None,
        clutter_model=clutter_model,
        tx_clutter_height_m=tx_clutter_height_m,
        rx_clutter_height_m=rx_clutter_height_m,
    )
    return float(pl_arr[0])


# ---------------------------------------------------------------------------
# Función principal de validación
# ---------------------------------------------------------------------------

def run_validation() -> pd.DataFrame:
    """
    Ejecuta la validación completa y retorna DataFrame con resultados.

    NIVEL 1: compara get_reference_field_intensity() contra E_step11 de logs ITU.
    NIVEL 2: informa E_final (con correcciones) solo como referencia.
    """
    ITU_LOGS_DIR = (
        ROOT / "itu"
        / "Validation examples for Recommendation ITU-R P.1546-6 - Ver 6.2"
        / "validation_results"
    )

    rows = []

    for profile_name in FLAT_PROFILES:
        profile_path = ITU_PROFILES_DIR / profile_name
        if not profile_path.exists():
            log.warning(f"Perfil no encontrado, omitido: {profile_name}")
            continue

        profile = parse_itu_profile(profile_path)
        d_km = profile["path_length_km"]

        if d_km is None:
            log.warning(f"{profile_name}: no se pudo leer path_length_km, omitido")
            continue

        if not profile["measurements"]:
            log.warning(f"{profile_name}: sin mediciones, omitido")
            continue

        for dataset_idx, meas in enumerate(profile["measurements"]):
            freq_mhz  = meas["freq_mhz"]
            h1_m      = meas["h1_m"]
            time_pct  = meas["time_pct"]
            E_ref_final = meas["E_ref_dbuvm"]  # E final del perfil

            # ─── Leer log ITU para obtener valores del paso 11 ───
            profile_stem = Path(profile_name).stem
            log_fname = f"{profile_stem}_{dataset_idx + 1}_log.csv"
            log_path = ITU_LOGS_DIR / log_fname
            itu_log = parse_itu_log(log_path)

            # h1 según el cálculo ITU (puede diferir de h1 en perfil por §3)
            h1_for_lookup = itu_log["h1_log"] if itu_log["h1_log"] is not None else h1_m

            # h2 del receptor (columna 3 del perfil; default 1.5 m si no está)
            h2_m = meas["h2_m"]

            # Valor de referencia del paso 11 (interpolación de tabla pura)
            E_ref_step11 = itu_log["E_step11"]

            # PL final del log ITU (incluye h2 §9, TCA, clutter §10, slope-path)
            PL_final_log = itu_log["PL_final"]

            # E final del log (para compatibilidad con columnas anteriores)
            E_final_log = itu_log["E_final"] if itu_log["E_final"] is not None else E_ref_final

            # ─── Calcular E con nuestro modelo (NIVEL 1: tabla pura) ───
            # Clip de distancia: sub-1km se redondea a 1km (igual que ITU)
            d_eff = max(d_km, 1.0)

            E_model_arr = get_reference_field_intensity(
                frequency=freq_mhz,
                distance_km=np.array([d_eff]),
                h_eff_m=np.array([h1_for_lookup]),
                xp=np,
            )
            E_model = float(E_model_arr[0])

            # ─── Comparación NIVEL 1: tabla pura vs step 11 ───
            if E_ref_step11 is not None:
                error_step11 = E_model - E_ref_step11
                passes_step11 = abs(error_step11) <= PASS_THRESHOLD_DB
            else:
                error_step11 = float("nan")
                passes_step11 = False

            # ─── Comparación NIVEL 2: modelo completo vs PL_final ITU ───
            # Dos pasadas: P.2108-1 y ITU Annex 5 §10
            # TCA = 0 en ambos (terreno plano, sin DEM)
            env_for_model = get_environment_from_profile(profile_name)
            if PL_final_log is not None:
                # L2a: P.2108-1 (default)
                try:
                    pl_model_full = compute_full_model_pl(
                        d_km=d_km,
                        h1_m=h1_for_lookup,
                        h2_m=h2_m,
                        freq_mhz=freq_mhz,
                        time_pct=time_pct,
                        environment=env_for_model,
                        clutter_model='p2108',
                    )
                    error_L2 = pl_model_full - PL_final_log
                    passes_L2 = abs(error_L2) <= PASS_THRESHOLD_L2
                except Exception as exc:
                    log.warning(f"Nivel 2 P.2108 error para {profile_name}#{dataset_idx+1}: {exc}")
                    pl_model_full = float("nan")
                    error_L2 = float("nan")
                    passes_L2 = False

                # L2b: ITU Annex 5 §10 — usar R1/R2 del perfil si están disponibles
                try:
                    pl_model_annex5 = compute_full_model_pl(
                        d_km=d_km,
                        h1_m=h1_for_lookup,
                        h2_m=h2_m,
                        freq_mhz=freq_mhz,
                        time_pct=time_pct,
                        environment=env_for_model,
                        clutter_model='itu_annex5',
                        tx_clutter_height_m=profile.get('tx_clutter_height_m'),
                        rx_clutter_height_m=profile.get('rx_clutter_height_m'),
                    )
                    error_L2a = pl_model_annex5 - PL_final_log
                    passes_L2a = abs(error_L2a) <= PASS_THRESHOLD_L2
                except Exception as exc:
                    log.warning(f"Nivel 2 Annex5 error para {profile_name}#{dataset_idx+1}: {exc}")
                    pl_model_annex5 = float("nan")
                    error_L2a = float("nan")
                    passes_L2a = False
            else:
                pl_model_full = pl_model_annex5 = float("nan")
                error_L2 = error_L2a = float("nan")
                passes_L2 = passes_L2a = False

            rows.append({
                "profile":           profile_name,
                "dataset":           dataset_idx + 1,
                "freq_mhz":          freq_mhz,
                "d_km":              d_km,
                "h1_m_profile":      h1_m,
                "h1_m_log":          itu_log["h1_log"],
                "h1_used":           h1_for_lookup,
                "h2_m":              h2_m,
                "env_model":         env_for_model,
                "time_pct":          time_pct,
                # Nivel 1
                "E_ref_step11":      E_ref_step11,
                "E_model_dbuvm":     E_model,
                "error_step11_db":   error_step11,
                "pass_step11":       passes_step11,
                # Nivel 2 — P.2108-1
                "PL_ITU_final":      PL_final_log,
                "PL_model_full":     pl_model_full,
                "error_L2_db":       error_L2,
                "pass_L2":           passes_L2,
                # Nivel 2 — Annex 5 §10
                "PL_model_annex5":   pl_model_annex5,
                "error_L2a_db":      error_L2a,
                "pass_L2a":          passes_L2a,
                # Auxiliares
                "E_ref_final":       E_final_log,
                "log_found":         log_path.exists(),
            })

            # Consola: Nivel 1 + Nivel 2 (ambos modelos de clutter)
            if E_ref_step11 is not None:
                status1 = "PASS" if passes_step11 else "FAIL"
                l2_str  = f"L2p2108:{error_L2:+.2f}" if not np.isnan(error_L2) else "L2p2108:N/A"
                l2a_str = f"L2annex5:{error_L2a:+.2f}" if not np.isnan(error_L2a) else "L2annex5:N/A"
                log.info(
                    f"[{status1}] {profile_name} #{dataset_idx+1} "
                    f"f={freq_mhz:.0f}MHz d={d_km:.0f}km h1={h1_for_lookup:.1f}m h2={h2_m:.1f}m "
                    f"err={error_step11:+.3f}dB  {l2_str}dB  {l2a_str}dB"
                )
            else:
                log.warning(
                    f"[N/A] {profile_name} #{dataset_idx+1} — log no encontrado: {log_fname}"
                )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

def save_results_csv(df: pd.DataFrame):
    out = OUTPUT_DIR / "validation_results.csv"
    df.to_csv(out, index=False, float_format="%.6f")
    log.info(f"Resultados guardados: {out}")


def save_summary(df: pd.DataFrame):
    # ── Nivel 1: tabla pura vs E_step11 ──────────────────────────────────────
    df_s11 = df[df["E_ref_step11"].notna()].copy()
    n_total = len(df_s11)
    n_pass  = int(df_s11["pass_step11"].sum())

    rmse    = float(np.sqrt(np.mean(df_s11["error_step11_db"] ** 2))) if n_total > 0 else float("nan")
    mae     = float(np.mean(np.abs(df_s11["error_step11_db"]))) if n_total > 0 else float("nan")
    bias    = float(np.mean(df_s11["error_step11_db"])) if n_total > 0 else float("nan")
    max_err = float(df_s11["error_step11_db"].abs().max()) if n_total > 0 else float("nan")
    min_err = float(df_s11["error_step11_db"].min()) if n_total > 0 else float("nan")
    max_err_signed = float(df_s11["error_step11_db"].max()) if n_total > 0 else float("nan")

    # ── Nivel 2: modelo completo vs PL_final ITU ────────────────────────────
    df_L2 = df[df["PL_ITU_final"].notna() & df["PL_model_full"].notna()].copy()
    n_L2      = len(df_L2)
    n_pass_L2 = int(df_L2["pass_L2"].sum()) if n_L2 > 0 else 0
    rmse_L2   = float(np.sqrt(np.mean(df_L2["error_L2_db"] ** 2))) if n_L2 > 0 else float("nan")
    mae_L2    = float(np.mean(np.abs(df_L2["error_L2_db"]))) if n_L2 > 0 else float("nan")
    bias_L2   = float(np.mean(df_L2["error_L2_db"])) if n_L2 > 0 else float("nan")
    max_L2    = float(df_L2["error_L2_db"].abs().max()) if n_L2 > 0 else float("nan")

    # ── Nivel 2a: modelo Annex5 vs PL_final ITU ──────────────────────────────
    df_L2a = df[df["PL_ITU_final"].notna() & df["PL_model_annex5"].notna()].copy()
    n_L2a      = len(df_L2a)
    n_pass_L2a = int(df_L2a["pass_L2a"].sum()) if n_L2a > 0 else 0
    rmse_L2a   = float(np.sqrt(np.mean(df_L2a["error_L2a_db"] ** 2))) if n_L2a > 0 else float("nan")
    mae_L2a    = float(np.mean(np.abs(df_L2a["error_L2a_db"]))) if n_L2a > 0 else float("nan")
    bias_L2a   = float(np.mean(df_L2a["error_L2a_db"])) if n_L2a > 0 else float("nan")
    max_L2a    = float(df_L2a["error_L2a_db"].abs().max()) if n_L2a > 0 else float("nan")

    lines = [
        "=" * 90,
        "Validacion ITU-R P.1546-6",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 90,
        "",
        "METODOLOGIA:",
        "  Nivel 1: get_reference_field_intensity() vs E_step11 del log ITU",
        "           Paso 11 = interpolacion de tabla SIN correcciones h2/TCA/clutter",
        "           Valida la exactitud de las tablas y la interpolacion.",
        "",
        "  Nivel 2 (P.2108-1): ITUR_P1546Model [clutter_model='p2108'] vs PL_final ITU",
        "           h2 §9 [impl.] + TCA=0 (plano) + P.2108-1 §3 (modelo moderno RX)",
        "           Diferencia deliberada: la ITU usa clutter §10 (TX).",
        "",
        "  Nivel 2a (Annex5):  ITUR_P1546Model [clutter_model='itu_annex5'] vs PL_final ITU",
        "           h2 §9 [impl.] + TCA=0 (plano) + §10 Annex5 (clutter TX P.1546)",
        "           Comparacion directa con el modelo de referencia ITU.",
        "",
        f"NIVEL 1 — Interpolacion de tablas (paso 11):",
        f"  Casos con log ITU disponible: {n_total}/{len(df)}",
        f"  PASS (|err|<={PASS_THRESHOLD_DB:.0f}dB): {n_pass}/{n_total} ({100*n_pass/n_total:.1f}%)" if n_total > 0 else "  Sin casos",
        f"  RMSE:      {rmse:.4f} dB",
        f"  MAE:       {mae:.4f} dB",
        f"  Bias:      {bias:+.4f} dB",
        f"  Max |err|: {max_err:.4f} dB  (rango: {min_err:+.3f} a {max_err_signed:+.3f} dB)",
        "",
        f"NIVEL 2 — Modelo completo P.2108-1 vs PL_final ITU:",
        f"  Casos evaluados: {n_L2}/{len(df)}",
        f"  PASS (|err|<={PASS_THRESHOLD_L2:.0f}dB): {n_pass_L2}/{n_L2} ({100*n_pass_L2/n_L2:.1f}%)" if n_L2 > 0 else "  Sin casos",
        f"  RMSE:      {rmse_L2:.4f} dB",
        f"  MAE:       {mae_L2:.4f} dB",
        f"  Bias:      {bias_L2:+.4f} dB",
        f"  Max |err|: {max_L2:.4f} dB",
        "",
        f"NIVEL 2a — Modelo completo Annex5 §10 vs PL_final ITU:",
        f"  Casos evaluados: {n_L2a}/{len(df)}",
        f"  PASS (|err|<={PASS_THRESHOLD_L2:.0f}dB): {n_pass_L2a}/{n_L2a} ({100*n_pass_L2a/n_L2a:.1f}%)" if n_L2a > 0 else "  Sin casos",
        f"  RMSE:      {rmse_L2a:.4f} dB",
        f"  MAE:       {mae_L2a:.4f} dB",
        f"  Bias:      {bias_L2a:+.4f} dB",
        f"  Max |err|: {max_L2a:.4f} dB",
        f"  NOTA: Los errores residuales en Nivel 2a se deben a:",
        "        - §16 slope-path no implementado (<0.1 dB en perfiles planos)",
        "        - Curvatura terrestre no corregida (relevante solo en d>50km)",
        "        - §10 TX clutter derivado automaticamente del entorno (sin R1 explicito)",
        "",
        "FUENTE DE TABLAS:",
        "  Extraido de exceltables{1,9,17} de P1546FieldStrMixed.m",
        "  (MATLAB oficial ITU-R P.1546-6 v6.2)",
        "",
        f"{'Profile':<40} {'#':>2} {'f':>5} {'d':>6} {'h1':>5} {'h2':>4} "
        f"{'dS11':>7} {'S11':>4} | {'PL_ITU':>7} {'PL_p2108':>8} {'dL2':>7} {'L2':>4} "
        f"{'PL_ann5':>8} {'dL2a':>7} {'L2a':>4}",
        "-" * 125,
    ]
    for _, row in df.iterrows():
        err_s11 = row.get("error_step11_db", float("nan"))
        stat1 = ("PASS" if row["pass_step11"] else "FAIL") if not np.isnan(err_s11) else "N/A "
        err_s11_str = f"{err_s11:+7.3f}" if not np.isnan(err_s11) else "    N/A"

        pl_itu  = row.get("PL_ITU_final", float("nan"))
        pl_mod  = row.get("PL_model_full", float("nan"))
        err_L2  = row.get("error_L2_db", float("nan"))
        pl_ann5 = row.get("PL_model_annex5", float("nan"))
        err_L2a = row.get("error_L2a_db", float("nan"))

        pl_itu_str  = f"{pl_itu:7.2f}"   if not np.isnan(pl_itu)  else "    N/A"
        pl_mod_str  = f"{pl_mod:8.2f}"   if not np.isnan(pl_mod)  else "     N/A"
        err_L2_str  = f"{err_L2:+7.2f}"  if not np.isnan(err_L2)  else "    N/A"
        stat2       = ("PASS" if row.get("pass_L2",  False) else "FAIL") if not np.isnan(err_L2)  else "N/A "
        pl_ann5_str = f"{pl_ann5:8.2f}"  if not np.isnan(pl_ann5) else "     N/A"
        err_L2a_str = f"{err_L2a:+7.2f}" if not np.isnan(err_L2a) else "    N/A"
        stat2a      = ("PASS" if row.get("pass_L2a", False) else "FAIL") if not np.isnan(err_L2a) else "N/A "

        lines.append(
            f"{row['profile']:<40} {int(row['dataset']):>2} "
            f"{row['freq_mhz']:>5.0f} {row['d_km']:>6.1f} {row['h1_used']:>5.1f} {row.get('h2_m', 0):>4.1f} "
            f"{err_s11_str} {stat1:>4} | {pl_itu_str} {pl_mod_str} {err_L2_str} {stat2:>4} "
            f"{pl_ann5_str} {err_L2a_str} {stat2a:>4}"
        )

    out = OUTPUT_DIR / "validation_summary.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"Resumen guardado: {out}")

    # Imprimir en consola (hasta la tabla) — escapar chars no-ASCII para cp1252
    console_text = "\n".join(lines[:55])
    print("\n" + console_text.encode("ascii", errors="replace").decode("ascii"))

# ---------------------------------------------------------------------------
# Helpers de graficación (internos)
# ---------------------------------------------------------------------------

def _plot_scatter(df_plot: pd.DataFrame,
                  x_col: str, y_col: str, error_col: str, pass_col: str,
                  x_label: str, y_label: str,
                  tolerance: float, out_path: Path) -> None:
    """Scatter genérico referencia vs modelo, coloreado por frecuencia. Sin título."""
    if df_plot.empty:
        return

    fig, ax = plt.subplots(figsize=(7, 7))
    cmap = plt.get_cmap("tab10")
    freqs = sorted(df_plot["freq_mhz"].unique())

    for i, f in enumerate(freqs):
        mask = df_plot["freq_mhz"] == f
        ax.scatter(
            df_plot.loc[mask, x_col],
            df_plot.loc[mask, y_col],
            label=f"{f:.0f} MHz",
            color=cmap(i % 10),
            s=70, zorder=3,
        )

    all_vals = pd.concat([df_plot[x_col], df_plot[y_col]]).dropna()
    lim_min = all_vals.min() - 5
    lim_max = all_vals.max() + 5

    ax.plot([lim_min, lim_max], [lim_min, lim_max],
            "k--", lw=1.2, label="y = x (ideal)", zorder=2)
    ax.fill_between(
        [lim_min, lim_max],
        [lim_min - tolerance, lim_max - tolerance],
        [lim_min + tolerance, lim_max + tolerance],
        alpha=0.12, color="green",
        label=f"±{tolerance:.0f} dB",
    )

    # Estadísticas en leyenda extra
    errors = df_plot[error_col].dropna()
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    n_pass = int(df_plot[pass_col].sum())
    n = len(df_plot)
    ax.plot([], [], " ", label=f"RMSE = {rmse:.3f} dB")
    ax.plot([], [], " ", label=f"PASS = {n_pass}/{n} ({100*n_pass/n:.0f}%)")

    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(lim_min, lim_max)
    ax.set_ylim(lim_min, lim_max)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    log.info(f"Scatter guardado: {out_path}")


def _plot_boxplot(df_plot: pd.DataFrame,
                  error_col: str,
                  tolerance: float,
                  x_label: str, y_label: str,
                  out_path: Path) -> None:
    """Boxplot de error agrupado por frecuencia, con media marcada y anotada. Sin título."""
    df_valid = df_plot[df_plot[error_col].notna()].copy()
    if df_valid.empty:
        return

    freqs_sorted = sorted(df_valid["freq_mhz"].unique())
    data_groups = [df_valid.loc[df_valid["freq_mhz"] == f, error_col].values
                   for f in freqs_sorted]
    labels = [f"{f:.0f} MHz" for f in freqs_sorted]

    fig, ax = plt.subplots(figsize=(8, 5))
    cmap = plt.get_cmap("tab10")

    bp = ax.boxplot(
        data_groups,
        tick_labels=labels,
        patch_artist=True,
        notch=False,
        showmeans=True,
        meanprops=dict(marker="D", markerfacecolor="red",
                       markeredgecolor="darkred", markersize=8, zorder=5),
    )

    for j, (patch, group_data) in enumerate(zip(bp["boxes"], data_groups)):
        patch.set_facecolor(cmap(j % 10))
        patch.set_alpha(0.6)

        # Anotar valor de la media
        if len(group_data) > 0:
            mean_val = float(np.mean(group_data))
            # Posición: ligeramente desplazada a la derecha del diamante
            ax.annotate(
                f"{mean_val:+.2f}",
                xy=(j + 1, mean_val),
                xytext=(8, 4),
                textcoords="offset points",
                fontsize=8,
                color="darkred",
                fontweight="bold",
                zorder=6,
            )

    ax.axhline(0, color="black", lw=1.2, ls="--", label="Error = 0 dB")
    ax.axhline(+tolerance, color="green", lw=1, ls=":",
               label=f"±{tolerance:.0f} dB (tolerancia)")
    ax.axhline(-tolerance, color="green", lw=1, ls=":")

    # Entrada de leyenda para la media
    ax.plot([], [], marker="D", color="red", ls="none",
            markersize=8, label="Media (valor anotado)")

    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    log.info(f"Boxplot guardado: {out_path}")


def _plot_error_distance(df_plot: pd.DataFrame,
                         error_col: str,
                         tolerance: float,
                         y_label: str,
                         out_path: Path) -> None:
    """Error vs distancia (escala log), coloreado por frecuencia. Sin título."""
    df_valid = df_plot[df_plot[error_col].notna()].copy()
    if df_valid.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    cmap = plt.get_cmap("tab10")
    freqs = sorted(df_valid["freq_mhz"].unique())

    for i, f in enumerate(freqs):
        mask = df_valid["freq_mhz"] == f
        ax.scatter(
            df_valid.loc[mask, "d_km"],
            df_valid.loc[mask, error_col],
            label=f"{f:.0f} MHz",
            color=cmap(i % 10),
            s=70, zorder=3,
        )

    ax.axhline(0, color="black", lw=1.2, ls="--", label="Error = 0 dB")
    ax.axhline(+tolerance, color="green", lw=1, ls=":",
               label=f"±{tolerance:.0f} dB (tolerancia)")
    ax.axhline(-tolerance, color="green", lw=1, ls=":")
    ax.set_xscale("log")
    ax.set_xlabel("Distancia TX–RX [km] (escala log)", fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    log.info(f"Scatter distancia guardado: {out_path}")


# ---------------------------------------------------------------------------
# Funciones de graficación públicas — Nivel 1 y Nivel 2
# ---------------------------------------------------------------------------

def plot_scatter_L1(df: pd.DataFrame) -> None:
    """Nivel 1: E_step11 (ITU) vs E_model [dBμV/m]."""
    df_plot = df[df["E_ref_step11"].notna()].copy()
    _plot_scatter(
        df_plot,
        x_col="E_ref_step11", y_col="E_model_dbuvm",
        error_col="error_step11_db", pass_col="pass_step11",
        x_label="E referencia ITU-R — paso 11 [dBμV/m]",
        y_label="E modelo Python [dBμV/m]",
        tolerance=PASS_THRESHOLD_DB,
        out_path=OUTPUT_DIR / "scatter_L1_E_ref_vs_model.png",
    )


def plot_scatter_L2(df: pd.DataFrame) -> None:
    """Nivel 2: PL_final (ITU) vs PL_model_full [dB]."""
    df_plot = df[df["PL_ITU_final"].notna() & df["PL_model_full"].notna()].copy()
    _plot_scatter(
        df_plot,
        x_col="PL_ITU_final", y_col="PL_model_full",
        error_col="error_L2_db", pass_col="pass_L2",
        x_label="PL referencia ITU-R — final [dB]",
        y_label="PL modelo Python — completo [dB]",
        tolerance=PASS_THRESHOLD_L2,
        out_path=OUTPUT_DIR / "scatter_L2_PL_ref_vs_model.png",
    )


def plot_error_by_frequency_L1(df: pd.DataFrame) -> None:
    """Nivel 1: boxplot error_step11 por frecuencia."""
    df_plot = df[df["E_ref_step11"].notna()].copy()
    _plot_boxplot(
        df_plot,
        error_col="error_step11_db",
        tolerance=PASS_THRESHOLD_DB,
        x_label="Frecuencia",
        y_label="Error Nivel 1 [dB]  (E_modelo − E_paso11 ITU)",
        out_path=OUTPUT_DIR / "error_by_frequency_L1.png",
    )


def plot_error_by_frequency_L2(df: pd.DataFrame) -> None:
    """Nivel 2: boxplot error_L2 por frecuencia."""
    df_plot = df[df["error_L2_db"].notna()].copy()
    _plot_boxplot(
        df_plot,
        error_col="error_L2_db",
        tolerance=PASS_THRESHOLD_L2,
        x_label="Frecuencia",
        y_label="Error Nivel 2 [dB]  (PL_modelo − PL_final ITU)",
        out_path=OUTPUT_DIR / "error_by_frequency_L2.png",
    )


def plot_error_by_distance_L1(df: pd.DataFrame) -> None:
    """Nivel 1: error_step11 vs distancia."""
    df_plot = df[df["E_ref_step11"].notna()].copy()
    _plot_error_distance(
        df_plot,
        error_col="error_step11_db",
        tolerance=PASS_THRESHOLD_DB,
        y_label="Error Nivel 1 [dB]  (E_modelo − E_paso11 ITU)",
        out_path=OUTPUT_DIR / "error_by_distance_L1.png",
    )


def plot_error_by_distance_L2(df: pd.DataFrame) -> None:
    """Nivel 2: error_L2 vs distancia."""
    df_plot = df[df["error_L2_db"].notna()].copy()
    _plot_error_distance(
        df_plot,
        error_col="error_L2_db",
        tolerance=PASS_THRESHOLD_L2,
        y_label="Error Nivel 2 [dB]  (PL_modelo − PL_final ITU)",
        out_path=OUTPUT_DIR / "error_by_distance_L2.png",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("Iniciando validación ITU-R P.1546-6 contra estándar oficial")
    log.info(f"Perfiles ITU: {ITU_PROFILES_DIR}")
    log.info(f"Salida:       {OUTPUT_DIR}")
    log.info("=" * 60)

    df = run_validation()

    if df.empty:
        log.error("No se procesó ningún caso. Verificar rutas en ITU_PROFILES_DIR.")
        sys.exit(1)

    save_results_csv(df)
    save_summary(df)
    # Nivel 1
    plot_scatter_L1(df)
    plot_error_by_frequency_L1(df)
    plot_error_by_distance_L1(df)
    # Nivel 2 — P.2108-1
    plot_scatter_L2(df)
    plot_error_by_frequency_L2(df)
    plot_error_by_distance_L2(df)
    # Nivel 2a — Annex 5 §10
    _plot_scatter(
        df[df["PL_ITU_final"].notna() & df["PL_model_annex5"].notna()].copy(),
        x_col="PL_ITU_final", y_col="PL_model_annex5",
        error_col="error_L2a_db", pass_col="pass_L2a",
        x_label="PL referencia ITU-R — final [dB]",
        y_label="PL modelo Python — Annex5 §10 [dB]",
        tolerance=PASS_THRESHOLD_L2,
        out_path=OUTPUT_DIR / "scatter_L2a_PL_ref_vs_annex5.png",
    )
    _plot_boxplot(
        df[df["error_L2a_db"].notna()].copy(),
        error_col="error_L2a_db",
        tolerance=PASS_THRESHOLD_L2,
        x_label="Frecuencia",
        y_label="Error Nivel 2a [dB]  (PL_Annex5 - PL_final ITU)",
        out_path=OUTPUT_DIR / "error_by_frequency_L2a.png",
    )
    _plot_error_distance(
        df[df["error_L2a_db"].notna()].copy(),
        error_col="error_L2a_db",
        tolerance=PASS_THRESHOLD_L2,
        y_label="Error Nivel 2a [dB]  (PL_Annex5 - PL_final ITU)",
        out_path=OUTPUT_DIR / "error_by_distance_L2a.png",
    )

    n_pass = int(df["pass_step11"].sum())
    n_total = len(df[df["E_ref_step11"].notna()])
    rmse = float(np.sqrt(np.mean(df[df["E_ref_step11"].notna()]["error_step11_db"] ** 2))) if n_total > 0 else float("nan")

    log.info("=" * 60)
    log.info(f"Validación completa: {n_pass}/{n_total} PASS, RMSE={rmse:.4f} dB")
    log.info(f"Resultados en: {OUTPUT_DIR}")
    log.info("=" * 60)
