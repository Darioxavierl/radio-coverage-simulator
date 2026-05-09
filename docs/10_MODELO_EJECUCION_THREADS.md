# Modelo de Ejecución y Threading

**Versión:** 2026-05-08

## 1. Propósito

La aplicación utiliza un modelo threading multihilo para separar la ejecución de cálculos pesados (simulación) del hilo principal de la GUI. Esto mantiene la interfaz responsiva mientras las operaciones numéricas se ejecutan en background. Este documento describe la arquitectura de threading y las señales de comunicación.

## 2. Problema: GUI Bloqueada

### 2.1 Escenario Problemático (Sin Threading)

```
MainThread (GUI)
┌──────────────────────────────────────────────────┐
│ Usuario hace clic "Simular"                      │
├──────────────────────────────────────────────────┤
│ 1. Iniciar simulación (inmediato) ✅             │
├──────────────────────────────────────────────────┤
│ 2. Calcular cobertura [BLOQUEADO 5 segundos] ❌  │
├──────────────────────────────────────────────────┤
│ 3. GUI no responde a clicks, mouse, etc.         │
├──────────────────────────────────────────────────┤
│ 4. S.O. marca aplicación como "No responde"      │
├──────────────────────────────────────────────────┤
│ 5. Finalizar simulación (inmediato)              │
├──────────────────────────────────────────────────┤
│ 6. Mostrar resultados y reactivar GUI ✅         │
└──────────────────────────────────────────────────┘
```

**Resultado**: Experiencia de usuario mala, sensación de "cuelgue"

### 2.2 Solución: Worker en QThread Separado

```
MainThread (GUI)                WorkerThread (Cálculo)
┌──────────────────┐            ┌────────────────────────┐
│ Usuario hace      │            │                        │
│ clic "Simular"    │            │                        │
└────────┬──────────┘            │                        │
         │                       │                        │
         ↓ lanzar worker         │                        │
┌──────────────────┐            │                        │
│ GUI activa       │            ↓ iniciar cálculo        │
│ Barra de         │            ├────────────────────────┤
│ progreso gira    │            │ 1. Crear grid (100ms)  │
│ Usuario puede    │            ├────────────────────────┤
│ hacer scroll,    │◄───signal─ │ 2. Loop antenas (2s)   │
│ mover ventana    │            ├────────────────────────┤
│                  │            │ 3. Agregar (500ms)     │
│ Mostrar          │            ├────────────────────────┤
│ resultados       │◄───signal─ │ 4. Metadata (50ms)     │
│ cuando lleguen    │            ├────────────────────────┤
└──────────────────┘            │ Emitir finished(results)
                                └────────────────────────┘
```

**Resultado**: GUI responsiva durante simulación, experiencia fluida

## 3. Arquitectura de Threading

### 3.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────┐
│ MainWindow (QObject, MainThread)                        │
├─────────────────────────────────────────────────────────┤
│ • UI: botones, menús, mapas                            │
│ • Gestiona proyectos, antenas                          │
│ • Conecta signals de worker a slots                    │
│ • Recibe resultados y actualiza visualización          │
│                                                         │
│  self.simulation_worker = SimulationWorker()           │
│  self.simulation_worker.moveToThread(thread)           │
│  self.simulation_worker.finished.connect(              │
│      self._on_simulation_finished                      │
│  )                                                      │
└──────────────┬──────────────────────────────────────────┘
               │ moveTo()
┌──────────────▼──────────────────────────────────────────┐
│ WorkerThread (QThread)                                 │
├─────────────────────────────────────────────────────────┤
│ • Thread separado de la GUI                            │
│ • Ejecuta run() del worker en este thread              │
│ • NO TOCA la GUI directamente                          │
└──────────────┬──────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────┐
│ SimulationWorker (QObject, WorkerThread)               │
├─────────────────────────────────────────────────────────┤
│ • run() ejecuta la simulación completa                 │
│ • Emite signals: progress, status_message, finished    │
│ • Las signals se entregan a MainThread automáticamente │
│   (mecanismo de queue interno de Qt)                   │
└──────────────┬──────────────────────────────────────────┘
               │ emitir
┌──────────────▼──────────────────────────────────────────┐
│ Signals (Thread-safe)                                  │
├─────────────────────────────────────────────────────────┤
│ • progress(int): 0-100 %                               │
│ • status_message(str): "Calculando..."                 │
│ • finished(dict): resultados finales                   │
│                                                         │
│ Conexión: worker.progress.connect(slot)                │
│ → Qt encoloca el slot en MainThread automáticamente    │
└─────────────────────────────────────────────────────────┘
```

## 4. Clase SimulationWorker

### 4.1 Definición y Signals

**Ubicación**: `src/workers/simulation_worker.py`, líneas 10-50

```python
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import logging

class SimulationWorker(QObject):
    """
    Worker que ejecuta simulaciones en thread separado.
    
    Emite signals thread-safe para comunicar progreso y resultados
    al hilo principal (GUI).
    """
    
    # Signals (solo en direcciones): Worker → MainThread
    
    # Progreso: 0-100 %
    progress = pyqtSignal(int)
    
    # Mensaje de estado (ej: "Calculando cobertura de Antena 1...")
    status_message = pyqtSignal(str)
    
    # Resultados finales: dict con individual, aggregated, metadata
    finished = pyqtSignal(dict)
    
    # Error (si ocurre excepción)
    error = pyqtSignal(str)
    
    def __init__(self, antennas, config, calculator):
        """
        Inicializa el worker.
        
        Args:
            antennas: lista de Antenna objects
            config: dict de configuración (model, radius, resolution, etc.)
            calculator: CoverageCalculator instance
        """
        super().__init__()
        
        self.antennas = antennas
        self.config = config
        self.calculator = calculator
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """
        Punto de entrada principal del worker.
        
        Se ejecuta automáticamente cuando el thread se inicia.
        Toda la lógica de simulación va aquí.
        """
        try:
            self.status_message.emit("Iniciando simulación...")
            self.progress.emit(5)
            
            # ... implementación de simulación ...
            # (ver 09_PIPELINE_SIMULACION_FLUJO.md para detalles)
            
            results = {}
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"Simulación fallida: {str(e)}")
            self.logger.exception("Error in simulation worker")
```

### 4.2 Conexión Desde MainWindow

**Ubicación**: `src/ui/main_window.py`, líneas 200-250

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... init UI ...
    
    def on_simulation_button_clicked(self):
        """Slot: usuario hace clic en botón Simular"""
        
        # Crear worker
        self.simulation_worker = SimulationWorker(
            antennas=self.project.antennas,
            config=self.get_simulation_config(),
            calculator=self.coverage_calculator
        )
        
        # Crear thread dedicado
        self.simulation_thread = QThread()
        
        # Mover worker al thread
        self.simulation_worker.moveToThread(self.simulation_thread)
        
        # Conectar signals del worker a slots de MainWindow
        # ─────────────────────────────────────────────
        
        # Cuando worker emite progress(int), ejecutar slot:
        self.simulation_worker.progress.connect(
            self._on_simulation_progress
        )
        # Qt automáticamente encoloca _on_simulation_progress en MainThread
        
        # Status message
        self.simulation_worker.status_message.connect(
            self._on_simulation_status
        )
        
        # Resultados finales
        self.simulation_worker.finished.connect(
            self._on_simulation_finished
        )
        # Aquí recibimos el dict de resultados en MainThread
        
        # Error
        self.simulation_worker.error.connect(
            self._on_simulation_error
        )
        
        # Cleanup cuando thread termina
        self.simulation_thread.finished.connect(
            self.simulation_thread.deleteLater
        )
        self.simulation_worker.finished.connect(
            self.simulation_thread.quit
        )
        
        # Iniciar thread (llamará a worker.run() en el thread)
        self.simulation_thread.start()
    
    @pyqtSlot(int)
    def _on_simulation_progress(self, percent):
        """Slot: worker reporta progreso"""
        self.progress_bar.setValue(percent)
        # ← Actualiza UI inmediatamente (safe thread)
    
    @pyqtSlot(str)
    def _on_simulation_status(self, message):
        """Slot: worker reporta mensaje de estado"""
        self.status_label.setText(message)
        self.logger.info(message)
    
    @pyqtSlot(dict)
    def _on_simulation_finished(self, results):
        """Slot: worker terminó, resultados disponibles"""
        self.logger.info("Simulation completed")
        
        # Actualizar visualizador
        self.map_widget.add_coverage_layer(
            results['individual'],
            results['aggregated']
        )
        
        # Exportar si lo solicitó el usuario
        if self.auto_export_enabled:
            self.export_manager.export_results(results)
    
    @pyqtSlot(str)
    def _on_simulation_error(self, error_msg):
        """Slot: worker reportó error"""
        self.logger.error(f"Simulation error: {error_msg}")
        QMessageBox.critical(self, "Error", error_msg)
```

## 5. Flujo de Ejecución Completo

### 5.1 Timeline

```
Tiempo    MainThread (GUI)              WorkerThread
────────  ────────────────────────────  ─────────────────────
  0ms     Usuario click Simular
  1ms     Crear SimulationWorker
  2ms     Crear QThread
  3ms     moveToThread()
  4ms     Connect signals
  5ms     thread.start() ──┐
          ↓                │
  6ms     GUI activa       ↓ iniciar worker.run()
  7ms     Progress bar 5%  ├─ _create_grid()
  ...                       │ emit progress(10)
 50ms     Progress bar 10% ├────────────────┐
          Status: "Creating grid"           │
 100ms    Progress bar 30% ├─ Loop antennas │
          Status: "Antenna 1"               ├─ Calcular
 500ms    Progress bar 40% │                │
 1000ms   Progress bar 50% │                │
 2000ms   Progress bar 70% ├─ Aggregation   │
 2500ms   Progress bar 90% ├─ Metadata      │
 2600ms   Progress bar 100% ├─ Emit finished({...})
          ├─ _on_simulation_finished() ────┘
          ├─ Actualizar mapa
          ├─ Mostrar resultados
          └─ GUI activa nuevamente
```

**Duración típica**: 2.5 segundos (GPU)

## 6. Mecanismo de Signals Thread-Safe

### 6.1 Cómo Qt Maneja Thread-Safety

Qt proporciona un mecanismo automático para pasar mensajes entre threads:

```
WorkerThread emite:
    self.progress.emit(30)
         ↓
    [Signal encolado en MainThread]
         ↓
MainThread recibe:
    _on_simulation_progress(30)
         ↓
    Ejecutar en MainThread de forma segura
```

**Garantías de Qt**:
- ✅ Signals conectadas con `Qt.QueuedConnection` (default entre threads)
- ✅ Automáticamente seguras: no hay race conditions
- ✅ Orden preservado: signals se entregan en orden
- ✅ Sincronización interna: Qt maneja la cola de mensajes

### 6.2 Implementación Interna (Concepto)

```python
# Pseudocódigo: cómo Qt lo hace internamente

class Signal:
    def emit(self, *args):
        if sender_thread != current_thread:
            # Diferente thread: encolar mensaje
            event = SignalEvent(self, args)
            receiver_thread.postEvent(event)
        else:
            # Mismo thread: ejecutar directamente
            self.call_slots(*args)
```

## 7. Consideraciones de Seguridad

### 7.1 Qué NO hacer en WorkerThread

```python
# ❌ INCORRECTO: modificar UI desde worker thread
class SimulationWorker(QObject):
    def run(self):
        self.map_widget.setVisible(False)  # ← CRASH potencial!
        # MainThread puede estar accediendo al widget
```

### 7.2 Forma Correcta: Usar Signals

```python
# ✅ CORRECTO: usar signal para notificar MainThread
class SimulationWorker(QObject):
    visualization_update = pyqtSignal(dict)  # signal
    
    def run(self):
        # En worker thread, solo calcular
        results = self.calculate()
        # Emitir signal (será recibido en MainThread)
        self.visualization_update.emit(results)

# En MainWindow:
self.worker.visualization_update.connect(
    self.map_widget.update_coverage  # ← ejecuta en MainThread
)
```

### 7.3 Checklist de Thread-Safety

- ✅ Signals para comunicación entre threads
- ✅ Slots conectados automáticamente thread-safe
- ✅ No acceder directamente a UI desde worker
- ✅ Datos compartidos protegidos (si existen)
- ✅ Cleanup: deleteLater() en lugar de delete()

## 8. Resumen Técnico

| Componente | Ubicación | Thread | Responsabilidad |
|-----------|-----------|--------|-----------------|
| MainWindow | src/ui/main_window.py | Main | Coordina UI y worker |
| SimulationWorker | src/workers/simulation_worker.py | Worker | Ejecuta cálculos |
| Signals | PyQt6 core | Both | Comunicación T-safe |
| QThread | PyQt6 core | Both | Gestiona el thread |

---

**Ver también**: [01_GUI.md](01_GUI.md), [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md)
