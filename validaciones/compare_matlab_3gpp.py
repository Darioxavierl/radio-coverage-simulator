"""
compare_matlab_3gpp.py
======================
Comparación entre la salida del programa Python (RF Coverage Tool, escenario A6)
y la salida del script MATLAB de referencia (3GPP TR 38.901 estadístico puro).

Diferencias respecto a compare_atoll_rf.py:
  - Referencia: CSV MATLAB (wide format) en lugar de TXT Atoll.
  - Python CSV: long format (una fila por antena × punto) → se agrega a best-server.
  - Ambas grillas están en lat/lon WGS84 → proyección UTM solo para cálculo de distancias.
  - Análisis adicional: comparación de P_LOS vs error y path loss por antena.

Uso:
    python compare_matlab_3gpp.py [--py-csv PATH] [--matlab-csv PATH] [--output-dir PATH]

Salidas (en output-dir):
    matched_points.csv          Pares coincidentes con error
    metrics_report.json         Todas las métricas en JSON
    cdf_abs_error.csv           CDF error absoluto
    cdf_signed_error.csv        CDF error con signo
    tolerance_sweep_metrics.csv Barrido de tolerancias
    error_hist_kde.png          Histograma + KDE del error
    cdf_abs_error.png           CDF error absoluto
    scatter_py_vs_matlab.png    Scatter Python vs MATLAB
    error_violin.png            Violín con cuartiles
    error_spatial_map.png       Mapa espacial del error
    plos_vs_error.png           P_LOS vs |error| (específico MATLAB)
    tolerance_sensitivity.png   RMSE/Bias vs tolerancia
"""

import argparse
import json
import logging
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rutas por defecto
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

DEFAULT_PY_CSV    = _ROOT / "data" / "exports" / "validacion" / "A6.csv"
DEFAULT_MAT_CSV   = _ROOT / "matlab" / "simulacion_compara_3gpp.csv"
DEFAULT_OUTPUT    = _HERE / "resultados" / "A6"

# EPSG:4326  WGS84 — Coordenadas geográficas
WORK_CRS    = "EPSG:4326"
SOURCE_CRS  = "EPSG:4326"

DEFAULT_TOLERANCE_M        = 25.0    # Tolerancia principal (m) — grillas ~20m vs ~10m
DEFAULT_STRICT_DIST_M      = 15.0    # Criterio estricto adicional
DEFAULT_TOLERANCE_SWEEP    = [10, 15, 20, 25, 30, 40, 50, 75, 100]
DEFAULT_ERROR_CMAP_LIMIT   = 15.0    # Límite colormap mapa espacial (dB)


# ===========================================================================
# 1. Carga de datos
# ===========================================================================

def load_python_csv(file_path: Path) -> pd.DataFrame:
    """
    Carga el CSV del programa Python (long format) y agrega a best-server.

    El CSV tiene una fila por (antena × punto de grilla). Se agrupa por
    (grid_lat, grid_lon) y se toma el máximo rsrp_dbm (best-server).

    Columnas entrada: antenna_id, grid_lat, grid_lon, rsrp_dbm, path_loss_db, ...
    Columnas salida: lat, lon, py_dbm
    """
    log.info(f"Cargando CSV Python: {file_path}")
    df = pd.read_csv(file_path)
    log.info(f"  Forma raw: {df.shape} | Columnas: {list(df.columns)}")

    required = {"grid_lat", "grid_lon", "rsrp_dbm"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en CSV Python: {sorted(missing)}")

    df = df.dropna(subset=["grid_lat", "grid_lon", "rsrp_dbm"])

    # Agregar a best-server: máximo RSRP por punto de grilla
    best = (
        df.groupby(["grid_lat", "grid_lon"], as_index=False)["rsrp_dbm"]
        .max()
        .rename(columns={"grid_lat": "lat", "grid_lon": "lon", "rsrp_dbm": "py_dbm"})
    )

    log.info(f"  Puntos únicos de grilla (best-server): {len(best)}")
    log.info(f"  RSRP Python: [{best['py_dbm'].min():.1f}, {best['py_dbm'].max():.1f}] dBm")
    return best


def load_matlab_csv(file_path: Path) -> pd.DataFrame:
    """
    Carga el CSV de MATLAB (wide format).

    Columnas de interés:
      Latitud, Longitud, RSRP_Max_dBm (best-server)
      PLOS_Ant1/2/3 (probabilidad LOS por antena)
      PathLoss_Ant1/2/3 (path loss por antena)
      Best_Antenna_ID

    Columnas salida: lat, lon, mat_dbm, plos_mean, best_antenna_id, ...
    """
    log.info(f"Cargando CSV MATLAB: {file_path}")
    df = pd.read_csv(file_path)
    log.info(f"  Forma raw: {df.shape} | Columnas: {list(df.columns)}")

    required = {"Latitud", "Longitud", "RSRP_Max_dBm"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en CSV MATLAB: {sorted(missing)}")

    df = df.dropna(subset=["Latitud", "Longitud", "RSRP_Max_dBm"])

    result = df.rename(columns={
        "Latitud": "lat",
        "Longitud": "lon",
        "RSRP_Max_dBm": "mat_dbm",
    }).copy()

    # P_LOS media entre antenas (si disponible)
    plos_cols = [c for c in df.columns if c.startswith("PLOS_")]
    if plos_cols:
        result["plos_mean"] = df[plos_cols].mean(axis=1)
    else:
        result["plos_mean"] = np.nan

    # Columnas opcionales
    pl_cols = {c: c for c in df.columns if c.startswith("PathLoss_")}
    for src, dst in pl_cols.items():
        result[dst] = df[src]

    if "Best_Antenna_ID" in df.columns:
        result["best_antenna_id"] = df["Best_Antenna_ID"]

    log.info(f"  Puntos MATLAB: {len(result)}")
    log.info(f"  RSRP MATLAB: [{result['mat_dbm'].min():.1f}, {result['mat_dbm'].max():.1f}] dBm")
    if not result["plos_mean"].isna().all():
        log.info(f"  P_LOS media: [{result['plos_mean'].min():.3f}, {result['plos_mean'].max():.3f}]")
    return result


# ===========================================================================
# 2. Proyección y matching espacial
# ===========================================================================

def project_to_utm(df: pd.DataFrame, lat_col="lat", lon_col="lon") -> pd.DataFrame:
    """Proyecta lat/lon WGS84 → UTM 17S y agrega columnas x_m, y_m."""
    transformer = Transformer.from_crs(SOURCE_CRS, WORK_CRS, always_xy=True)
    x, y = transformer.transform(df[lon_col].to_numpy(), df[lat_col].to_numpy())
    out = df.copy()
    out["x_m"] = x
    out["y_m"] = y
    return out


def match_grids(
    py_df: pd.DataFrame,
    mat_df: pd.DataFrame,
    tolerance_m: float,
) -> pd.DataFrame:
    """
    Empareja puntos Python ↔ MATLAB por vecino más cercano (KDTree en UTM).

    Solo mantiene pares con distancia ≤ tolerance_m.
    Devuelve DataFrame con columnas de ambas grillas más error_db.
    """
    log.info(f"Matcheando grillas (tolerancia={tolerance_m}m)...")
    tree = cKDTree(mat_df[["x_m", "y_m"]].to_numpy())
    dists, idx = tree.query(py_df[["x_m", "y_m"]].to_numpy(), k=1)

    matched = py_df.copy()
    matched["match_dist_m"] = dists
    matched["mat_idx"] = idx

    # Agregar columnas MATLAB
    mat_cols = ["lat", "lon", "mat_dbm", "plos_mean"] + \
               [c for c in mat_df.columns if c.startswith("PathLoss_") or c == "best_antenna_id"]
    for col in mat_cols:
        if col in mat_df.columns:
            matched[f"mat_{col}" if col not in ("mat_dbm", "plos_mean") else col] = \
                mat_df.iloc[idx][col].to_numpy()

    # Filtrar por tolerancia
    matched = matched[matched["match_dist_m"] <= tolerance_m].copy()
    matched["error_db"] = matched["py_dbm"] - matched["mat_dbm"]
    matched["abs_error_db"] = matched["error_db"].abs()

    log.info(f"  Pares dentro de tolerancia: {len(matched)}/{len(py_df)}")
    if len(matched):
        log.info(f"  Distancia match: median={matched['match_dist_m'].median():.1f}m "
                 f"p95={matched['match_dist_m'].quantile(0.95):.1f}m")
    return matched


def build_paired_for_tolerance(
    py_df: pd.DataFrame,
    mat_df: pd.DataFrame,
    tolerance_m: float,
) -> pd.DataFrame:
    """Versión ligera de match_grids para el barrido de tolerancias (reutiliza distancias)."""
    tree = cKDTree(mat_df[["x_m", "y_m"]].to_numpy())
    dists, idx = tree.query(py_df[["x_m", "y_m"]].to_numpy(), k=1)
    mask = dists <= tolerance_m
    matched = py_df[mask].copy()
    matched["mat_dbm"] = mat_df.iloc[idx[mask]]["mat_dbm"].to_numpy()
    matched["match_dist_m"] = dists[mask]
    matched["error_db"] = matched["py_dbm"] - matched["mat_dbm"]
    matched["abs_error_db"] = matched["error_db"].abs()
    return matched


# ===========================================================================
# 3. Métricas
# ===========================================================================

def compute_metrics(matched: pd.DataFrame, label: str = "") -> dict:
    if matched.empty:
        raise ValueError(f"Sin puntos emparejados{' (' + label + ')' if label else ''}")

    error = matched["error_db"].to_numpy()
    py_v  = matched["py_dbm"].to_numpy()
    mat_v = matched["mat_dbm"].to_numpy()

    rmse = float(np.sqrt(np.mean(error**2)))
    mae  = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    if len(matched) > 1:
        r, pval = pearsonr(mat_v, py_v)
    else:
        r, pval = float("nan"), float("nan")

    slope, intercept = (np.polyfit(mat_v, py_v, 1) if len(matched) > 1
                        else (float("nan"), float("nan")))

    metrics = {
        "n_matched": int(len(matched)),
        "rmse_db": rmse,
        "mae_db": mae,
        "bias_db": bias,
        "pearson_r": float(r),
        "pearson_pvalue": float(pval),
        "regression_slope": float(slope),
        "regression_intercept": float(intercept),
        "error_p50_db": float(np.quantile(np.abs(error), 0.50)),
        "error_p90_db": float(np.quantile(np.abs(error), 0.90)),
        "error_p95_db": float(np.quantile(np.abs(error), 0.95)),
        "match_dist_median_m": float(matched["match_dist_m"].median()),
        "match_dist_p95_m":    float(matched["match_dist_m"].quantile(0.95)),
    }
    tag = f" [{label}]" if label else ""
    log.info(f"Métricas{tag}: RMSE={rmse:.2f} dB | Bias={bias:.2f} dB | "
             f"MAE={mae:.2f} dB | r={r:.4f} | N={len(matched)}")
    return metrics


def run_tolerance_sweep(
    py_proj: pd.DataFrame,
    mat_proj: pd.DataFrame,
    tolerances: Iterable[float],
) -> pd.DataFrame:
    rows = []
    for tol in tolerances:
        try:
            m = build_paired_for_tolerance(py_proj, mat_proj, tol)
            if m.empty:
                rows.append({"tolerance_m": tol, "n_matched": 0,
                             "rmse_db": np.nan, "mae_db": np.nan,
                             "bias_db": np.nan, "pearson_r": np.nan})
                continue
            met = compute_metrics(m, label=f"tol={tol}m")
            rows.append({"tolerance_m": tol, "n_matched": met["n_matched"],
                         "rmse_db": met["rmse_db"], "mae_db": met["mae_db"],
                         "bias_db": met["bias_db"], "pearson_r": met["pearson_r"]})
        except Exception as e:
            log.warning(f"  Tolerancia {tol}m falló: {e}")
            rows.append({"tolerance_m": tol, "n_matched": 0,
                         "rmse_db": np.nan, "mae_db": np.nan,
                         "bias_db": np.nan, "pearson_r": np.nan})
    return pd.DataFrame(rows)


# ===========================================================================
# 4. Gráficos
# ===========================================================================

def generate_plots(
    matched: pd.DataFrame,
    metrics: dict,
    sweep_df: pd.DataFrame,
    output_dir: Path,
    error_cmap_limit_db: float,
) -> None:
    sns.set_theme(style="whitegrid", context="talk", font_scale=1.05)
    bias   = metrics["bias_db"]
    mae    = metrics["mae_db"]
    rmse   = metrics["rmse_db"]
    r      = metrics["pearson_r"]
    slope  = metrics["regression_slope"]
    inter  = metrics["regression_intercept"]
    n      = metrics["n_matched"]

    # 1. Histograma + KDE del error
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(matched["error_db"], bins=60, kde=True, color="#2563eb", ax=ax)
    ax.axvline(bias, color="#dc2626", linestyle="--", lw=2.5, label=f"Bias = {bias:.2f} dB")
    ax.axvline(0,    color="black",   linestyle=":",  lw=1.5, label="0 dB")
    ax.set_xlabel("Error [dB]  (Python − MATLAB)", fontsize=11)
    ax.set_ylabel("Frecuencia", fontsize=11)
    ax.legend()
    ax.text(0.98, 0.97, f"N = {n}\nRMSE = {rmse:.2f} dB\nMAE = {mae:.2f} dB",
            transform=ax.transAxes, ha="right", va="top",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=10)
    fig.savefig(output_dir / "error_hist_kde.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 2. CDF error absoluto
    abs_err_sorted = np.sort(matched["abs_error_db"].to_numpy())
    cdf = np.arange(1, len(abs_err_sorted) + 1) / len(abs_err_sorted)
    cdf_abs_df = pd.DataFrame({"abs_error_db": abs_err_sorted, "cdf": cdf})
    cdf_abs_df.to_csv(output_dir / "cdf_abs_error.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(abs_err_sorted, cdf, color="#059669", lw=2.5)
    ax.axvline(mae, color="#f97316", linestyle=":", lw=2, label=f"MAE = {mae:.2f} dB")
    ax.axhline(0.5, color="gray", linestyle=":", alpha=0.4, lw=1.5)
    ax.axhline(0.9, color="gray", linestyle=":", alpha=0.4, lw=1.5)
    for t, col in [(3, "#16a34a"), (6, "#eab308"), (10, "#dc2626")]:
        idx = np.searchsorted(abs_err_sorted, t, "right") - 1
        pct = float(cdf[idx]) * 100 if idx >= 0 else 0
        ax.axvline(t, linestyle="--", lw=1.8, color=col, label=f"{t} dB → {pct:.1f}%")
    ax.set_xlabel("|Error| [dB]", fontsize=11)
    ax.set_ylabel("Fracción acumulada", fontsize=11)
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=9)
    fig.savefig(output_dir / "cdf_abs_error.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 3. CDF error con signo
    signed_sorted = np.sort(matched["error_db"].to_numpy())
    cdf_signed = np.arange(1, len(signed_sorted) + 1) / len(signed_sorted)
    pd.DataFrame({"error_db": signed_sorted, "cdf": cdf_signed}).to_csv(
        output_dir / "cdf_signed_error.csv", index=False
    )

    # 4. Scatter Python vs MATLAB
    fig, ax = plt.subplots(figsize=(9, 9))
    sns.scatterplot(data=matched, x="mat_dbm", y="py_dbm",
                    s=10, alpha=0.35, color="#7c3aed", edgecolor=None, ax=ax,
                    label=f"Puntos (N={n})")
    lo = min(matched["mat_dbm"].min(), matched["py_dbm"].min())
    hi = max(matched["mat_dbm"].max(), matched["py_dbm"].max())
    ax.plot([lo, hi], [lo, hi], "k--", lw=1.8, label="1:1")
    reg_x = np.linspace(lo, hi, 100)
    ax.plot(reg_x, slope * reg_x + inter, color="#0f172a", lw=2,
            label=f"Regresión  slope={slope:.3f}  r={r:.3f}")
    ax.set_xlabel("RSRP MATLAB [dBm]", fontsize=11)
    ax.set_ylabel("RSRP Python [dBm]", fontsize=11)
    ax.legend(fontsize=9)
    ax.text(0.98, 0.02, f"RMSE = {rmse:.2f} dB\nBias = {bias:.2f} dB",
            transform=ax.transAxes, va="bottom", ha="right",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=10)
    fig.savefig(output_dir / "scatter_py_vs_matlab.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 5. Violín con cuartiles
    fig, ax = plt.subplots(figsize=(7, 7))
    sns.violinplot(y=matched["error_db"], inner=None, color="#60a5fa", ax=ax)
    for q, lbl in [(0.25, "Q1"), (0.50, "Q2"), (0.75, "Q3")]:
        val = float(np.quantile(matched["error_db"], q))
        ax.axhline(val, color="#f97316", lw=2.2, alpha=0.75)
        ax.text(0.52, val, f" {lbl} = {val:.2f} dB", va="center", fontsize=9,
                bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.7})
    ax.axhline(bias, color="#dc2626", linestyle="--", lw=2, label=f"Bias = {bias:.2f} dB")
    ax.axhline(0, color="black", linestyle=":", lw=1.5, alpha=0.5)
    ax.set_ylabel("Error [dB]  (Python − MATLAB)", fontsize=11)
    ax.legend(fontsize=9)
    fig.savefig(output_dir / "error_violin.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 6. Mapa espacial del error
    fig, ax = plt.subplots(figsize=(10, 8))
    sc = ax.scatter(matched["lon"], matched["lat"],
                    c=matched["error_db"], cmap="coolwarm", s=8, alpha=0.75,
                    vmin=-abs(error_cmap_limit_db), vmax=abs(error_cmap_limit_db))
    plt.colorbar(sc, ax=ax, label="Error [dB]  (Python − MATLAB)")
    ax.set_xlabel("Longitud [°]")
    ax.set_ylabel("Latitud [°]")
    ax.text(0.02, 0.02, f"N={n}\nBias={bias:.2f} dB",
            transform=ax.transAxes, va="bottom", ha="left",
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85}, fontsize=9)
    fig.savefig(output_dir / "error_spatial_map.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 7. P_LOS vs |error| (específico de comparación MATLAB)
    if "plos_mean" in matched.columns and not matched["plos_mean"].isna().all():
        fig, ax = plt.subplots(figsize=(9, 6))
        sc = ax.scatter(matched["plos_mean"], matched["abs_error_db"],
                        c=matched["error_db"], cmap="coolwarm", s=8, alpha=0.5,
                        vmin=-abs(error_cmap_limit_db), vmax=abs(error_cmap_limit_db))
        plt.colorbar(sc, ax=ax, label="Error con signo [dB]")
        ax.set_xlabel("P_LOS media (MATLAB)", fontsize=11)
        ax.set_ylabel("|Error| [dB]", fontsize=11)
        ax.set_title("Relación entre probabilidad LOS y error de predicción", fontsize=11)
        # Línea de tendencia
        valid = matched[["plos_mean", "abs_error_db"]].dropna()
        if len(valid) > 5:
            sl, ic = np.polyfit(valid["plos_mean"], valid["abs_error_db"], 1)
            xx = np.linspace(valid["plos_mean"].min(), valid["plos_mean"].max(), 100)
            ax.plot(xx, sl * xx + ic, "k--", lw=1.5, alpha=0.7, label=f"tendencia (slope={sl:.2f})")
            ax.legend(fontsize=9)
        fig.savefig(output_dir / "plos_vs_error.png", dpi=180, bbox_inches="tight")
        plt.close(fig)

    # 8. Barrido de tolerancias
    if not sweep_df.empty and not sweep_df["rmse_db"].isna().all():
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = ax1.twinx()
        l1 = ax1.plot(sweep_df["tolerance_m"], sweep_df["rmse_db"],
                      "o-", color="#dc2626", lw=2.5, ms=7, label="RMSE [dB]")
        l2 = ax2.plot(sweep_df["tolerance_m"], sweep_df["bias_db"],
                      "s-", color="#2563eb", lw=2.5, ms=7, label="Bias [dB]")
        ax1.set_xlabel("Tolerancia de emparejamiento [m]", fontsize=11)
        ax1.set_ylabel("RMSE [dB]", color="#dc2626", fontsize=11)
        ax2.set_ylabel("Bias [dB]", color="#2563eb", fontsize=11)
        ax1.tick_params(axis="y", labelcolor="#dc2626")
        ax2.tick_params(axis="y", labelcolor="#2563eb")
        lines = l1 + l2
        ax1.legend(lines, [l.get_label() for l in lines], loc="best", fontsize=10)
        fig.savefig(output_dir / "tolerance_sensitivity.png", dpi=180, bbox_inches="tight")
        plt.close(fig)

    # 9. Barras de métricas resumen (RMSE, MAE, |Bias|)
    fig, ax = plt.subplots(figsize=(10, 5))
    bar_names  = ["RMSE", "MAE", "|Bias|"]
    bar_values = [rmse, mae, abs(bias)]
    bar_colors = ["#dc2626", "#f97316", "#2563eb"]
    bars = ax.barh(bar_names, bar_values, color=bar_colors, alpha=0.85,
                   edgecolor="black", linewidth=1.5)
    for bar, val in zip(bars, bar_values):
        ax.text(val + 0.15, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f} dB", va="center", ha="left",
                fontsize=11, fontweight="bold")
    ax.set_xlabel("Valor [dB]", fontsize=11)
    ax.set_xlim(0, max(bar_values) * 1.35 if bar_values else 1)
    ax.grid(axis="x", alpha=0.3)
    fig.savefig(output_dir / "metrics_summary_bar.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 10. Gauge / barra Pearson r
    fig, ax = plt.subplots(figsize=(8, 4))
    # Fondo gris (dominio completo 0–1)
    ax.barh(["Pearson r"], [1.0], color="#e5e7eb", edgecolor="black", linewidth=1.2, height=0.45)
    # Relleno coloreado según valor
    gauge_color = "#16a34a" if r >= 0.85 else ("#eab308" if r >= 0.70 else "#dc2626")
    ax.barh(["Pearson r"], [max(r, 0.0)], color=gauge_color, alpha=0.85,
            edgecolor="black", linewidth=1.2, height=0.45)
    # Línea umbral 0.85
    ax.axvline(0.85, color="#0f172a", linestyle="--", lw=1.8, label="Umbral ≥ 0.85")
    # Valor centrado
    ax.text(max(r, 0.0) / 2, 0, f"r = {r:.4f}",
            va="center", ha="center", fontsize=16, fontweight="bold",
            color="white" if r >= 0.3 else "black")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Coeficiente de Pearson", fontsize=11)
    status_r = "PASS" if r >= 0.85 else "FAIL"
    #ax.set_title(f"Correlación Pearson  —  {status_r}", fontsize=12,
    #             color="#16a34a" if status_r == "PASS" else "#dc2626", fontweight="bold")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_yticks([])
    fig.savefig(output_dir / "pearson_gauge.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    log.info(f"Gráficos guardados en {output_dir} (10 figuras)")


# ===========================================================================
# 5. Reporte de texto
# ===========================================================================

PASS_CRITERIA = {
    "mae_db":      ("<=", 6.0,  "MAE ≤ 6 dB"),
    "rmse_db":     ("<=", 8.0,  "RMSE ≤ 8 dB"),
    "bias_db":     ("abs<=", 3.0, "Bias ∈ [−3, +3] dB"),
    "pearson_r":   (">=", 0.85, "Pearson r ≥ 0.85"),
}


def _check_criterion(value: float, op: str, threshold: float) -> bool:
    if op == "<=":   return value <= threshold
    if op == ">=":   return value >= threshold
    if op == "abs<=": return abs(value) <= threshold
    return False


def write_text_summary(
    metrics: dict,
    strict_metrics: dict | None,
    match_quality: dict,
    sweep_df: pd.DataFrame,
    py_csv: Path,
    matlab_csv: Path,
    output_dir: Path,
) -> None:
    lines = []
    sep = "=" * 80
    lines += [sep,
              "Comparacion RF Coverage Tool (Python) vs MATLAB 3GPP TR 38.901",
              f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
              sep, ""]

    lines += ["ARCHIVOS DE ENTRADA:",
              f"  Python CSV : {py_csv}",
              f"  MATLAB CSV : {matlab_csv}", ""]

    lines += ["CALIDAD DEL EMPAREJAMIENTO:",
              f"  Puntos Python (best-server)  : {match_quality['py_points']}",
              f"  Puntos MATLAB (best-server)  : {match_quality['mat_points']}",
              f"  Pares emparejados            : {match_quality['matched_pairs']}",
              f"  Tasa de match                : {match_quality['match_rate']*100:.1f}%",
              f"  Distancia mediana match      : {metrics['match_dist_median_m']:.1f} m",
              f"  Distancia P95 match          : {metrics['match_dist_p95_m']:.1f} m", ""]

    lines += ["METRICAS PRINCIPALES (tolerancia principal):"]
    lines += [f"  {'Metrica':<28} {'Valor':>10}  {'Criterio':<20}  {'Estado'}"]
    lines += [f"  {'-'*70}"]

    all_pass = True
    for key, (op, threshold, desc) in PASS_CRITERIA.items():
        val = metrics.get(key, float("nan"))
        ok = _check_criterion(val, op, threshold)
        if not ok:
            all_pass = False
        status = "PASS" if ok else "FAIL"
        lines.append(f"  {desc:<28} {val:>10.4f}  {desc:<20}  {status}")

    lines += ["",
              f"  RMSE                         : {metrics['rmse_db']:.4f} dB",
              f"  MAE                          : {metrics['mae_db']:.4f} dB",
              f"  Bias                         : {metrics['bias_db']:.4f} dB",
              f"  Pearson r                    : {metrics['pearson_r']:.4f}",
              f"  Error P50                    : {metrics['error_p50_db']:.4f} dB",
              f"  Error P90                    : {metrics['error_p90_db']:.4f} dB",
              f"  Error P95                    : {metrics['error_p95_db']:.4f} dB", ""]

    veredicto = "APROBADO" if all_pass else "REPROBADO"
    lines += [f"VEREDICTO (criterios Plan A6): {veredicto}", ""]

    if strict_metrics:
        lines += ["METRICAS ESTRICTAS (distancia match reducida):",
                  f"  N puntos     : {strict_metrics['n_matched']}",
                  f"  RMSE         : {strict_metrics['rmse_db']:.4f} dB",
                  f"  Bias         : {strict_metrics['bias_db']:.4f} dB",
                  f"  Pearson r    : {strict_metrics['pearson_r']:.4f}", ""]

    if not sweep_df.empty:
        lines += ["SENSIBILIDAD DE TOLERANCIA:"]
        lines += [f"  {'Tolerancia (m)':>14}  {'N pares':>8}  {'RMSE (dB)':>10}  {'Bias (dB)':>10}  {'r':>7}"]
        for _, row in sweep_df.iterrows():
            n_v = int(row["n_matched"]) if not np.isnan(row["n_matched"]) else 0
            rmse_v = f"{row['rmse_db']:.3f}" if not np.isnan(row.get("rmse_db", float("nan"))) else "N/A"
            bias_v = f"{row['bias_db']:.3f}" if not np.isnan(row.get("bias_db", float("nan"))) else "N/A"
            r_v    = f"{row['pearson_r']:.3f}" if not np.isnan(row.get("pearson_r", float("nan"))) else "N/A"
            lines.append(f"  {row['tolerance_m']:>14.0f}  {n_v:>8}  {rmse_v:>10}  {bias_v:>10}  {r_v:>7}")
        lines.append("")

    summary_path = output_dir / "comparison_summary.txt"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Resumen guardado: {summary_path}")

    # Imprimir en consola
    print("\n" + "\n".join(lines))


# ===========================================================================
# 6. Main
# ===========================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Comparación RF Coverage Tool (Python) vs MATLAB 3GPP TR 38.901 — Escenario A6"
    )
    p.add_argument("--py-csv",       type=Path, default=DEFAULT_PY_CSV,
                   help=f"CSV exportado por el programa Python (default: {DEFAULT_PY_CSV})")
    p.add_argument("--matlab-csv",   type=Path, default=DEFAULT_MAT_CSV,
                   help=f"CSV generado por MATLAB (default: {DEFAULT_MAT_CSV})")
    p.add_argument("--output-dir",   type=Path, default=DEFAULT_OUTPUT,
                   help=f"Directorio de salida (default: {DEFAULT_OUTPUT})")
    p.add_argument("--tolerance-m",  type=float, default=DEFAULT_TOLERANCE_M,
                   help=f"Tolerancia principal de emparejamiento en m (default: {DEFAULT_TOLERANCE_M})")
    p.add_argument("--strict-dist-m", type=float, default=DEFAULT_STRICT_DIST_M,
                   help=f"Distancia estricta adicional en m (default: {DEFAULT_STRICT_DIST_M})")
    p.add_argument("--error-cmap-limit", type=float, default=DEFAULT_ERROR_CMAP_LIMIT,
                   help=f"Límite colormap mapa espacial en dB (default: {DEFAULT_ERROR_CMAP_LIMIT})")
    p.add_argument("--tolerance-sweep", type=str,
                   default=",".join(str(v) for v in DEFAULT_TOLERANCE_SWEEP),
                   help="Lista de tolerancias para el barrido, separadas por coma")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    py_csv    = args.py_csv.resolve()
    matlab_csv = args.matlab_csv.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Añadir log a fichero
    fh = logging.FileHandler(output_dir / "comparison.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
    logging.getLogger().addHandler(fh)

    tolerance_sweep = [float(v.strip()) for v in args.tolerance_sweep.split(",") if v.strip()]

    log.info("=" * 70)
    log.info("COMPARACION RF Tool (Python) vs MATLAB 3GPP TR 38.901  [Escenario A6]")
    log.info("=" * 70)
    log.info(f"Python CSV  : {py_csv}")
    log.info(f"MATLAB CSV  : {matlab_csv}")
    log.info(f"Output      : {output_dir}")
    log.info(f"Tolerancia  : {args.tolerance_m} m")

    if not py_csv.exists():
        log.error(f"No existe el CSV Python: {py_csv}")
        sys.exit(1)
    if not matlab_csv.exists():
        log.error(f"No existe el CSV MATLAB: {matlab_csv}")
        sys.exit(1)

    # --- Carga ---
    py_df  = load_python_csv(py_csv)
    mat_df = load_matlab_csv(matlab_csv)

    # --- Proyección UTM ---
    log.info("Proyectando a UTM 17S...")
    py_proj  = project_to_utm(py_df)
    mat_proj = project_to_utm(mat_df)

    # --- Match principal ---
    matched = match_grids(py_proj, mat_proj, args.tolerance_m)
    if matched.empty:
        log.error("Sin puntos emparejados — verifica que las grillas se solapan geográficamente.")
        log.error(f"  Python  lat=[{py_df['lat'].min():.4f},{py_df['lat'].max():.4f}] "
                  f"lon=[{py_df['lon'].min():.4f},{py_df['lon'].max():.4f}]")
        log.error(f"  MATLAB  lat=[{mat_df['lat'].min():.4f},{mat_df['lat'].max():.4f}] "
                  f"lon=[{mat_df['lon'].min():.4f},{mat_df['lon'].max():.4f}]")
        sys.exit(1)

    # --- Métricas principales ---
    metrics = compute_metrics(matched, "tolerancia principal")

    # --- Métricas estrictas ---
    strict_matched = matched[matched["match_dist_m"] <= args.strict_dist_m].copy()
    strict_metrics = compute_metrics(strict_matched, "estricto") if not strict_matched.empty else None

    # --- Barrido de tolerancias ---
    log.info("Barrido de tolerancias...")
    sweep_df = run_tolerance_sweep(py_proj, mat_proj, tolerance_sweep)
    sweep_df.to_csv(output_dir / "tolerance_sweep_metrics.csv", index=False)

    # --- Gráficos ---
    generate_plots(matched, metrics, sweep_df, output_dir, args.error_cmap_limit)

    # --- Guardar datos ---
    matched.to_csv(output_dir / "matched_points.csv", index=False)
    if strict_metrics:
        strict_matched.to_csv(output_dir / "matched_points_strict.csv", index=False)

    match_quality = {
        "py_points":     int(len(py_df)),
        "mat_points":    int(len(mat_df)),
        "matched_pairs": int(len(matched)),
        "match_rate":    float(len(matched) / len(py_df)) if len(py_df) else 0.0,
    }

    report = {
        "timestamp": datetime.now().isoformat(),
        "input_files": {"py_csv": str(py_csv), "matlab_csv": str(matlab_csv)},
        "config": {
            "tolerance_m": args.tolerance_m,
            "strict_dist_m": args.strict_dist_m,
            "work_crs": WORK_CRS,
            "tolerance_sweep": tolerance_sweep,
        },
        "match_quality": match_quality,
        "metrics": metrics,
        "strict_metrics": strict_metrics,
        "tolerance_sweep": sweep_df.to_dict(orient="records"),
    }
    with (output_dir / "metrics_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # --- Resumen en texto ---
    write_text_summary(
        metrics, strict_metrics, match_quality,
        sweep_df, py_csv, matlab_csv, output_dir
    )

    log.info("=" * 70)
    log.info(f"Completado. Resultados en: {output_dir}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
