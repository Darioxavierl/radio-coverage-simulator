"""
analyze_gpu_benchmark.py — Analisis y visualizacion del benchmark GPU/CPU

Lee los *_runs.csv generados por benchmark_gpu.py, calcula estadisticas
internamente (mediana/media/std/CV/speedup) y genera figuras por escenario.

Uso:
    .venv/Scripts/python.exe analyze_gpu_benchmark.py
    .venv/Scripts/python.exe analyze_gpu_benchmark.py --scenarios G1 G3 G4
    .venv/Scripts/python.exe analyze_gpu_benchmark.py --show

Salida:
    validaciones/resultados/aceleracion/
        G1/  speedup_bars.png  cpu_time_series.png  gpu_time_series.png  boxplot_pathloss.png
        G2/  ...
        G3/  ...
        G4/  ...
        G5/  ...
        G6/
            okumura_hata/  cost231_hata/  itu_p1546/  three_gpp_38901/
                speedup_bars.png  cpu_time_series.png  gpu_time_series.png  boxplot_pathloss.png
            speedup_bars_all_models.png
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sin ventana; se sobreescribe con --show
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).resolve().parent.parent
GPU_DIR   = ROOT_DIR / "data" / "exports" / "validacion" / "GPU"
OUT_DIR   = ROOT_DIR / "validaciones" / "resultados" / "aceleracion"

# Escenarios G1–G5 y sus descripciones
SCENARIO_META = {
    "G1": {"desc": "Monocelda 40 K pts",       "n_ant": 1},
    "G2": {"desc": "Monocelda 122 K pts",       "n_ant": 1},
    "G3": {"desc": "Monocelda 250 K pts",       "n_ant": 1},
    "G4": {"desc": "Multi-antena 5 celdas",     "n_ant": 5},
    "G5": {"desc": "Multi-antena 9 celdas",     "n_ant": 9},
}

G6_MODELS = ["okumura_hata", "cost231_hata", "itu_p1546", "three_gpp_38901"]

G6_LABELS = {
    "okumura_hata":   "Okumura-Hata",
    "cost231_hata":   "COST-231 Hata",
    "itu_p1546":      "ITU-R P.1546",
    "three_gpp_38901":"3GPP 38.901",
}

# Métricas para barras de speedup
SPEEDUP_METRICS = [
    ("coverage_s",   "RF coverage"),
    ("pathloss_s",   "Path Loss"),
    ("total_s",      "Total"),
]

# Colores
C_CPU        = "#3498db"
C_GPU        = "#e74c3c"
C_SPEEDUP_OK = "#2ecc71"
C_SPEEDUP_NO = "#e67e22"
C_MEDIAN     = "#2c3e50"
C_MEAN       = "#8e44ad"

# ══════════════════════════════════════════════════════════════════════════════
# CARGA Y ESTADÍSTICAS
# ══════════════════════════════════════════════════════════════════════════════

def load_runs(csv_path: Path) -> pd.DataFrame | None:
    """Lee un *_runs.csv y devuelve solo filas de medicion (is_warmup==False)."""
    if not csv_path.exists():
        print(f"  [AVISO] No encontrado: {csv_path.relative_to(ROOT_DIR)}")
        return None
    df = pd.read_csv(csv_path)
    df = df[df["is_warmup"] == False].reset_index(drop=True)
    if df.empty:
        print(f"  [AVISO] Sin runs de medicion en: {csv_path.name}")
        return None
    return df


def compute_stats(df: pd.DataFrame, metric: str) -> dict:
    """Calcula estadisticas basicas de una metrica sobre el DataFrame."""
    vals = df[metric].dropna().values.astype(float)
    if len(vals) == 0:
        return {"median": np.nan, "mean": np.nan, "std": np.nan,
                "cv_pct": np.nan, "n": 0, "vals": vals}
    med = float(np.median(vals))
    mn  = float(np.mean(vals))
    sd  = float(np.std(vals, ddof=1)) if len(vals) > 1 else np.nan
    cv  = sd / mn * 100 if mn != 0 else np.nan
    if len(vals) > 1:
        t_crit  = float(sp_stats.t.ppf(0.975, df=len(vals) - 1))
        sem     = sd / np.sqrt(len(vals))
        ci95_lo = mn - t_crit * sem
        ci95_hi = mn + t_crit * sem
    else:
        ci95_lo = ci95_hi = mn
    return {"median": med, "mean": mn, "std": sd, "cv_pct": cv,
            "n": len(vals), "vals": vals,
            "ci95_lo": float(ci95_lo), "ci95_hi": float(ci95_hi)}


def speedup_ratio(cpu_stats: dict, gpu_stats: dict) -> float:
    """Speedup = cpu_mean / gpu_mean. nan si datos insuficientes."""
    c, g = cpu_stats["mean"], gpu_stats["mean"]
    if np.isnan(c) or np.isnan(g) or g == 0:
        return np.nan
    return c / g


def gpu_device_label(df: pd.DataFrame) -> str:
    """Extrae el nombre del dispositivo GPU del DataFrame."""
    if df is None:
        return "GPU"
    col = df["gpu_device"].dropna()
    if col.empty:
        return "GPU"
    raw = col.iloc[0]
    # "GPU: NVIDIA GeForce GTX 1660 SUPER (CC 7.5)" → "GTX 1660 SUPER"
    raw = str(raw).replace("GPU: ", "").strip()
    return raw


# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICA 1 — BARRAS DE SPEEDUP
# ══════════════════════════════════════════════════════════════════════════════

def plot_speedup_bars(cpu_df: pd.DataFrame, gpu_df: pd.DataFrame,
                      out_path: Path, title: str) -> None:
    """
    Barras horizontales de speedup CPU/GPU para coverage_s, pathloss_s, total_s.
    Calcula internamente desde los DataFrames de runs.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    labels  = []
    speedups = []
    colors   = []

    for metric, label in SPEEDUP_METRICS:
        if metric not in (cpu_df.columns if cpu_df is not None else []):
            continue
        cs = compute_stats(cpu_df, metric) if cpu_df is not None else {"median": np.nan}
        gs = compute_stats(gpu_df, metric) if gpu_df is not None else {"median": np.nan}
        sp = speedup_ratio(cs, gs)
        labels.append(label)
        speedups.append(sp)
        colors.append(C_SPEEDUP_OK if (not np.isnan(sp) and sp > 1.0) else C_SPEEDUP_NO)

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(labels))
    bars = ax.bar(x, speedups, color=colors, edgecolor="white",
                  linewidth=0.8, width=0.55, zorder=3)

    # Línea de referencia CPU=GPU
    ax.axhline(1.0, color="#e74c3c", linestyle="--", linewidth=1.2,
               label="CPU = GPU (1.0×)", zorder=4)

    # Valor encima o dentro de cada barra
    for bar, sp in zip(bars, speedups):
        if np.isnan(sp):
            txt = "N/D"
        else:
            txt = f"{sp:.3f}×"
        h = bar.get_height()
        va_y = h / 2 if not np.isnan(sp) else 0.05
        ax.text(bar.get_x() + bar.get_width() / 2, va_y,
                txt, ha="center", va="center",
                fontsize=11, fontweight="bold", color="white",
                zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Speedup GPU/CPU  (×)", fontsize=10)
    #ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc="upper right")

    # Footnote con n y device
    n_cpu = cpu_df["run_id"].nunique() if cpu_df is not None else 0
    n_gpu = gpu_df["run_id"].nunique() if gpu_df is not None else 0
    dev   = gpu_device_label(gpu_df)
    fig.text(0.5, 0.01,
             f"CPU n={n_cpu}  |  GPU n={n_gpu}  |  Dispositivo: {dev}",
             ha="center", fontsize=8, color="gray")

    # Leyenda de colores
    patch_ok = mpatches.Patch(color=C_SPEEDUP_OK, label="GPU más rápida (>1×)")
    patch_no = mpatches.Patch(color=C_SPEEDUP_NO, label="GPU más lenta (<1×)")
    ax.legend(handles=[patch_ok, patch_no,
                        plt.Line2D([0], [0], color="#e74c3c",
                                   linestyle="--", linewidth=1.2,
                                   label="CPU = GPU (1.0×)")],
              fontsize=8, loc="upper right")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path.relative_to(ROOT_DIR)}")


# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICA 2 — SERIE TEMPORAL POR MODO
# ══════════════════════════════════════════════════════════════════════════════

def plot_time_series(df: pd.DataFrame, mode_label: str,
                     out_path: Path, title: str) -> None:
    """
    Grafica pathloss_s run a run con líneas de mediana y media.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metric = "pathloss_s"
    stats  = compute_stats(df, metric)
    vals   = stats["vals"]
    run_ids = df["run_id"].values

    color = C_CPU if "CPU" in mode_label.upper() else C_GPU

    fig, ax = plt.subplots(figsize=(8, 4))

    # Serie de puntos
    ax.plot(run_ids, vals, marker="o", markersize=5, linewidth=1.5,
            color=color, label=f"pathloss_s por run", zorder=3)
    ax.scatter(run_ids, vals, color=color, s=30, zorder=4)

    # Mediana y media
    ax.axhline(stats["median"], color=C_MEDIAN, linewidth=1.8,
               linestyle="-",
               label=f"Mediana = {stats['median']:.4f} s")
    ax.axhline(stats["mean"],   color=C_MEAN,   linewidth=1.5,
               linestyle="--",
               label=f"Media   = {stats['mean']:.4f} s")

    ax.set_xlabel("Número de repetición (run_id)", fontsize=10)
    ax.set_ylabel("pathloss_s  [s]", fontsize=10)
    #ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.set_xticks(run_ids)
    ax.grid(linestyle=":", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc="upper right")

    # Subtítulo con CV y std
    fig.text(0.5, 0.01,
             f"n={stats['n']}  |  std={stats['std']:.4f} s  |  CV={stats['cv_pct']:.1f}%",
             ha="center", fontsize=8, color="gray")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path.relative_to(ROOT_DIR)}")


# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICA 3 — BOXPLOT COMPARATIVO CPU vs GPU
# ══════════════════════════════════════════════════════════════════════════════

def plot_boxplot_comparison(cpu_df: pd.DataFrame, gpu_df: pd.DataFrame,
                            out_path: Path, title: str) -> None:
    """
    Boxplot CPU vs GPU (pathloss_s) en una sola figura.
    Caja = IQR, bigotes = 1.5xIQR, linea interior = mediana.
    Triangulo = media, barra de error = IC 95%.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metric = "pathloss_s"

    data_map = []
    if cpu_df is not None:
        data_map.append(("CPU", cpu_df, C_CPU))
    if gpu_df is not None:
        data_map.append(("GPU", gpu_df, C_GPU))

    if not data_map:
        return

    fig, ax = plt.subplots(figsize=(6, 5))
    positions = list(range(1, len(data_map) + 1))
    bp_data   = []
    labels_bp = []

    for pos, (lbl, df, color) in zip(positions, data_map):
        st = compute_stats(df, metric)
        bp_data.append(st["vals"])
        labels_bp.append(lbl)

        err_lo = st["mean"] - st["ci95_lo"]
        err_hi = st["ci95_hi"] - st["mean"]
        ax.errorbar(pos, st["mean"],
                    yerr=[[err_lo], [err_hi]],
                    fmt="^", color=color,
                    markersize=9, capsize=6, linewidth=1.8,
                    label=(
                        f"{lbl}  "
                        f"$\\bar{{x}}$={st['mean']:.4f} s  "
                        f"IC95%=[{st['ci95_lo']:.4f}, {st['ci95_hi']:.4f}]"
                    ),
                    zorder=5)

    bp = ax.boxplot(bp_data, positions=positions, widths=0.4,
                    patch_artist=True, zorder=3,
                    medianprops=dict(color="#2c3e50", linewidth=2),
                    whiskerprops=dict(linewidth=1.2),
                    capprops=dict(linewidth=1.5),
                    flierprops=dict(marker="o", markersize=4, alpha=0.5))

    for patch, (_, _, color) in zip(bp["boxes"], data_map):
        patch.set_facecolor(color)
        patch.set_alpha(0.4)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels_bp, fontsize=12)
    ax.set_ylabel("pathloss_s  [s]", fontsize=10)
    ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, loc="upper right")

    parts = []
    for lbl, df, _ in data_map:
        st = compute_stats(df, metric)
        parts.append(f"{lbl}: n={st['n']}  std={st['std']:.4f} s  CV={st['cv_pct']:.1f}%")
    fig.text(0.5, 0.01, "   |   ".join(parts),
             ha="center", fontsize=7.5, color="gray")

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path.relative_to(ROOT_DIR)}")


# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICA COMPARATIVA G6 — TODOS LOS MODELOS
# ══════════════════════════════════════════════════════════════════════════════

def plot_g6_all_models(model_data: dict, out_path: Path) -> None:
    """
    Grouped bar chart: eje X = 4 modelos, grupos de barras = métricas de speedup.
    model_data: {model_label: {"cpu": df, "gpu": df}}
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    metric_labels = [(m, l) for m, l in SPEEDUP_METRICS]
    n_metrics  = len(metric_labels)
    models     = [m for m in G6_MODELS if m in model_data]
    n_models   = len(models)

    if n_models == 0:
        print("  [AVISO] Sin datos G6 para figura comparativa.")
        return

    speedups_matrix = np.full((n_metrics, n_models), np.nan)

    for j, model in enumerate(models):
        cpu_df = model_data[model].get("cpu")
        gpu_df = model_data[model].get("gpu")
        for i, (metric, _) in enumerate(metric_labels):
            cs = compute_stats(cpu_df, metric) if cpu_df is not None else {"median": np.nan}
            gs = compute_stats(gpu_df, metric) if gpu_df is not None else {"median": np.nan}
            speedups_matrix[i, j] = speedup_ratio(cs, gs)

    fig, ax = plt.subplots(figsize=(10, 5))
    width   = 0.22
    x       = np.arange(n_models)
    metric_colors = ["#5dade2", "#58d68d", "#f39c12"]

    for i, (metric, m_label) in enumerate(metric_labels):
        offset = (i - n_metrics / 2 + 0.5) * width
        vals   = speedups_matrix[i]
        bar_colors = [C_SPEEDUP_OK if (not np.isnan(v) and v > 1.0)
                      else C_SPEEDUP_NO for v in vals]
        bars = ax.bar(x + offset, vals, width=width * 0.9,
                      color=bar_colors, edgecolor="white",
                      linewidth=0.6, label=m_label, zorder=3,
                      alpha=0.85)
        # Valores en las barras
        for bar, sp in zip(bars, vals):
            if np.isnan(sp):
                continue
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() / 2,
                    f"{sp:.2f}×",
                    ha="center", va="center",
                    fontsize=8, fontweight="bold", color="white", zorder=5)

    ax.axhline(1.0, color="#e74c3c", linestyle="--", linewidth=1.2,
               label="CPU = GPU (1.0×)", zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([G6_LABELS.get(m, m) for m in models], fontsize=10)
    ax.set_ylabel("Speedup GPU/CPU  (×)", fontsize=10)
    #ax.set_title("G6 — Speedup por modelo de propagación", fontsize=13, fontweight="bold", pad=10)
    ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)

    # Leyenda de métricas
    metric_patches = [mpatches.Patch(color=metric_colors[i], alpha=0.85,
                                     label=label)
                      for i, (_, label) in enumerate(metric_labels)]
    line_ref = plt.Line2D([0], [0], color="#e74c3c", linestyle="--",
                           linewidth=1.2, label="CPU = GPU")
    ax.legend(handles=metric_patches + [line_ref], fontsize=9,
              loc="upper right")

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path.relative_to(ROOT_DIR)}")


# ══════════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO POR ESCENARIO G1–G5
# ══════════════════════════════════════════════════════════════════════════════

def process_scenario(scenario_id: str, show: bool) -> None:
    base = GPU_DIR / scenario_id
    out  = OUT_DIR / scenario_id

    print(f"\n{'─'*60}")
    print(f"  Procesando {scenario_id}...")

    cpu_df = load_runs(base / "CPU_runs.csv")
    gpu_df = load_runs(base / "GPU_runs.csv")

    if cpu_df is None and gpu_df is None:
        print(f"  Sin datos para {scenario_id}, saltando.")
        return

    meta  = SCENARIO_META.get(scenario_id, {"desc": scenario_id, "n_ant": "?"})
    title_base = f"{scenario_id} — {meta['desc']}"

    # ── Figura 1: Speedup bars ────────────────────────────────────────────────
    if cpu_df is not None and gpu_df is not None:
        plot_speedup_bars(
            cpu_df, gpu_df,
            out / "speedup_bars.png",
            f"Speedup GPU/CPU — {title_base}"
        )
    else:
        print(f"  [INFO] Speedup omitido: faltan datos CPU o GPU.")

    # ── Figura 2: Serie temporal CPU ──────────────────────────────────────────
    if cpu_df is not None:
        plot_time_series(
            cpu_df, "CPU",
            out / "cpu_time_series.png",
            f"Path Loss — {title_base} — CPU"
        )

    # ── Figura 3: Serie temporal GPU ──────────────────────────────────────────
    if gpu_df is not None:
        plot_time_series(
            gpu_df, "GPU",
            out / "gpu_time_series.png",
            f"Path Loss — {title_base} — GPU"
        )

    # ── Figura 4: Boxplot comparativo CPU vs GPU ──────────────────────────────
    if cpu_df is not None or gpu_df is not None:
        plot_boxplot_comparison(
            cpu_df, gpu_df,
            out / "boxplot_pathloss.png",
            f"Distribución pathloss_s — {title_base}"
        )

    if show:
        plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO G6
# ══════════════════════════════════════════════════════════════════════════════

def process_g6(show: bool) -> None:
    base = GPU_DIR / "G6"
    out  = OUT_DIR / "G6"

    print(f"\n{'─'*60}")
    print(f"  Procesando G6 (multi-modelo)...")

    model_data = {}

    for model in G6_MODELS:
        model_base = base / model
        model_out  = out / model
        label      = G6_LABELS.get(model, model)

        print(f"\n  ── Modelo: {label}")

        cpu_df = load_runs(model_base / "CPU_runs.csv")
        gpu_df = load_runs(model_base / "GPU_runs.csv")
        model_data[model] = {"cpu": cpu_df, "gpu": gpu_df}

        title_base = f"G6 / {label}"

        # Speedup bars por modelo
        if cpu_df is not None and gpu_df is not None:
            plot_speedup_bars(
                cpu_df, gpu_df,
                model_out / "speedup_bars.png",
                f"Speedup GPU/CPU — {title_base}"
            )
        else:
            print(f"    [INFO] Speedup omitido para {model}: faltan CPU o GPU.")

        # Series temporales
        if cpu_df is not None:
            plot_time_series(cpu_df, "CPU",
                             model_out / "cpu_time_series.png",
                             f"Path Loss — {title_base} — CPU")
        if gpu_df is not None:
            plot_time_series(gpu_df, "GPU",
                             model_out / "gpu_time_series.png",
                             f"Path Loss — {title_base} — GPU")

        # Boxplot comparativo
        if cpu_df is not None or gpu_df is not None:
            plot_boxplot_comparison(cpu_df, gpu_df,
                                    model_out / "boxplot_pathloss.png",
                                    f"Distribución pathloss_s — G6 / {label}")

    # Figura comparativa de los 4 modelos
    print(f"\n  ── Figura comparativa todos los modelos")
    plot_g6_all_models(model_data, out / "speedup_bars_all_models.png")

    if show:
        plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Analiza y visualiza resultados del benchmark GPU/CPU."
    )
    parser.add_argument(
        "--scenarios", nargs="+",
        default=["G1", "G2", "G3", "G4", "G5", "G6"],
        choices=["G1", "G2", "G3", "G4", "G5", "G6"],
        help="Escenarios a procesar (default: todos)."
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Mostrar figuras interactivamente ademas de guardarlas."
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.show:
        matplotlib.use("TkAgg")  # ventana interactiva
        plt.ion()

    print(f"\n{'═'*60}")
    print(f"  analyze_gpu_benchmark.py")
    print(f"  Escenarios : {' '.join(args.scenarios)}")
    print(f"  Salida     : {OUT_DIR.relative_to(ROOT_DIR)}")
    print(f"{'═'*60}")

    for sid in args.scenarios:
        if sid == "G6":
            process_g6(args.show)
        else:
            process_scenario(sid, args.show)

    print(f"\n{'═'*60}")
    print(f"  Completado. Figuras en: {OUT_DIR.relative_to(ROOT_DIR)}")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
