# Sistema de Logging: Documentación Técnica

**Archivo fuente:** `src/utils/logger.py`
**Función de inicialización:** `setup_logger()`
**Versión:** 2026-05-09

---

## 1. Descripción General

El sistema de logging registra eventos, advertencias y errores en tiempo de ejecución. Se basa íntegramente en el módulo estándar `logging` de Python, configurado una sola vez al arranque mediante `setup_logger()` y usado por **18 clases** a lo largo de todo el sistema.

### 1.1 Alcance

| Capa | Módulos con logger |
|------|-------------------|
| Entrada/Main | `main.py` |
| UI | `MainWindow`, `MapWidget`, `ProjectPanel`, `AntennaPropertiesDialog`, `SettingsDialog` |
| Core | `CoverageCalculator`, `AntennaManager`, `SiteManager`, `ProjectManager`, `TerrainLoader` |
| Workers | `SimulationWorker` |
| Modelos | `FreeSpaceModel`, `OkumuraHataModel`, `models.COST-231`, `models.ITU-R P.1546` |
| Utils | `ConfigManager`, `ExportManager`, `HeatmapGenerator` |

---

## 2. Inicialización — `setup_logger()`

**Ubicación:** `src/utils/logger.py`

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

def setup_logger(log_dir: str = "logs", level=logging.INFO):
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Archivo con fecha: logs/app_YYYYMMDD.log
    log_file = log_path / f"app_{datetime.now().strftime('%Y%m%d')}.log"

    # Formato: 2026-05-09 14:32:01 - SimulationWorker - INFO - mensaje
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler rotativo: máximo 10 MB por archivo, 5 backups
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Handler consola (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Logger raíz — todos los loggers del sistema heredan de este
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger
```

### 2.1 Punto de Invocación

`setup_logger()` se llama **una sola vez**, en la primera línea ejecutable de `main.py`, antes de instanciar cualquier componente:

```python
# src/main.py
def main():
    QApplication.setAttribute(...)       # Qt primero
    from utils.logger import setup_logger
    setup_logger()                       # logging segundo — antes de todo
    logging.info("RF Coverage Tool - Starting")
    ...
```

Este orden garantiza que cualquier excepción durante la inicialización de Qt, GPU, o modelos quede registrada.

---

## 3. Jerarquía de Loggers

Python `logging` usa una jerarquía de nombres separados por puntos. El **logger raíz** (`""`) configurado en `setup_logger()` actúa como padre de todos.

```
root  ("")                  ← setup_logger() lo configura
├── MainWindow
├── MapWidget
├── ProjectPanel
├── AntennaPropertiesDialog
├── SettingsDialog
├── CoverageCalculator
├── AntennaManager
├── SiteManager
├── ProjectManager
├── TerrainLoader
├── SimulationWorker
├── ConfigManager
├── ExportManager
├── HeatmapGenerator
├── FreeSpaceModel
├── OkumuraHataModel
└── models              ← prefijo compartido
    ├── models.COST-231 Walfisch-Ikegami
    └── models.ITU-R P.1546
```

Los loggers de **modelos de propagación** usan el prefijo `models.` definido en `base_model.py`:

```python
# src/core/models/base_model.py
class PropagationModel(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.logger = logging.getLogger(f"models.{name}")
```

Los demás módulos usan nombres planos:

```python
# Patrón uniforme en todos los módulos
self.logger = logging.getLogger("NombreClase")
```

---

## 4. Niveles de Log Usados

El sistema usa 4 de los 5 niveles estándar de Python:

| Nivel | Valor numérico | Uso en el sistema |
|-------|---------------|-------------------|
| `DEBUG` | 10 | Detalles internos de cálculo (solo en desarrollo) |
| `INFO` | 20 | Eventos normales del ciclo de vida |
| `WARNING` | 30 | Situaciones degradadas pero recuperables |
| `ERROR` | 40 | Fallos que se manejan con fallback |
| `CRITICAL` | 50 | No usado actualmente |

El nivel por defecto es `logging.INFO` — los mensajes `DEBUG` no se escriben en producción.

### 4.1 Ejemplos por Nivel

**DEBUG** — cálculos internos, solo visibles si se baja el nivel:
```python
# SimulationWorker
self.logger.debug(f"Using frequency override: {frequency_override_mhz} MHz")
self.logger.debug(f"3GPP config: scenario={base_model_params['scenario']}")
self.logger.debug(f"TX elevation for {antenna.name}: {tx_elevation:.1f}m")
self.logger.debug(f"Antenna {antenna.name} calculated in {antenna_time:.3f}s")

# MainWindow
self.logger.debug("No default terrain file found at data/terrain/cuenca_terrain.tif")
```

**INFO** — eventos normales del flujo principal:
```python
# main.py
logging.info("RF Coverage Tool - Starting")

# SimulationWorker
self.logger.info(f"Starting simulation for {len(self.antennas)} antennas on {'GPU' if gpu_used else 'CPU'}")
self.logger.info(f"Global grid created: {grid_lats.shape} points")
self.logger.info(f"Using propagation model: {model_name}")
self.logger.info(f"Okumura-Hata config: {okumura_config}")
self.logger.info("Computing aggregated coverage for multi-antenna deployment")
self.logger.info(f"Simulation completed in {total_time:.2f}s")

# AntennaManager
self.logger.info(f"Antenna added: {antenna.name} ({antenna.id})")
self.logger.info(f"Antenna removed: {antenna_id}")
self.logger.info(f"Antenna updated: {antenna_id}")

# MainWindow
self.logger.info(f"Project saved: {filepath}")
self.logger.info(f"Project loaded: {filename}")
self.logger.info(f"Compute mode updated: {mode}")
```

**WARNING** — degradación sin fallo crítico:
```python
# ConfigManager (archivo de config no encontrado → usa defaults)
self.logger.warning(f"Config file not found, using defaults: {path}")

# SimulationWorker (terreno no disponible → usa terreno plano)
self.logger.warning("No terrain file found at data/terrain/cuenca_terrain.tif, using flat terrain")
self.logger.warning("Default terrain file validation failed")

# Modelos de propagación (parámetros fuera de rango)
self.logger.warning(f"Frequency {frequency} MHz outside valid range (800-2000 MHz)")
self.logger.warning(f"TX height {tx_height}m outside valid range (30-200m)")

# SimulationWorker (modelo desconocido → Free Space)
self.logger.warning(f"Unknown model '{model_name}', using Free Space")
```

**ERROR** — fallo manejado con try/except + fallback:
```python
# ConfigManager
self.logger.error(f"Invalid JSON in {path}: {e}. Using defaults.")
self.logger.error(f"Error reading {path}: {e}. Using defaults.")
self.logger.error(f"Invalid config format in {path}: root must be an object. Using defaults.")

# MainWindow
self.logger.error(f"Error loading project: {e}")
self.logger.error(f"Error saving project: {e}")
self.logger.error(f"Export error: {e}", exc_info=True)

# SimulationWorker
self.logger.error(f"Simulation error: {e}", exc_info=True)
```

---

## 5. Stack Traces con `exc_info=True`

Cuando un error es crítico para el diagnóstico, se pasa `exc_info=True` para incluir el stack trace completo en el log:

```python
# SimulationWorker — error en cálculo de simulación
self.logger.error(f"Simulation error: {e}", exc_info=True)

# MainWindow — error en exportación
self.logger.error(f"Export error: {e}", exc_info=True)
```

**Ejemplo de salida en el archivo de log:**
```
2026-05-09 14:35:22 - SimulationWorker - ERROR - Simulation error: division by zero
Traceback (most recent call last):
  File ".../simulation_worker.py", line 150, in run
    result = model.calculate_path_loss(...)
  File ".../free_space.py", line 45, in calculate_path_loss
    ...
ZeroDivisionError: division by zero
```

---

## 6. Formato de los Mensajes

Todos los mensajes siguen el formato definido en `setup_logger()`:

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Ejemplo real de una sesión de simulación:**
```
2026-05-09 14:32:01 - root - INFO - ==================================================
2026-05-09 14:32:01 - root - INFO - RF Coverage Tool - Starting
2026-05-09 14:32:01 - root - INFO - ==================================================
2026-05-09 14:32:02 - MainWindow - INFO - MainWindow initialized
2026-05-09 14:32:02 - MainWindow - INFO - Managers initialized
2026-05-09 14:32:03 - TerrainLoader - INFO - Loaded terrain: 2400×1800 px
2026-05-09 14:34:11 - SimulationWorker - INFO - Starting simulation for 3 antennas on GPU
2026-05-09 14:34:11 - SimulationWorker - INFO - Global grid created: (100, 100) points
2026-05-09 14:34:11 - SimulationWorker - INFO - Using propagation model: Okumura-Hata
2026-05-09 14:34:11 - SimulationWorker - DEBUG - TX elevation for Antena_1: 2541.3m
2026-05-09 14:34:12 - SimulationWorker - INFO - Computing aggregated coverage for multi-antenna deployment
2026-05-09 14:34:12 - SimulationWorker - INFO - Simulation completed in 1.23s
```

| Campo | Descripción |
|-------|-------------|
| `asctime` | Fecha y hora: `YYYY-MM-DD HH:MM:SS` |
| `name` | Nombre del logger (clase que emitió el mensaje) |
| `levelname` | Nivel: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `message` | Texto libre del mensaje |

---

## 7. Archivos de Log

### 7.1 Ubicación y Rotación

Los archivos se generan en `logs/` con nombre `app_YYYYMMDD.log`:

```
logs/
├── app_20251103.log
├── app_20260205.log
├── app_20260318.log
├── app_20260326.log
├── app_20260331.log
├── app_20260413.log
├── app_20260415.log
├── app_20260418.log
├── app_20260419.log
├── app_20260428.log
├── app_20260429.log
├── app_20260430.log
├── app_20260502.log
├── app_20260505.log
└── app_20260509.log   ← hoy
```

El `RotatingFileHandler` aplica rotación automática:
- **Tamaño máximo:** 10 MB por archivo
- **Backups:** 5 archivos adicionales antes de descartar (`app_20260509.log.1`, `.2`, ...)
- **Encoding:** UTF-8 (soporta tildes y caracteres especiales)

### 7.2 Doble Destino

Cada mensaje se escribe **simultáneamente** en dos destinos:

```
log message
    ├──► RotatingFileHandler → logs/app_YYYYMMDD.log
    └──► StreamHandler       → consola (stdout)
```

Esto permite:
- **Desarrollo:** ver mensajes en terminal en tiempo real
- **Producción:** revisar logs persistentes post-mortem

---

## 8. Patrón de Uso en los Módulos

Todos los módulos siguen el mismo patrón de dos líneas:

```python
import logging

class MiClase:
    def __init__(self, ...):
        # 1. Obtener logger con nombre de la clase
        self.logger = logging.getLogger("MiClase")

    def alguna_operacion(self):
        # 2. Usar self.logger con el nivel apropiado
        self.logger.info("Operación iniciada")
        self.logger.debug(f"Detalle interno: {valor}")
        self.logger.warning("Parámetro fuera de rango")
        self.logger.error(f"Fallo: {e}", exc_info=True)
```

`logging.getLogger("MiClase")` **no crea un logger nuevo** si ya existe uno con ese nombre — devuelve la instancia existente. Esto es seguro en entornos multithreaded (como `SimulationWorker` que corre en un `QThread`).

---

## 9. Módulos y sus Nombres de Logger

| Módulo | Nombre del logger | Archivo |
|--------|------------------|---------|
| `main.py` | `root` (logging directo) | `src/main.py` |
| `MainWindow` | `"MainWindow"` | `src/ui/main_window.py` |
| `MapWidget` | `"MapWidget"` | `src/ui/widgets/map_widget.py` |
| `ProjectPanel` | `"ProjectPanel"` | `src/ui/panels/project_panel.py` |
| `AntennaPropertiesDialog` | `"AntennaPropertiesDialog"` | `src/ui/dialogs/antenna_properties_dialog.py` |
| `SettingsDialog` | `"SettingsDialog"` | `src/ui/dialogs/settings_dialog.py` |
| `CoverageCalculator` | `"CoverageCalculator"` | `src/core/coverage_calculator.py` |
| `AntennaManager` | `"AntennaManager"` | `src/core/antenna_manager.py` |
| `SiteManager` | `"SiteManager"` | `src/core/site_manager.py` |
| `ProjectManager` | `"ProjectManager"` | `src/core/project_manager.py` |
| `TerrainLoader` | `"TerrainLoader"` | `src/core/terrain_loader.py` |
| `SimulationWorker` | `"SimulationWorker"` | `src/workers/simulation_worker.py` |
| `ConfigManager` | `"ConfigManager"` | `src/utils/config_manager.py` |
| `ExportManager` | `"ExportManager"` | `src/utils/export_manager.py` |
| `HeatmapGenerator` | `"HeatmapGenerator"` | `src/utils/heatmap_generator.py` |
| `FreeSpacePathLossModel` | `"FreeSpaceModel"` | `src/core/models/traditional/free_space.py` |
| `OkumuraHataModel` | `"OkumuraHataModel"` | `src/core/models/traditional/okumura_hata.py` |
| `COST231WalfischIkegamiModel` | `"models.COST-231 Walfisch-Ikegami"` | `src/core/models/traditional/cost231.py` |
| `ITUR_P1546Model` | `"models.ITU-R P.1546"` | `src/core/models/traditional/itu_r_p1546.py` |

---

## 10. Integración con el Pipeline de Simulación

El flujo de simulación genera una secuencia de mensajes predecible que sirve para auditar ejecuciones:

```
INFO  SimulationWorker  Starting simulation for N antennas on GPU/CPU
INFO  SimulationWorker  Creating global simulation grid...
INFO  SimulationWorker  Global grid created: (100, 100) points
INFO  SimulationWorker  Using propagation model: <nombre>
INFO  SimulationWorker  <Modelo> config: {...}
  (para cada antena):
DEBUG SimulationWorker  TX elevation for <antena>: <X>m
DEBUG SimulationWorker  3GPP config: scenario=..., h_bs=..., h_ue=...   [si 3GPP]
DEBUG SimulationWorker  Antenna <nombre> calculated in <t>s
  (si multi-antena):
INFO  SimulationWorker  Computing aggregated coverage for multi-antenna deployment
INFO  SimulationWorker  Aggregated coverage generated successfully
INFO  SimulationWorker  Simulation completed in <total>s
```

En caso de error:
```
ERROR SimulationWorker  Simulation error: <mensaje>
      <stack trace completo por exc_info=True>
```

---

## 11. Cómo Filtrar los Logs

Para analizar los archivos de log desde terminal (Windows PowerShell):

```powershell
# Ver solo errores
Select-String "ERROR" logs\app_20260509.log

# Ver todo lo de SimulationWorker
Select-String "SimulationWorker" logs\app_20260509.log

# Ver mensajes de modelos de propagación
Select-String "models\." logs\app_20260509.log

# Ver tiempo de simulaciones completadas
Select-String "Simulation completed" logs\app_20260509.log
```

---

## 12. Cambiar el Nivel de Log (Desarrollo)

Para activar mensajes `DEBUG` durante desarrollo, modificar la llamada en `main.py`:

```python
# src/main.py — cambio temporal para desarrollo
setup_logger(level=logging.DEBUG)
# Ahora se verán mensajes como:
# DEBUG SimulationWorker - TX elevation for Antena_1: 2541.3m
# DEBUG SimulationWorker - Antenna Antena_1 calculated in 0.043s
# DEBUG SimulationWorker - 3GPP config: scenario=UMa, h_bs=25, h_ue=1.5
```

---

**Ver también:**
- [04_PIPELINE_SIMULACION.md](04_PIPELINE_SIMULACION.md) — contexto de cuándo se emiten los mensajes de simulación
- [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md) — workers y threading donde corre `SimulationWorker`
