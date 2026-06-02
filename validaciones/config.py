from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

ATOLL_TXT_PATH = ROOT_DIR / "Atoll" / "A4.txt"
RF_CSV_PATH = ROOT_DIR / "data" / "exports" / "validacion" / "A4.csv"
OUTPUT_DIR = ROOT_DIR / "validaciones" / "resultados" / "A4"

WORK_CRS = "EPSG:4326"
SOURCE_CRS = "EPSG:4326"
#SOURCE_CRS = "EPSG:32717"  # Asumimos que los datos ya están en UTM para evitar reproyecciones
MATCH_TOLERANCE_M = 10.0
DISTANCE_STRICT_THRESHOLD_M = 20.0
TOLERANCE_SWEEP_LIST = [10.0, 20.0, 30.0, 35.0, 40.0, 50.0]
USE_MUTUAL_MATCH_FILTER = True
ERROR_CMAP_LIMIT_DB = 20.0
