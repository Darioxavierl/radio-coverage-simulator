"""
benchmark_gpu.py — Benchmarking headless CPU vs GPU para escenarios G1-G6.

Reutiliza exactamente el mismo SimulationWorker, ComputeEngine y CoverageCalculator
que usa la GUI, sin modificar ningun archivo existente del proyecto.

Uso rapido:
    .env/Scripts/python.exe benchmark_gpu.py
    .env/Scripts/python.exe benchmark_gpu.py --n-runs 10 --scenarios G1 G2 G3
    .env/Scripts/python.exe benchmark_gpu.py --scenarios G4 G5 G6 --n-runs 5
    .env/Scripts/python.exe benchmark_gpu.py --n-runs 5 --skip-gpu
    .env/Scripts/python.exe benchmark_gpu.py --help

Requisitos G4/G5:
    Crear los proyectos en la GUI antes de ejecutar:
      data/projects/Validaciones/G4.rfproj  (5 antenas direccionales)
      data/projects/Validaciones/G5.rfproj  (9 antenas direccionales)
    G6 reutiliza el rfproj de G4 (misma topologia, 4 modelos distintos).
    Si el .rfproj no existe, el escenario se salta con aviso (no aborta).

Salida:
    data/exports/validacion/GPU/G1/CPU_runs.csv
    data/exports/validacion/GPU/G1/GPU_runs.csv
    data/exports/validacion/GPU/G1/summary.csv
    ...
    data/exports/validacion/GPU/G6/
        okumura_hata/CPU_runs.csv, GPU_runs.csv, summary.csv
        cost231_hata/...
        itu_p1546/...
        three_gpp_38901/...
        summary_all_models.csv
"""

import sys
import logging
import argparse
import csv
import time
from pathlib import Path
from datetime import datetime

# Forzar UTF-8 en stdout/stderr para compatibilidad con Windows (cp1252 no soporta box chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── mismo sys.path que run.py ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

# ── Qt sin ventana (requerido por QObject/QCoreApplication) ───────────────────
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)   # QCoreApplication no alcanza para algunos signals Qt6

# ── imports del proyecto (ya con src en path) ─────────────────────────────────
from models.project import Project
from core.compute_engine import ComputeEngine
from core.coverage_calculator import CoverageCalculator
from core.terrain_loader import TerrainLoader
from workers.simulation_worker import SimulationWorker

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACION DE ESCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

_BASE_CONFIG = {
    "model":        "cost231_hata",
    "environment":  "Urban",
    "city_type":    "medium",
    "mobile_height": 1.5,
}

_G123_RFPROJ = str(ROOT_DIR / "data" / "projects" / "Validaciones" / "G1-2-3.rfproj")
_G4_RFPROJ   = str(ROOT_DIR / "data" / "projects" / "Validaciones" / "G4.rfproj")
_G5_RFPROJ   = str(ROOT_DIR / "data" / "projects" / "Validaciones" / "G5.rfproj")

SCENARIO_CONFIGS = {
    "G1": {**_BASE_CONFIG, "resolution": 200, "radius_km": 4, "n_antennas": 1,
           "rfproj": _G123_RFPROJ,
           "description": "Monocelda baja carga (40,000 pts)"},
    "G2": {**_BASE_CONFIG, "resolution": 350, "radius_km": 5, "n_antennas": 1,
           "rfproj": _G123_RFPROJ,
           "description": "Monocelda media carga (122,500 pts)"},
    "G3": {**_BASE_CONFIG, "resolution": 500, "radius_km": 5, "n_antennas": 1,
           "rfproj": _G123_RFPROJ,
           "description": "Monocelda alta carga / maximo programa (250,000 pts)"},
    "G4": {**_BASE_CONFIG, "resolution": 300, "radius_km": 5, "n_antennas": 5,
           "rfproj": _G4_RFPROJ,
           "description": "Multiantena 5 celdas (90,000 pts)"},
    "G5": {**_BASE_CONFIG, "resolution": 300, "radius_km": 5, "n_antennas": 9,
           "rfproj": _G5_RFPROJ,
           "description": "Multiantena 9 celdas / estres (90,000 pts)"},
    "G6": {"resolution": 300, "radius_km": 5, "n_antennas": 5,
           "rfproj": _G4_RFPROJ,   # misma topologia que G4
           "model": None,           # multi-modelo: ver G6_MODEL_CONFIGS
           "description": "Impacto del modelo de propagacion (5 antenas, 4 modelos)"},
}

# Configuracion de cada modelo para G6 (parametros exactos del worker)
G6_MODEL_CONFIGS = {
    "okumura_hata": {
        "model":         "okumura_hata",
        "environment":   "Urban",
        "city_type":     "medium",
        "mobile_height": 1.5,
    },
    "cost231_hata": {
        "model":         "cost231_hata",
        "environment":   "Urban",
        "city_type":     "medium",
        "mobile_height": 1.5,
    },
    "itu_p1546": {
        "model":         "itu_p1546",
        "environment":   "Urban",
        "terrain_type":  "mixed",
        "clutter_model": "p2108",
    },
    "three_gpp_38901": {
        "model":    "three_gpp_38901",
        "scenario": "UMa",
        "h_bs":     25.0,
        "h_ue":     1.5,
        "use_dem":  False,
    },
}

DEFAULT_TERRAIN = str(ROOT_DIR / "data" / "terrain" / "cuenca_terrain.tif")
OUTPUT_BASE = ROOT_DIR / "data" / "exports" / "validacion" / "GPU"

# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.WARNING,          # silenciar logs internos del worker
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("benchmark_gpu")
log.setLevel(logging.DEBUG)

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def load_antennas(rfproj_path: str) -> list:
    """Carga la lista de antenas desde un archivo .rfproj."""
    project = Project.load_from_file(rfproj_path)
    antennas = list(project.antennas.values())
    log.info(f"Cargadas {len(antennas)} antena(s) desde {rfproj_path}")
    return antennas


def build_stack(use_gpu: bool):
    """
    Construye ComputeEngine + CoverageCalculator para el modo indicado.
    Se llama UNA vez por modo (no por run) para no medir el overhead de init.
    Silencia loggers de modelos a ERROR para que los guards isEnabledFor(WARNING/DEBUG)
    retornen False y no se ejecuten las conversiones D2H de logging.
    """
    engine = ComputeEngine(use_gpu=use_gpu)
    calculator = CoverageCalculator(engine)

    # Suprimir warnings/info de modelos durante benchmark — evita D2H syncs por logging
    for _logger_name in (
        "COST231HataModel", "OkumuraHataModel", "ThreeGPP38901Model",
        "ITURp1546Model", "CoverageCalculator", "SimulationWorker", "TerrainLoader",
        "LOSCalculator",
    ):
        logging.getLogger(_logger_name).setLevel(logging.ERROR)

    return engine, calculator


def build_terrain(terrain_file: str):
    """
    Carga TerrainLoader UNA vez por modo y lo reutiliza entre runs,
    exactamente igual que hace la GUI.
    """
    t = TerrainLoader(terrain_file)
    if not t.is_loaded():
        log.warning(f"TerrainLoader no pudo cargar {terrain_file} — se usara terreno plano")
        return None
    stats = t.get_stats()
    log.info(f"Terreno cargado: elevacion {stats['min']:.0f}-{stats['max']:.0f} m")
    return t


def _extract_timings(metadata: dict) -> dict:
    """
    Extrae las metricas de tiempo del results['metadata'] emitido por SimulationWorker.
    Devuelve siempre las mismas claves (con 0.0 si faltan) para uniformidad en CSV.
    """
    cov_times = metadata.get("antenna_coverage_times_seconds", {})
    ren_times = metadata.get("antenna_render_times_seconds", {})
    pl_times  = metadata.get("antenna_pathloss_times_seconds", {})

    # suma de todas las antenas (G1-G3 tienen 1 antena; por robustez se suma todo)
    coverage_s  = sum(cov_times.values()) if cov_times else 0.0
    render_s    = sum(ren_times.values()) if ren_times else 0.0
    pathloss_s  = sum(pl_times.values())  if pl_times  else 0.0

    return {
        "coverage_s":    round(coverage_s, 4),
        "pathloss_s":    round(pathloss_s, 4),
        "render_s":      round(render_s, 4),
        "terrain_s":     round(metadata.get("terrain_loading_time_seconds", 0.0), 4),
        "aggregation_s": round(metadata.get("multi_antenna_aggregation_time_seconds", 0.0), 4),
        "total_s":       round(metadata.get("total_execution_time_seconds", 0.0), 4),
        "gpu_used":      metadata.get("gpu_used", False),
        "gpu_device":    metadata.get("gpu_device", "unknown"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# EJECUCION DE UN SOLO RUN
# ══════════════════════════════════════════════════════════════════════════════

def run_single(antennas, calculator, terrain, config: dict) -> dict:
    """
    Instancia SimulationWorker y llama run() directamente (sincrono).
    Captura el resultado via slot conectado a finished.
    Retorna el dict de timings o lanza RuntimeError si hubo error.
    """
    result_holder = {}

    def on_finished(results: dict):
        result_holder["timings"] = _extract_timings(results["metadata"])

    def on_error(msg: str):
        result_holder["error"] = msg

    worker = SimulationWorker(
        antennas=antennas,
        coverage_calculator=calculator,
        terrain_data=terrain,
        config=config,
    )
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    # run() es sincrono — bloquea hasta completar y emite finished o error
    worker.run()

    if "error" in result_holder:
        raise RuntimeError(f"SimulationWorker error: {result_holder['error']}")

    return result_holder["timings"]


# ══════════════════════════════════════════════════════════════════════════════
# LOOP DE BENCHMARK POR ESCENARIO/MODO
# ══════════════════════════════════════════════════════════════════════════════

def run_benchmark_mode(scenario_id: str, config: dict, antennas: list,
                       use_gpu: bool, n_runs: int, n_warmup: int = 1,
                       n_antennas: int = 1, model_label: str = "") -> list:
    """
    Ejecuta n_warmup + n_runs simulaciones para un escenario/modo.
    Retorna lista de dicts (uno por run, incluyendo warmup marcado).
    """
    mode_label = "GPU" if use_gpu else "CPU"
    log.info(f"=== {scenario_id} | {mode_label} | {n_warmup} warmup + {n_runs} runs ===")

    _, calculator = build_stack(use_gpu)
    terrain = build_terrain(DEFAULT_TERRAIN)

    all_runs = []
    total_iters = n_warmup + n_runs

    for i in range(total_iters):
        is_warmup = i < n_warmup
        run_label = "warmup" if is_warmup else f"run {i - n_warmup + 1}/{n_runs}"

        try:
            t_wall = time.perf_counter()
            timings = run_single(antennas, calculator, terrain, config)
            wall_s = round(time.perf_counter() - t_wall, 4)

            row = {
                "run_id":        i,
                "is_warmup":     is_warmup,
                "timestamp":     datetime.now().isoformat(timespec="seconds"),
                **timings,
                "wall_s":        wall_s,
                "n_antennas":    n_antennas,
                "model_label":   model_label or config.get("model", ""),
            }
            all_runs.append(row)

            status = "WARMUP" if is_warmup else "OK"
            print(
                f"  [{scenario_id} | {mode_label} | {run_label}]  "
                f"coverage={timings['coverage_s']:.3f}s  "
                f"pathloss={timings['pathloss_s']:.3f}s  "
                f"render={timings['render_s']:.3f}s  "
                f"total={timings['total_s']:.3f}s  [{status}]"
            )

        except RuntimeError as exc:
            print(f"  [{scenario_id} | {mode_label} | {run_label}]  ERROR: {exc}")
            log.error(str(exc))

    return all_runs


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTACION CSV
# ══════════════════════════════════════════════════════════════════════════════

_RUNS_FIELDS = [
    "run_id", "is_warmup", "timestamp",
    "coverage_s", "pathloss_s", "render_s", "terrain_s", "aggregation_s", "total_s",
    "wall_s", "n_antennas", "model_label", "gpu_used", "gpu_device",
]


def save_runs_csv(runs: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_RUNS_FIELDS)
        writer.writeheader()
        writer.writerows(runs)
    log.info(f"Guardado: {path}")


def _median(values: list) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def _mean(values: list) -> float:
    return sum(values) / len(values) if values else float("nan")


def _std(values: list) -> float:
    if len(values) < 2:
        return float("nan")
    m = _mean(values)
    return (sum((x - m) ** 2 for x in values) / (len(values) - 1)) ** 0.5


def save_summary_csv(cpu_runs: list, gpu_runs: list, path: Path) -> None:
    """
    Genera summary.csv con estadisticas por metrica y speedup CPU/GPU.
    Solo usa runs donde is_warmup=False.
    """
    def meas(runs): return [r for r in runs if not r["is_warmup"]]

    cpu_m = meas(cpu_runs)
    gpu_m = meas(gpu_runs)

    metrics = ["coverage_s", "pathloss_s", "render_s", "aggregation_s", "total_s"]
    rows = []

    for metric in metrics:
        cpu_vals = [r[metric] for r in cpu_m if r.get(metric) is not None]
        gpu_vals = [r[metric] for r in gpu_m if r.get(metric) is not None]

        cpu_med = _median(cpu_vals)
        gpu_med = _median(gpu_vals)
        cpu_mn  = _mean(cpu_vals)
        gpu_mn  = _mean(gpu_vals)
        cpu_sd  = _std(cpu_vals)
        gpu_sd  = _std(gpu_vals)

        def cv(sd, mn): return round(sd / mn * 100, 2) if mn and mn != 0 else float("nan")
        speedup = round(cpu_med / gpu_med, 4) if gpu_med and gpu_med != 0 else float("nan")

        rows.append({
            "metric":          metric,
            "cpu_median_s":    round(cpu_med, 4),
            "cpu_mean_s":      round(cpu_mn, 4),
            "cpu_std_s":       round(cpu_sd, 4),
            "cpu_cv_pct":      cv(cpu_sd, cpu_mn),
            "gpu_median_s":    round(gpu_med, 4),
            "gpu_mean_s":      round(gpu_mn, 4),
            "gpu_std_s":       round(gpu_sd, 4),
            "gpu_cv_pct":      cv(gpu_sd, gpu_mn),
            "speedup":         speedup,
            "n_cpu_runs":      len(cpu_vals),
            "n_gpu_runs":      len(gpu_vals),
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "metric",
        "cpu_median_s", "cpu_mean_s", "cpu_std_s", "cpu_cv_pct",
        "gpu_median_s", "gpu_mean_s", "gpu_std_s", "gpu_cv_pct",
        "speedup", "n_cpu_runs", "n_gpu_runs",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # Imprimir tabla resumen en consola
    print(f"\n{'─'*72}")
    print(f"  RESUMEN — {path.parent.name}")
    print(f"{'─'*72}")
    print(f"  {'Metrica':<18} {'CPU median':>12} {'GPU median':>12} {'Speedup':>10}")
    print(f"  {'─'*18} {'─'*12} {'─'*12} {'─'*10}")
    for r in rows:
        print(
            f"  {r['metric']:<18} "
            f"{r['cpu_median_s']:>11.3f}s "
            f"{r['gpu_median_s']:>11.3f}s "
            f"{r['speedup']:>9.3f}x"
        )
    print(f"{'─'*72}\n")

    log.info(f"Guardado: {path}")


def save_all_models_summary_csv(model_results: dict, path: Path) -> None:
    """
    Genera summary_all_models.csv con una fila por (modelo, metrica).
    model_results: {model_label: {"cpu": [runs], "gpu": [runs]}}
    """
    def meas(runs): return [r for r in runs if not r["is_warmup"]]

    metrics = ["coverage_s", "pathloss_s", "render_s", "aggregation_s", "total_s"]
    rows = []

    for model_label, mode_runs in model_results.items():
        cpu_m = meas(mode_runs.get("cpu", []))
        gpu_m = meas(mode_runs.get("gpu", []))
        for metric in metrics:
            cpu_vals = [r[metric] for r in cpu_m if r.get(metric) is not None]
            gpu_vals = [r[metric] for r in gpu_m if r.get(metric) is not None]
            cpu_med = _median(cpu_vals)
            gpu_med = _median(gpu_vals)
            speedup = round(cpu_med / gpu_med, 4) if gpu_med and gpu_med != 0 else float("nan")
            cpu_cv = round(_std(cpu_vals) / _mean(cpu_vals) * 100, 2) \
                     if cpu_vals and _mean(cpu_vals) != 0 else float("nan")
            gpu_cv = round(_std(gpu_vals) / _mean(gpu_vals) * 100, 2) \
                     if gpu_vals and _mean(gpu_vals) != 0 else float("nan")
            rows.append({
                "model_label":  model_label,
                "metric":       metric,
                "cpu_median_s": round(cpu_med, 4),
                "gpu_median_s": round(gpu_med, 4),
                "speedup":      speedup,
                "cpu_cv_pct":   cpu_cv,
                "gpu_cv_pct":   gpu_cv,
                "n_cpu_runs":   len(cpu_vals),
                "n_gpu_runs":   len(gpu_vals),
            })

    fields = ["model_label", "metric", "cpu_median_s", "gpu_median_s",
              "speedup", "cpu_cv_pct", "gpu_cv_pct", "n_cpu_runs", "n_gpu_runs"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # Tabla comparativa en consola
    print(f"\n{'─'*76}")
    print(f"  G6 RESUMEN COMPARATIVO DE MODELOS")
    print(f"{'─'*76}")
    print(f"  {'Modelo':<20} {'CPU cov':>10} {'GPU cov':>10} {'Spdup cov':>10} {'Spdup tot':>10}")
    print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")
    for label in model_results:
        cov_row = next((r for r in rows if r["model_label"] == label
                        and r["metric"] == "coverage_s"), {})
        tot_row = next((r for r in rows if r["model_label"] == label
                        and r["metric"] == "total_s"), {})
        print(
            f"  {label:<20}"
            f"  {cov_row.get('cpu_median_s', float('nan')):>8.3f}s"
            f"  {cov_row.get('gpu_median_s', float('nan')):>8.3f}s"
            f"  {cov_row.get('speedup', float('nan')):>8.3f}x"
            f"  {tot_row.get('speedup', float('nan')):>8.3f}x"
        )
    print(f"{'─'*76}\n")
    log.info(f"Guardado: {path}")


def run_g6(antennas: list, n_runs: int, skip_cpu: bool, skip_gpu: bool,
           out_dir: Path) -> None:
    """
    Orquesta el benchmark G6: itera sobre G6_MODEL_CONFIGS, ejecuta
    CPU+GPU para cada modelo y guarda CSV individuales + summary global.
    """
    base_sim_cfg = {"resolution": 300, "radius_km": 5}
    n_ant = len(antennas)
    model_results = {}   # {model_label: {"cpu": runs, "gpu": runs}}

    for model_label, model_cfg in G6_MODEL_CONFIGS.items():
        sim_cfg = {**model_cfg, **base_sim_cfg}
        model_dir = out_dir / model_label
        print(f"\n  [G6 | {model_label}]")

        cpu_runs, gpu_runs = [], []

        if not skip_cpu:
            cpu_runs = run_benchmark_mode(
                scenario_id="G6",
                config=sim_cfg,
                antennas=antennas,
                use_gpu=False,
                n_runs=n_runs,
                n_antennas=n_ant,
                model_label=model_label,
            )
            save_runs_csv(cpu_runs, model_dir / "CPU_runs.csv")

        if not skip_gpu:
            gpu_runs = run_benchmark_mode(
                scenario_id="G6",
                config=sim_cfg,
                antennas=antennas,
                use_gpu=True,
                n_runs=n_runs,
                n_antennas=n_ant,
                model_label=model_label,
            )
            save_runs_csv(gpu_runs, model_dir / "GPU_runs.csv")

        if cpu_runs and gpu_runs:
            save_summary_csv(cpu_runs, gpu_runs, model_dir / "summary.csv")
        elif cpu_runs:
            print(f"  (summary de {model_label} omitido: sin runs GPU)")
        elif gpu_runs:
            print(f"  (summary de {model_label} omitido: sin runs CPU)")

        model_results[model_label] = {"cpu": cpu_runs, "gpu": gpu_runs}

    save_all_models_summary_csv(model_results, out_dir / "summary_all_models.csv")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark headless CPU vs GPU — Escenarios G1-G6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--n-runs", type=int, default=10,
        help="Numero de runs de medicion por escenario/modo (default: 10)",
    )
    parser.add_argument(
        "--scenarios", nargs="+", default=["G1", "G2", "G3"],
        choices=list(SCENARIO_CONFIGS.keys()),
        help="Escenarios a ejecutar (default: G1 G2 G3). G4/G5/G6 requieren rfproj creado en GUI.",
    )
    parser.add_argument(
        "--rfproj-g4", default=None, metavar="PATH",
        help="Override de ruta .rfproj para G4 (default: segun SCENARIO_CONFIGS)",
    )
    parser.add_argument(
        "--rfproj-g5", default=None, metavar="PATH",
        help="Override de ruta .rfproj para G5 (default: segun SCENARIO_CONFIGS)",
    )
    parser.add_argument(
        "--rfproj-g6", default=None, metavar="PATH",
        help="Override de ruta .rfproj para G6 (default: igual que G4)",
    )
    parser.add_argument("--skip-cpu", action="store_true", help="Omitir ejecuciones en CPU")
    parser.add_argument("--skip-gpu", action="store_true", help="Omitir ejecuciones en GPU")
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"\n{'═'*72}")
    print(f"  benchmark_gpu.py — RF Coverage Tool")
    print(f"  Escenarios : {' '.join(args.scenarios)}")
    print(f"  Runs       : {args.n_runs} medicion + 1 warmup (por escenario/modo)")
    print(f"  CPU        : {'omitido' if args.skip_cpu else 'SI'}")
    print(f"  GPU        : {'omitido' if args.skip_gpu else 'SI'}")
    print(f"{'═'*72}\n")

    # rfproj overrides por escenario
    rfproj_overrides = {"G4": args.rfproj_g4, "G5": args.rfproj_g5, "G6": args.rfproj_g6}

    for scenario_id in args.scenarios:
        cfg = SCENARIO_CONFIGS[scenario_id]
        pts = cfg["resolution"] ** 2

        # Resolver ruta rfproj: CLI override > default del escenario
        rfproj_path = rfproj_overrides.get(scenario_id) or cfg["rfproj"]

        # Verificar existencia antes de arrancar
        if not Path(rfproj_path).exists():
            print(f"\n  AVISO [{scenario_id}]: rfproj no encontrado — saltando.")
            print(f"           Ruta esperada: {rfproj_path}")
            print(f"           Crea el proyecto en la GUI y vuelve a ejecutar.\n")
            continue

        antennas = load_antennas(rfproj_path)
        if not antennas:
            print(f"\n  AVISO [{scenario_id}]: el proyecto no tiene antenas — saltando.\n")
            continue

        n_ant = len(antennas)
        print(f"\n{'━'*72}")
        print(f"  Escenario {scenario_id}: {cfg['description']}")
        print(f"  resolution={cfg['resolution']}  radius_km={cfg['radius_km']}  puntos={pts:,}  antenas={n_ant}")
        print(f"  rfproj: {rfproj_path}")
        print(f"{'━'*72}")

        out_dir = OUTPUT_BASE / scenario_id

        # G6: flujo especial multi-modelo
        if scenario_id == "G6":
            run_g6(antennas=antennas, n_runs=args.n_runs,
                   skip_cpu=args.skip_cpu, skip_gpu=args.skip_gpu,
                   out_dir=out_dir)
            continue

        cpu_runs = []
        gpu_runs = []

        if not args.skip_cpu:
            cpu_runs = run_benchmark_mode(
                scenario_id=scenario_id,
                config=cfg,
                antennas=antennas,
                use_gpu=False,
                n_runs=args.n_runs,
                n_antennas=n_ant,
            )
            save_runs_csv(cpu_runs, out_dir / "CPU_runs.csv")

        if not args.skip_gpu:
            gpu_runs = run_benchmark_mode(
                scenario_id=scenario_id,
                config=cfg,
                antennas=antennas,
                use_gpu=True,
                n_runs=args.n_runs,
                n_antennas=n_ant,
            )
            save_runs_csv(gpu_runs, out_dir / "GPU_runs.csv")

        if cpu_runs and gpu_runs:
            save_summary_csv(cpu_runs, gpu_runs, out_dir / "summary.csv")
        elif cpu_runs:
            print("  (summary omitido — no hay runs GPU para comparar)")
        elif gpu_runs:
            print("  (summary omitido — no hay runs CPU para comparar)")

    print(f"\n{'═'*72}")
    print(f"  Benchmark completado. Resultados en: {OUTPUT_BASE}")
    print(f"{'═'*72}\n")


if __name__ == "__main__":
    main()
