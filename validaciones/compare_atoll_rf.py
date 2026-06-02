import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import pearsonr

import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.OUTPUT_DIR.parent / 'comparison.log', encoding='utf-8')
    ]
)
log = logging.getLogger(__name__)


def parse_atoll_txt(file_path: Path) -> tuple[dict, pd.DataFrame]:
    log.info(f"🔄 Parseando archivo Atoll: {file_path}")
    metadata = {}
    data_rows = []

    # Patrón para líneas de datos: lon;lat;[cell_id];dbm
    line_pattern = re.compile(
        r"^\s*([+-]?\d+(?:\.\d+)?);([+-]?\d+(?:\.\d+)?);\[?(.*?)\]?;([+-]?\d+(?:\.\d+)?)\s*$"
    )

    try:
        with file_path.open("r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line:
                    continue

                if "\t" in line and not line_pattern.match(line):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        metadata[parts[0].strip()] = parts[1].strip()
                    continue

                match = line_pattern.match(line)
                if match:
                    lon, lat, cell_id, dbm = match.groups()
                    data_rows.append(
                        {
                            "lon": float(lon),
                            "lat": float(lat),
                            "cell_id": cell_id.strip(),
                            "atoll_dbm": float(dbm),
                        }
                    )
                elif line and not line.startswith("#"):
                    log.debug(f"Línea {line_num} no coincide con patrón: {line[:80]}")

        if not data_rows:
            raise ValueError(f"No se encontraron datos de cobertura en {file_path}")

        atoll_df = pd.DataFrame(data_rows)
        log.info(f"✅ Atoll parseado: {len(atoll_df)} puntos, {len(metadata)} metadatos")
        log.debug(f"Metadatos: {metadata}")
        log.info(f"Rango Atoll: {atoll_df['atoll_dbm'].min():.1f} a {atoll_df['atoll_dbm'].max():.1f} dBm")
        log.info(f"Área: lon [{atoll_df['lon'].min():.6f}, {atoll_df['lon'].max():.6f}] lat [{atoll_df['lat'].min():.6f}, {atoll_df['lat'].max():.6f}]")
        
        return metadata, atoll_df
    except Exception as e:
        log.error(f"❌ Error parseando Atoll: {e}")
        raise


def load_rf_csv(file_path: Path) -> pd.DataFrame:
    log.info(f"🔄 Cargando CSV RF: {file_path}")
    try:
        rf_df = pd.read_csv(file_path)
        log.info(f"CSV cargado: shape={rf_df.shape}")
        log.debug(f"Columnas: {list(rf_df.columns)}")

        required_cols = {"grid_lon", "grid_lat", "rsrp_dbm"}
        missing = required_cols - set(rf_df.columns)
        if missing:
            raise ValueError(f"Faltan columnas en CSV RF: {sorted(missing)}")

        rf_df = rf_df.rename(
            columns={"grid_lon": "lon", "grid_lat": "lat", "rsrp_dbm": "rf_dbm"}
        )
        keep_cols = ["lon", "lat", "rf_dbm"]
        if "antenna_id" in rf_df.columns:
            keep_cols.append("antenna_id")
        rf_df = rf_df[keep_cols].copy()
        
        n_before = len(rf_df)
        rf_df = rf_df.dropna(subset=["lon", "lat", "rf_dbm"])
        n_after = len(rf_df)
        
        if n_before > n_after:
            log.warning(f"Descartados {n_before - n_after} registros con NaN")
        
        log.info(f"✅ RF cargado: {len(rf_df)} puntos")
        log.info(f"Rango RF: {rf_df['rf_dbm'].min():.1f} a {rf_df['rf_dbm'].max():.1f} dBm")
        log.info(f"Área: lon [{rf_df['lon'].min():.6f}, {rf_df['lon'].max():.6f}] lat [{rf_df['lat'].min():.6f}, {rf_df['lat'].max():.6f}]")
        
        return rf_df
    except Exception as e:
        log.error(f"❌ Error cargando RF CSV: {e}")
        raise


def project_coordinates(df: pd.DataFrame, source_crs: str, target_crs: str) -> pd.DataFrame:
    log.info(f"🔄 Proyectando coordenadas: {source_crs} -> {target_crs}")
    try:
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        x, y = transformer.transform(df["lon"].to_numpy(), df["lat"].to_numpy())

        proj_df = df.copy()
        proj_df["x_m"] = x
        proj_df["y_m"] = y
        log.info(f"✅ Proyección completada: {len(proj_df)} puntos")
        log.debug(f"Rango X: [{x.min():.1f}, {x.max():.1f}] m")
        log.debug(f"Rango Y: [{y.min():.1f}, {y.max():.1f}] m")
        return proj_df
    except Exception as e:
        log.error(f"❌ Error proyectando: {e}")
        raise


def nearest_mapping(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_id_col: str,
    target_id_col: str,
    distance_col: str,
) -> pd.DataFrame:
    target_tree = cKDTree(target_df[["x_m", "y_m"]].to_numpy())
    distances, nearest_idx = target_tree.query(source_df[["x_m", "y_m"]].to_numpy(), k=1)

    mapped = pd.DataFrame(
        {
            source_id_col: source_df[source_id_col].to_numpy(),
            target_id_col: target_df.iloc[nearest_idx][target_id_col].to_numpy(),
            distance_col: distances,
        }
    )
    return mapped


def build_paired_dataframe(
    mapping_df: pd.DataFrame,
    atoll_df: pd.DataFrame,
    rf_df: pd.DataFrame,
    tolerance_m: float,
) -> pd.DataFrame:
    filtered = mapping_df[mapping_df["match_distance_m"] <= tolerance_m].copy()
    if filtered.empty:
        return filtered

    atoll_small = atoll_df[["atoll_idx", "lon", "lat", "x_m", "y_m", "atoll_dbm"]].copy()
    rf_keep_cols = ["rf_idx", "lon", "lat", "x_m", "y_m", "rf_dbm"]
    if "antenna_id" in rf_df.columns:
        rf_keep_cols.append("antenna_id")
    rf_small = rf_df[rf_keep_cols].copy()

    filtered = filtered.merge(atoll_small, on="atoll_idx", how="left")
    filtered = filtered.merge(
        rf_small,
        on="rf_idx",
        how="left",
        suffixes=("_atoll", "_rf"),
    )

    filtered = filtered.rename(
        columns={
            "lon_atoll": "lon",
            "lat_atoll": "lat",
            "lon_rf": "rf_lon",
            "lat_rf": "rf_lat",
            "x_m_atoll": "x_m",
            "y_m_atoll": "y_m",
            "x_m_rf": "rf_x_m",
            "y_m_rf": "rf_y_m",
        }
    )
    filtered["error_db"] = filtered["rf_dbm"] - filtered["atoll_dbm"]
    filtered["abs_error_db"] = filtered["error_db"].abs()

    return filtered


def apply_mutual_filter(
    forward_df: pd.DataFrame,
    reverse_df: pd.DataFrame,
) -> pd.DataFrame:
    reverse_map = dict(zip(reverse_df["rf_idx"], reverse_df["atoll_idx"]))
    return forward_df[
        forward_df.apply(
            lambda row: reverse_map.get(row["rf_idx"], None) == row["atoll_idx"],
            axis=1,
        )
    ].copy()


def match_points(
    atoll_df: pd.DataFrame,
    rf_df: pd.DataFrame,
    tolerance_m: float,
    use_mutual_match_filter: bool,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    log.info(f"🔄 Matcheando puntos (tolerancia={tolerance_m}m, mutual_filter={use_mutual_match_filter})")
    
    try:
        rf_tree = cKDTree(rf_df[["x_m", "y_m"]].to_numpy())
        log.debug(f"Árbol KD-Tree RF construido: {len(rf_df)} puntos")

        forward = nearest_mapping(
            source_df=atoll_df,
            target_df=rf_df,
            source_id_col="atoll_idx",
            target_id_col="rf_idx",
            distance_col="match_distance_m",
        )
        log.info(f"Forward mapping: {len(forward)} correspondencias encontradas")
        log.info(f"  Distancias: min={forward['match_distance_m'].min():.1f}m, max={forward['match_distance_m'].max():.1f}m, mean={forward['match_distance_m'].mean():.1f}m")

        reverse = nearest_mapping(
            source_df=rf_df,
            target_df=atoll_df,
            source_id_col="rf_idx",
            target_id_col="atoll_idx",
            distance_col="reverse_match_distance_m",
        )
        log.info(f"Reverse mapping: {len(reverse)} correspondencias encontradas")

        candidate_pairs = apply_mutual_filter(forward, reverse) if use_mutual_match_filter else forward
        log.info(f"Pares candidatos (después de filtro mutual): {len(candidate_pairs)}")

        matched_df = build_paired_dataframe(candidate_pairs, atoll_df, rf_df, tolerance_m)
        log.info(f"✅ Matched pairs después de tolerancia: {len(matched_df)}")

        if not matched_df.empty:
            log.info(f"Error: min={matched_df['error_db'].min():.2f}, max={matched_df['error_db'].max():.2f}, mean={matched_df['error_db'].mean():.2f} dB")

        match_quality = {
            "use_mutual_match_filter": bool(use_mutual_match_filter),
            "candidate_pairs": int(len(candidate_pairs)),
            "matched_pairs": int(len(matched_df)),
            "atoll_points_total": int(len(atoll_df)),
            "rf_points_total": int(len(rf_df)),
            "match_rate_vs_atoll": float(len(matched_df) / len(atoll_df)) if len(atoll_df) else 0.0,
        }

        return matched_df, match_quality, forward
    except Exception as e:
        log.error(f"❌ Error en matching: {e}", exc_info=True)
        raise


def compute_metrics(matched_df: pd.DataFrame) -> dict:
    log.info(f"🔄 Calculando métricas ({len(matched_df)} puntos)")
    
    if matched_df.empty:
        raise ValueError("No hay puntos emparejados para calcular métricas")

    error = matched_df["error_db"].to_numpy()
    atoll_vals = matched_df["atoll_dbm"].to_numpy()
    rf_vals = matched_df["rf_dbm"].to_numpy()

    rmse = float(np.sqrt(np.mean(np.square(error))))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    if len(matched_df) > 1:
        corr, corr_pvalue = pearsonr(atoll_vals, rf_vals)
        corr = float(corr)
        corr_pvalue = float(corr_pvalue)
    else:
        corr, corr_pvalue = float("nan"), float("nan")

    slope, intercept = np.polyfit(atoll_vals, rf_vals, 1) if len(matched_df) > 1 else (float("nan"), float("nan"))

    metrics = {
        "n_matched": int(len(matched_df)),
        "rmse_db": rmse,
        "mae_db": mae,
        "bias_db": bias,
        "pearson_r": corr,
        "pearson_pvalue": corr_pvalue,
        "regression_slope": float(slope),
        "regression_intercept": float(intercept),
        "error_p50_db": float(np.quantile(np.abs(error), 0.50)),
        "error_p90_db": float(np.quantile(np.abs(error), 0.90)),
        "error_p95_db": float(np.quantile(np.abs(error), 0.95)),
        "error_p99_db": float(np.quantile(np.abs(error), 0.99)),
        "match_distance_median": float(matched_df["match_distance_m"].median()),
        "match_distance_p90": float(matched_df["match_distance_m"].quantile(0.90)),
        "match_distance_p95": float(matched_df["match_distance_m"].quantile(0.95)),
        "match_distance_p99": float(matched_df["match_distance_m"].quantile(0.99)),
    }
    
    log.info(f"✅ Métricas calculadas:")
    log.info(f"  RMSE: {rmse:.2f} dB | Bias: {bias:.2f} dB | MAE: {mae:.2f} dB")
    log.info(f"  Pearson r: {corr:.4f} (p={corr_pvalue:.2e})")
    log.info(f"  Regresión: slope={slope:.4f}, intercept={intercept:.2f}")
    log.info(f"  Percentiles error: P50={metrics['error_p50_db']:.2f}, P90={metrics['error_p90_db']:.2f}, P95={metrics['error_p95_db']:.2f}, P99={metrics['error_p99_db']:.2f} dB")
    
    return metrics


def save_cdf_data(matched_df: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info(f"🔄 Calculando datos CDF...")
    abs_err_sorted = np.sort(matched_df["abs_error_db"].to_numpy())
    signed_err_sorted = np.sort(matched_df["error_db"].to_numpy())
    cdf_abs = np.arange(1, len(abs_err_sorted) + 1) / len(abs_err_sorted)
    cdf_signed = np.arange(1, len(signed_err_sorted) + 1) / len(signed_err_sorted)

    cdf_abs_df = pd.DataFrame({"abs_error_db": abs_err_sorted, "cdf": cdf_abs})
    cdf_signed_df = pd.DataFrame({"error_db": signed_err_sorted, "cdf": cdf_signed})

    cdf_abs_df.to_csv(output_dir / "cdf_abs_error.csv", index=False)
    cdf_signed_df.to_csv(output_dir / "cdf_signed_error.csv", index=False)
    log.info(f"✅ CDF guardados")
    return cdf_abs_df, cdf_signed_df


def compute_threshold_cdf(cdf_abs_df: pd.DataFrame, thresholds: Iterable[float]) -> dict:
    values = cdf_abs_df["abs_error_db"].to_numpy()
    cdf = cdf_abs_df["cdf"].to_numpy()
    out = {}
    for t in thresholds:
        idx = np.searchsorted(values, t, side="right") - 1
        out[str(t)] = float(cdf[idx]) if idx >= 0 else 0.0
    return out


def run_tolerance_sweep(
    forward_pairs: pd.DataFrame,
    atoll_df: pd.DataFrame,
    rf_df: pd.DataFrame,
    tolerance_values: Iterable[float],
) -> pd.DataFrame:
    log.info(f"🔄 Barrido de tolerancias: {list(tolerance_values)}")
    rows = []
    for tol in tolerance_values:
        matched = build_paired_dataframe(forward_pairs, atoll_df, rf_df, tol)
        if matched.empty:
            log.warning(f"  Tolerancia {tol}m: 0 puntos")
            rows.append(
                {
                    "tolerance_m": float(tol),
                    "n_matched": 0,
                    "rmse_db": np.nan,
                    "mae_db": np.nan,
                    "bias_db": np.nan,
                    "pearson_r": np.nan,
                }
            )
            continue

        metrics = compute_metrics(matched)
        log.info(f"  Tolerancia {tol}m: {metrics['n_matched']} puntos, RMSE={metrics['rmse_db']:.2f}dB, Bias={metrics['bias_db']:.2f}dB")
        rows.append(
            {
                "tolerance_m": float(tol),
                "n_matched": metrics["n_matched"],
                "rmse_db": metrics["rmse_db"],
                "mae_db": metrics["mae_db"],
                "bias_db": metrics["bias_db"],
                "pearson_r": metrics["pearson_r"],
            }
        )

    log.info(f"✅ Barrido completado")
    return pd.DataFrame(rows)


def assess_match_reliability(metrics: dict, sweep_df: pd.DataFrame, tolerance_m: float) -> dict:
    log.info(f"🔄 Evaluando confiabilidad del matching...")
    valid = sweep_df.dropna(subset=["bias_db", "rmse_db"])
    if valid.empty:
        log.warning(f"No hay datos válidos en barrido de tolerancias")
        return {
            "match_reliability": "insufficient_data",
            "reason": "No hay datos válidos en barrido de tolerancias",
        }

    bias_range = float(valid["bias_db"].max() - valid["bias_db"].min())
    rmse_range = float(valid["rmse_db"].max() - valid["rmse_db"].min())

    distance_ok = metrics["match_distance_p95"] <= tolerance_m * 0.9
    stable_bias = bias_range <= 1.0
    stable_rmse = rmse_range <= 1.0

    if distance_ok and stable_bias and stable_rmse:
        label = "high"
    elif stable_bias and stable_rmse:
        label = "medium"
    else:
        label = "low"

    log.info(f"  Bias range: {bias_range:.2f} dB (estable: {stable_bias})")
    log.info(f"  RMSE range: {rmse_range:.2f} dB (estable: {stable_rmse})")
    log.info(f"  Distancia OK: {distance_ok} (p95={metrics['match_distance_p95']:.1f}m vs {tolerance_m*0.9:.1f}m)")
    log.info(f"  Confiabilidad: {label}")

    return {
        "match_reliability": label,
        "bias_range_db": bias_range,
        "rmse_range_db": rmse_range,
        "distance_quality_ok": bool(distance_ok),
        "bias_stability_ok": bool(stable_bias),
        "rmse_stability_ok": bool(stable_rmse),
    }


def generate_plots(
    matched_df: pd.DataFrame,
    cdf_abs_df: pd.DataFrame,
    cdf_thresholds: dict,
    metrics: dict,
    output_dir: Path,
    error_cmap_limit_db: float,
    sweep_df: pd.DataFrame,
) -> None:
    log.info(f"🔄 Generando gráficos...")
    sns.set_theme(style="whitegrid", context="talk", font_scale=1.1)
    
    # Extraer métricas clave
    bias_db = metrics["bias_db"]
    mae_db = metrics["mae_db"]
    rmse_db = metrics["rmse_db"]
    n_points = metrics["n_matched"]
    pearson_r = metrics["pearson_r"]
    slope = metrics["regression_slope"]
    intercept = metrics["regression_intercept"]
    match_dist_p50 = metrics["match_distance_median"]
    match_dist_p95 = metrics["match_distance_p95"]

    # --- Gráfico 1: Histograma error ---
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(matched_df["error_db"], bins=60, kde=True, color="#2563eb", ax=ax)
    ax.axvline(bias_db, color="#dc2626", linestyle="--", linewidth=2.5, label=f"Bias = {bias_db:.2f} dB")
    ax.axvline(mae_db, color="#f97316", linestyle=":", linewidth=2.5, label=f"MAE = {mae_db:.2f} dB")
    ax.set_xlabel("Error de predicción [dB]  (RF Tool − Atoll)", fontsize=11)
    ax.set_ylabel("Densidad / Frecuencia", fontsize=11)
    ax.legend(loc='best', framealpha=0.9)
    ax.text(0.98, 0.02, f"N = {n_points}", transform=ax.transAxes, ha='right', va='bottom',
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8}, fontsize=10)
    fig.savefig(output_dir / "error_hist_kde.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 2: CDF error absoluto ---
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.lineplot(data=cdf_abs_df, x="abs_error_db", y="cdf", color="#059669", linewidth=2.5, ax=ax)
    
    # Línea MAE vertical
    ax.axvline(mae_db, color="#f97316", linestyle=":", linewidth=2.5, label=f"MAE = {mae_db:.2f} dB")
    
    # Líneas de referencia horizontal
    ax.axhline(0.5, color="gray", linestyle=":", alpha=0.5, linewidth=1.5)
    ax.axhline(0.9, color="gray", linestyle=":", alpha=0.5, linewidth=1.5)
    
    # Umbrales con leyenda
    threshold_colors = {3.0: "#16a34a", 6.0: "#eab308", 10.0: "#f97316", 15.0: "#dc2626"}
    threshold_lines = []
    for t in [3.0, 6.0, 10.0, 15.0]:
        if str(t) in cdf_thresholds:
            line = ax.axvline(t, linestyle="--", linewidth=1.8, color=threshold_colors[t],
                            label=f"{t:.0f} dB  ({cdf_thresholds[str(t)]*100:.1f}%)")
            threshold_lines.append(line)
    
    ax.set_xlabel("|Error| [dB]", fontsize=11)
    ax.set_ylabel("Fracción acumulada de puntos", fontsize=11)
    ax.set_ylim(0.0, 1.0)
    ax.legend(loc='lower right', framealpha=0.9, fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.savefig(output_dir / "cdf_abs_error.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 3: Scatter RF vs Atoll ---
    fig, ax = plt.subplots(figsize=(9, 9))
    sns.scatterplot(
        data=matched_df,
        x="atoll_dbm",
        y="rf_dbm",
        s=12,
        alpha=0.4,
        color="#7c3aed",
        edgecolor=None,
        ax=ax,
        label=f"Puntos  (N = {n_points})"
    )
    min_v = min(matched_df["atoll_dbm"].min(), matched_df["rf_dbm"].min())
    max_v = max(matched_df["atoll_dbm"].max(), matched_df["rf_dbm"].max())
    
    # Línea ideal 1:1
    ax.plot([min_v, max_v], [min_v, max_v], linestyle="--", color="black", linewidth=1.8, label="Referencia 1:1")
    
    # Regresión
    reg_x = np.linspace(min_v, max_v, 100)
    reg_y = slope * reg_x + intercept
    ax.plot(reg_x, reg_y, linestyle="-", color="#0f172a", linewidth=2, 
            label=f"Regresión  (slope = {slope:.4f}, r = {pearson_r:.3f})")
    
    ax.set_xlabel("RSRP Atoll [dBm]", fontsize=11)
    ax.set_ylabel("RSRP RF Tool [dBm]", fontsize=11)
    ax.legend(loc='best', framealpha=0.9, fontsize=10)
    
    # Caja de info en esquina inferior derecha
    ax.text(0.98, 0.02, f"RMSE = {rmse_db:.2f} dB\nBias = {bias_db:.2f} dB",
            transform=ax.transAxes, va='bottom', ha='right',
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=10)
    
    fig.savefig(output_dir / "scatter_rf_vs_atoll.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 4: Violin con cuartiles ---
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.violinplot(y=matched_df["error_db"], inner=None, color="#60a5fa", ax=ax)
    
    # Calcular cuartiles
    q1 = np.quantile(matched_df["error_db"], 0.25)
    q2 = np.quantile(matched_df["error_db"], 0.50)  # mediana
    q3 = np.quantile(matched_df["error_db"], 0.75)
    
    # Líneas de cuartiles en naranja
    ax.axhline(q1, color="#f97316", linestyle="-", linewidth=2.5, alpha=0.7)
    ax.axhline(q2, color="#f97316", linestyle="-", linewidth=2.5, alpha=0.7)
    ax.axhline(q3, color="#f97316", linestyle="-", linewidth=2.5, alpha=0.7)
    
    # Anotaciones de cuartiles
    ax.text(0.5, q1, f" Q1 = {q1:.2f} dB", va='center', ha='left', fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7})
    ax.text(0.5, q2, f" Q2 = {q2:.2f} dB", va='center', ha='left', fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7})
    ax.text(0.5, q3, f" Q3 = {q3:.2f} dB", va='center', ha='left', fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7})
    
    # Línea de Bias (rojo)
    ax.axhline(bias_db, color="#dc2626", linestyle="--", linewidth=2, alpha=0.8, label=f"Bias = {bias_db:.2f} dB")
    
    # Líneas ±MAE (naranja punteadas)
    ax.axhline(mae_db, color="#f97316", linestyle=":", linewidth=1.8, alpha=0.7, label=f"+MAE = +{mae_db:.2f} dB")
    ax.axhline(-mae_db, color="#f97316", linestyle=":", linewidth=1.8, alpha=0.7, label=f"−MAE = −{mae_db:.2f} dB")
    
    ax.set_ylabel("Error de predicción [dB]  (RF Tool − Atoll)", fontsize=11)
    ax.set_xlabel("")
    ax.legend(loc='best', framealpha=0.9, fontsize=9)
    fig.savefig(output_dir / "error_violin.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 5: Mapa espacial error ---
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(
        matched_df["lon"],
        matched_df["lat"],
        c=matched_df["error_db"],
        cmap="coolwarm",
        s=10,
        alpha=0.8,
        vmin=-abs(error_cmap_limit_db),
        vmax=abs(error_cmap_limit_db),
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Error de predicción [dB]  (RF Tool − Atoll)", fontsize=10)
    ax.set_xlabel("Longitud [°]", fontsize=11)
    ax.set_ylabel("Latitud [°]", fontsize=11)
    ax.text(0.02, 0.02, f"N = {n_points} puntos\nBias = {bias_db:.2f} dB",
            transform=ax.transAxes, va='bottom', ha='left',
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=10)
    fig.savefig(output_dir / "error_spatial_map.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 6: Mapa distancia match ---
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(
        matched_df["lon"],
        matched_df["lat"],
        c=matched_df["match_distance_m"],
        cmap="viridis",
        s=10,
        alpha=0.8,
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Distancia de emparejamiento [m]", fontsize=10)
    ax.set_xlabel("Longitud [°]", fontsize=11)
    ax.set_ylabel("Latitud [°]", fontsize=11)
    ax.text(0.02, 0.02, f"P50 = {match_dist_p50:.1f} m\nP95 = {match_dist_p95:.1f} m",
            transform=ax.transAxes, va='bottom', ha='left',
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=10)
    fig.savefig(output_dir / "match_distance_spatial_map.png", dpi=180, bbox_inches='tight')
    plt.close(fig)

    # --- Gráfico 7: Sensibilidad de tolerancias ---
    if not sweep_df.empty:
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = ax1.twinx()
        
        line1 = ax1.plot(sweep_df["tolerance_m"], sweep_df["rmse_db"], marker="o", color="#dc2626", 
                        linewidth=2.5, markersize=8, label="RMSE [dB]")
        line2 = ax2.plot(sweep_df["tolerance_m"], sweep_df["bias_db"], marker="s", color="#2563eb",
                        linewidth=2.5, markersize=8, label="Bias [dB]")
        
        ax1.set_xlabel("Umbral de emparejamiento [m]", fontsize=11)
        ax1.set_ylabel("RMSE [dB]", color="#dc2626", fontsize=11)
        ax2.set_ylabel("Bias [dB]", color="#2563eb", fontsize=11)
        ax1.tick_params(axis='y', labelcolor="#dc2626")
        ax2.tick_params(axis='y', labelcolor="#2563eb")
        
        # Leyenda combinada
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc='best', framealpha=0.9, fontsize=10)
        
        fig.savefig(output_dir / "tolerance_sensitivity.png", dpi=180, bbox_inches='tight')
        plt.close(fig)

    # --- Gráfico 8 NUEVO: Barras de métricas resumen ---
    fig, ax = plt.subplots(figsize=(10, 5))
    metrics_names = ["RMSE", "MAE", "|Bias|"]
    metrics_values = [rmse_db, mae_db, abs(bias_db)]
    colors = ["#dc2626", "#f97316", "#2563eb"]
    
    bars = ax.barh(metrics_names, metrics_values, color=colors, alpha=0.85, edgecolor="black", linewidth=1.5)
    
    # Anotaciones con valores al final de cada barra
    for i, (bar, val) in enumerate(zip(bars, metrics_values)):
        ax.text(val + 0.15, bar.get_y() + bar.get_height()/2, f"{val:.2f} dB",
                va='center', ha='left', fontsize=11, fontweight='bold')
    
    ax.set_xlabel("Valor [dB]", fontsize=11)
    ax.set_xlim(0, max(metrics_values) * 1.3)
    ax.grid(axis='x', alpha=0.3)
    fig.savefig(output_dir / "metrics_summary_bar.png", dpi=180, bbox_inches='tight')
    plt.close(fig)
    
    log.info(f"✅ Gráficos guardados en {output_dir} (8 figuras generadas)")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Comparador Atoll vs RF Tool")
    parser.add_argument("--atoll-txt", type=Path, default=config.ATOLL_TXT_PATH)
    parser.add_argument("--rf-csv", type=Path, default=config.RF_CSV_PATH)
    parser.add_argument("--output-dir", type=Path, default=config.OUTPUT_DIR)
    parser.add_argument("--source-crs", type=str, default=config.SOURCE_CRS)
    parser.add_argument("--work-crs", type=str, default=config.WORK_CRS)
    parser.add_argument("--tolerance-m", type=float, default=config.MATCH_TOLERANCE_M)
    parser.add_argument("--strict-distance-m", type=float, default=config.DISTANCE_STRICT_THRESHOLD_M)
    parser.add_argument("--error-cmap-limit-db", type=float, default=config.ERROR_CMAP_LIMIT_DB)
    parser.add_argument("--tolerance-sweep", type=str, default=",".join(str(v) for v in config.TOLERANCE_SWEEP_LIST))
    parser.add_argument("--use-mutual-match-filter", action=argparse.BooleanOptionalAction, default=config.USE_MUTUAL_MATCH_FILTER)
    return parser


def main() -> None:
    log.info("=" * 80)
    log.info("INICIANDO COMPARACION ATOLL vs RF TOOL")
    log.info("=" * 80)
    
    args = build_arg_parser().parse_args()

    atoll_txt = args.atoll_txt.resolve()
    rf_csv = args.rf_csv.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Configuración:")
    log.info(f"  Atoll TXT: {atoll_txt}")
    log.info(f"  RF CSV: {rf_csv}")
    log.info(f"  Output: {output_dir}")
    log.info(f"  Tolerancia match: {args.tolerance_m}m")
    log.info(f"  CRS: source={args.source_crs}, work={args.work_crs}")

    if not atoll_txt.exists():
        log.error(f"❌ No existe: {atoll_txt}")
        raise FileNotFoundError(f"No existe archivo Atoll: {atoll_txt}")
    if not rf_csv.exists():
        log.error(f"❌ No existe: {rf_csv}")
        raise FileNotFoundError(f"No existe CSV RF: {rf_csv}")

    tolerance_values = [float(v.strip()) for v in args.tolerance_sweep.split(",") if v.strip()]
    if not tolerance_values:
        raise ValueError("Debe definir al menos una tolerancia en --tolerance-sweep")

    log.info(f"Iniciando carga de datos...")
    atoll_meta, atoll_df = parse_atoll_txt(atoll_txt)
    rf_df = load_rf_csv(rf_csv)

    atoll_df = atoll_df.reset_index(drop=True)
    atoll_df["atoll_idx"] = atoll_df.index

    rf_df = rf_df.reset_index(drop=True)
    rf_df["rf_idx"] = rf_df.index

    log.info(f"Proyectando coordenadas a {args.work_crs}...")
    atoll_proj = project_coordinates(atoll_df, args.source_crs, args.work_crs)
    rf_proj = project_coordinates(rf_df, args.source_crs, args.work_crs)

    log.info(f"Buscando correspondencias...")
    matched_df, match_quality, forward_pairs = match_points(
        atoll_proj,
        rf_proj,
        args.tolerance_m,
        args.use_mutual_match_filter,
    )

    if matched_df.empty:
        log.error("❌ NO HAY PUNTOS EMPAREJADOS - VERIFICAR CONFIGURACION")
        log.error(f"  - Atoll área: [{atoll_df['lon'].min():.4f}, {atoll_df['lon'].max():.4f}] x [{atoll_df['lat'].min():.4f}, {atoll_df['lat'].max():.4f}]")
        log.error(f"  - RF área: [{rf_df['lon'].min():.4f}, {rf_df['lon'].max():.4f}] x [{rf_df['lat'].min():.4f}, {rf_df['lat'].max():.4f}]")
        raise ValueError("No hay puntos emparejados")

    log.info(f"Calculando métricas principales...")
    strict_matched_df = matched_df[matched_df["match_distance_m"] <= args.strict_distance_m].copy()
    strict_metrics = compute_metrics(strict_matched_df) if not strict_matched_df.empty else None

    metrics = compute_metrics(matched_df)
    cdf_abs_df, cdf_signed_df = save_cdf_data(matched_df, output_dir)
    cdf_thresholds = compute_threshold_cdf(cdf_abs_df, thresholds=[3.0, 6.0, 10.0, 15.0])

    log.info(f"Ejecutando barrido de tolerancias...")
    sweep_df = run_tolerance_sweep(forward_pairs, atoll_proj, rf_proj, tolerance_values)
    sweep_df.to_csv(output_dir / "tolerance_sweep_metrics.csv", index=False)
    
    log.info(f"Evaluando confiabilidad del matching...")
    reliability = assess_match_reliability(metrics, sweep_df, args.tolerance_m)

    log.info(f"Generando gráficos...")
    generate_plots(
        matched_df,
        cdf_abs_df,
        cdf_thresholds,
        metrics,
        output_dir,
        args.error_cmap_limit_db,
        sweep_df,
    )

    log.info(f"Guardando datos de salida...")
    matched_df.to_csv(output_dir / "matched_points.csv", index=False)
    if strict_metrics is not None:
        strict_matched_df.to_csv(output_dir / "matched_points_strict.csv", index=False)
    cdf_signed_df.to_csv(output_dir / "cdf_signed_error.csv", index=False)

    report = {
        "timestamp": datetime.now().isoformat(),
        "input_files": {
            "atoll_txt": str(atoll_txt),
            "rf_csv": str(rf_csv),
        },
        "config": {
            "source_crs": args.source_crs,
            "work_crs": args.work_crs,
            "tolerance_m": args.tolerance_m,
            "strict_distance_m": args.strict_distance_m,
            "error_cmap_limit_db": args.error_cmap_limit_db,
            "use_mutual_match_filter": args.use_mutual_match_filter,
            "tolerance_sweep": tolerance_values,
        },
        "counts": {
            "atoll_points": int(len(atoll_df)),
            "rf_points": int(len(rf_df)),
            "matched_points": int(len(matched_df)),
            "strict_matched_points": int(len(strict_matched_df)),
        },
        "atoll_metadata": atoll_meta,
        "match_quality": match_quality,
        "metrics": metrics,
        "strict_metrics": strict_metrics,
        "cdf_thresholds": cdf_thresholds,
        "match_reliability": reliability,
        "tolerance_sweep": sweep_df.to_dict(orient="records"),
    }

    with (output_dir / "metrics_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    summary_df = pd.DataFrame(
        [
            {
                "metric": "RMSE_dB",
                "value": metrics["rmse_db"],
            },
            {
                "metric": "Bias_dB",
                "value": metrics["bias_db"],
            },
            {
                "metric": "Pearson_r",
                "value": metrics["pearson_r"],
            },
            {
                "metric": "MatchDistanceP95_m",
                "value": metrics["match_distance_p95"],
            },
            {
                "metric": "Reliability",
                "value": reliability["match_reliability"],
            },
        ]
    )
    summary_df.to_csv(output_dir / "executive_summary.csv", index=False)

    log.info("")
    log.info("=" * 80)
    log.info("RESUMEN FINAL")
    log.info("=" * 80)
    log.info(f"Puntos Atoll: {len(atoll_df)}")
    log.info(f"Puntos RF: {len(rf_df)}")
    log.info(f"Puntos emparejados: {len(matched_df)} ({match_quality['match_rate_vs_atoll']*100:.1f}%)")
    log.info(f"Puntos emparejados estrictos: {len(strict_matched_df)}")
    log.info(f"")
    log.info(f"RMSE: {metrics['rmse_db']:.3f} dB")
    log.info(f"Bias: {metrics['bias_db']:.3f} dB")
    log.info(f"Pearson r: {metrics['pearson_r']:.4f}")
    log.info(f"Confiabilidad de match: {reliability['match_reliability']}")
    log.info(f"")
    log.info(f"✅ Resultados guardados en: {output_dir}")
    log.info("=" * 80)

    print("\n" + "=" * 80)
    print("COMPARACION COMPLETADA")
    print("=" * 80)
    print(f"Puntos Atoll: {len(atoll_df)}")
    print(f"Puntos RF: {len(rf_df)}")
    print(f"Puntos emparejados: {len(matched_df)}")
    print(f"RMSE: {metrics['rmse_db']:.3f} dB")
    print(f"Bias: {metrics['bias_db']:.3f} dB")
    print(f"Pearson r: {metrics['pearson_r']:.4f}")
    print(f"Resultados en: {output_dir}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
