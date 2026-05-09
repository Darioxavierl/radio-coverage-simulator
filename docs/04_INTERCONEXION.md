# Interconexión y Orquestación: Arquitectura de Integración E2E

**Versión:** 2026-05-08

## 1. Propósito

Este documento describe cómo interactúan todos los componentes del sistema desde que el usuario abre un proyecto hasta que se exportan los resultados. Incluye interfaces, flujos de datos, contratos entre módulos y ejemplos de código real.

## 2. Capas de Arquitectura

```
┌─────────────────────────────────────────┐
│ 5. Capa de Presentación                 │
│    MainWindow, Dialogs, MapWidget       │
│    (UI responsable, interacción usuario)│
└─────────────────────────────────────────┘
              ↓ Qt Signals/Slots
┌─────────────────────────────────────────┐
│ 4. Capa de Orquestación                 │
│    ProjectManager, SimulationWorker     │
│    (Flujo, estado, delegación)          │
└─────────────────────────────────────────┘
              ↓ Métodos directos
┌─────────────────────────────────────────┐
│ 3. Capa de Dominio                      │
│    Project, Site, Antenna (modelos)    │
│    (Encapsulación de datos de negocio)  │
└─────────────────────────────────────────┘
              ↓ Métodos directos
┌─────────────────────────────────────────┐
│ 2. Capa de Cálculo                      │
│    ComputeEngine, CoverageCalculator    │
│    TerrainLoader, PropagationModels     │
│    (Operaciones numéricas)              │
└─────────────────────────────────────────┘
              ↓ NumPy/CuPy arrays
┌─────────────────────────────────────────┐
│ 1. Capa de Hardware                     │
│    CPU (NumPy) o GPU (CuPy)             │
│    (Ejecución de operaciones)           │
└─────────────────────────────────────────┘
```

## 3. Interfaz de Contrato: ComputeEngine

**Ubicación**: `src/core/compute_engine.py`

### 3.1 Interfaz (Qué garantiza)

```python
class IComputeEngine(ABC):
    """
    Interfaz que cualquier implementación de motor de cómputo debe respetar.
    """
    
    @abstractmethod
    def get_compute_module(self):
        """
        Retorna: 'cupy' o 'numpy' (módulo seleccionado)
        Garantía: Siempre retorna un módulo funcional
        """
        pass
    
    @abstractmethod
    def is_gpu_available(self) -> bool:
        """
        Retorna: True si GPU está disponible y lista
        Garantía: Sin efectos secundarios, solo chequeo
        """
        pass
    
    @abstractmethod
    def get_device_info(self) -> dict:
        """
        Retorna: {'device_name', 'compute_capability', 'memory_mb'}
        Garantía: Información actual del dispositivo
        """
        pass

# Implementación
class ComputeEngine(IComputeEngine):
    def __init__(self, use_gpu: bool = True):
        self.gpu_detector = GPUDetector()
        self.use_gpu = use_gpu and self.gpu_detector.cupy_available
        self.xp = self._select_backend()
    
    def _select_backend(self):
        if self.use_gpu:
            return self.gpu_detector.get_compute_module()  # CuPy
        else:
            return np  # NumPy
```

### 3.2 Contrato de Entrada/Salida

```python
# ENTRADA
input_params = {
    'antenna_latitude': float,           # -2.9001
    'antenna_longitude': float,          # -79.0059
    'antenna_frequency_mhz': int,        # 900
    'antenna_tx_power_dbm': int,         # 40
    'antenna_tx_gain_dbi': int,          # 14
    'environment': str,                  # 'urban', 'suburban', 'rural'
    'model_name': str,                   # 'okumura_hata', 'cost_231', etc.
    'grid_resolution': int,              # 100 (100×100 grilla)
    'simulation_radius_km': float,       # 5 km
}

# SALIDA
output = {
    'rsrp': np.ndarray,                  # shape (100, 100), dtype float32
    'path_loss': np.ndarray,             # shape (100, 100), dtype float32
    'antenna_gain': np.ndarray,          # shape (100, 100), dtype float32
    'execution_time_ms': float,          # Timing de cálculo
    'backend_used': str,                 # 'numpy' o 'cupy'
    'grid_bounds': dict,                 # {'lat_min', 'lat_max', 'lon_min', 'lon_max'}
}
```

## 4. Flujo E2E: Desde Proyecto a Exportación

### 4.1 Paso 1: Cargar Proyecto desde Archivo

```python
# src/ui/main_window.py
class MainWindow(QMainWindow):
    def on_open_project(self):
        """Usuario hace click en 'Abrir Proyecto'"""
        
        filepath = QFileDialog.getOpenFileName(
            self, "Open Project", "", "RF Projects (*.rfproj)"
        )[0]
        
        if not filepath:
            return
        
        # Delegar al gestor de proyecto
        self.project_manager = ProjectManager()
        self.project = self.project_manager.load_project(filepath)
        # → self.project = Project(
        #     name='Mi Proyecto',
        #     sites=[Site(...), Site(...)],
        #     terrain_file='cuenca_terrain.tif'
        # )
        
        # Actualizar árbol de UI
        self._update_project_tree()

# src/core/project_manager.py
class ProjectManager:
    def load_project(self, filepath: str) -> Project:
        """
        Entrada: ruta a archivo .rfproj
        Proceso:
          1. Leer JSON
          2. Deserializar objetos
          3. Validar integridad
        Salida: objeto Project completamente inicializado
        """
        
        with open(filepath) as f:
            data = json.load(f)
        
        project = Project(
            id=data['project_id'],
            name=data['name'],
            terrain_file=data.get('terrain_file'),
        )
        
        # Cargar sitios y antenas
        for site_data in data.get('sites', []):
            site = Site(**site_data)
            for antenna_data in site_data.get('antennas', []):
                antenna = Antenna(**antenna_data)
                site.antennas.append(antenna)
            project.sites.append(site)
        
        return project
```

### 4.2 Paso 2: Usuario Inicia Simulación

```python
# src/ui/dialogs/simulation_dialog.py
class SimulationDialog(QDialog):
    def on_simulate_clicked(self):
        """Usuario hace click en 'Ejecutar Simulación'"""
        
        # Recopilar parámetros de UI
        params = {
            'model': self.model_combo.currentText(),        # 'okumura_hata'
            'environment': self.env_combo.currentText(),    # 'urban'
            'grid_resolution': self.resolution_spin.value(), # 100
            'radius_km': self.radius_spin.value(),          # 5
        }
        
        # Validar parámetros
        if not self._validate_params(params):
            QMessageBox.warning(self, "Error", "Parámetros inválidos")
            return
        
        # Emitir signal para enviar a worker
        self.simulation_requested.emit(params)
```

### 4.3 Paso 3: SimulationWorker Orquesta Cálculo

```python
# src/workers/simulation_worker.py
class SimulationWorker(QObject):
    # Signals
    started = pyqtSignal()
    progress = pyqtSignal(int)          # 0-100
    results_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def run_simulation(self, project: Project, params: dict):
        """
        Entrada: proyecto completo + parámetros de simulación
        Proceso: Orquestar pipeline completo
        Salida: Emitir results_ready.emit(results)
        """
        
        self.started.emit()
        start_time = time.time()
        
        try:
            # 1. Cargar terreno
            self.progress.emit(5)
            terrain_loader = TerrainLoader(project.terrain_file)
            terrain_info = terrain_loader.get_valid_coverage_region()
            
            # 2. Inicializar motor de cómputo
            self.progress.emit(10)
            compute_engine = ComputeEngine(use_gpu=True)
            
            # 3. Crear grilla de simulación
            self.progress.emit(15)
            grid_info = self._create_simulation_grid(
                center_lat=project.sites[0].latitude,
                center_lon=project.sites[0].longitude,
                radius_km=params['radius_km'],
                resolution=params['grid_resolution']
            )
            # grid_info = {
            #     'lats_1d': np.array([...]),     shape (100,)
            #     'lons_1d': np.array([...]),     shape (100,)
            #     'lats_2d': np.array([...]),     shape (100, 100)
            #     'lons_2d': np.array([...]),     shape (100, 100)
            #     'bounds': {...}
            # }
            
            # 4. Inicializar calculador de cobertura
            self.progress.emit(20)
            coverage_calc = CoverageCalculator(
                compute_engine=compute_engine,
                terrain_loader=terrain_loader
            )
            
            # 5. Cargar modelo de propagación
            self.progress.emit(25)
            propagation_model = get_propagation_model(
                params['model'],
                environment=params['environment']
            )
            
            # 6. Calcular cobertura por antena
            results = {
                'individual': {},
                'aggregated': {},
                'metadata': {}
            }
            
            # Obtener alturas de terreno (una sola vez)
            terrain_heights = terrain_loader.get_heights_fast(
                grid_info['lats_2d'],
                grid_info['lons_2d']
            )
            
            all_rsrp = []
            antenna_index = 0
            
            for site in project.sites:
                for antenna in site.antennas:
                    antenna_index += 1
                    progress_pct = 25 + (50 * antenna_index / len(project.sites[0].antennas))
                    self.progress.emit(int(progress_pct))
                    
                    # Calcular cobertura para esta antena
                    ant_result = coverage_calc.calculate_single_antenna_coverage(
                        antenna=antenna,
                        grid_lats=grid_info['lats_2d'],
                        grid_lons=grid_info['lons_2d'],
                        terrain_heights=terrain_heights,
                        model=propagation_model,
                        model_params=params
                    )
                    # ant_result = {
                    #     'rsrp': np.array [...] shape (100, 100)
                    #     'path_loss': np.array [...]
                    #     'antenna_gain': np.array [...]
                    # }
                    
                    results['individual'][antenna.id] = {
                        **ant_result,
                        'name': antenna.name,
                        'latitude': antenna.latitude,
                        'longitude': antenna.longitude,
                        'frequency_mhz': antenna.frequency_mhz,
                        'tx_power_dbm': antenna.tx_power_dbm,
                        'height_agl': antenna.height_agl,
                        'bounds': grid_info['bounds']
                    }
                    
                    all_rsrp.append(ant_result['rsrp'])
            
            # 7. Agregar resultados (máximo RSRP en cada punto)
            self.progress.emit(85)
            all_rsrp = compute_engine.xp.stack(all_rsrp, axis=0)
            rsrp_aggregated = compute_engine.xp.max(all_rsrp, axis=0)
            
            if compute_engine.use_gpu:
                rsrp_aggregated = compute_engine.xp.asnumpy(rsrp_aggregated)
            
            results['aggregated'] = {
                'rsrp': rsrp_aggregated,
                'bounds': grid_info['bounds']
            }
            
            # 8. Generar heatmap (imagen PNG base64)
            self.progress.emit(90)
            heatmap_gen = HeatmapGenerator()
            image_url = heatmap_gen.generate_heatmap_dataurl(
                rsrp_aggregated,
                vmin=-150,
                vmax=-40,
                cmap='RdYlGn_r'
            )
            
            results['aggregated']['image_url'] = image_url
            for ant_id, ant_data in results['individual'].items():
                results['individual'][ant_id]['image_url'] = \
                    heatmap_gen.generate_heatmap_dataurl(
                        ant_data['rsrp'],
                        vmin=-150,
                        vmax=-40
                    )
            
            # 9. Guardar metadata
            self.progress.emit(95)
            execution_time = time.time() - start_time
            results['metadata'] = {
                'model': params['model'],
                'environment': params['environment'],
                'frequency_mhz': project.sites[0].antennas[0].frequency_mhz,
                'terrain_file': project.terrain_file,
                'grid_resolution': params['grid_resolution'],
                'simulation_radius_km': params['radius_km'],
                'total_execution_time_seconds': execution_time,
                'gpu_device': compute_engine.gpu_detector.get_device_info() if compute_engine.use_gpu else 'CPU',
            }
            
            self.progress.emit(100)
            
            # 10. Emitir results (ThreadSafe)
            self.results_ready.emit(results)
            
        except Exception as e:
            self.logger.error(f"Simulation failed: {str(e)}")
            self.error_occurred.emit(f"Error: {str(e)}")
```

### 4.4 Paso 4: MainWindow Recibe Resultados

```python
# src/ui/main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Crear worker
        self.simulation_worker = SimulationWorker()
        self.worker_thread = QThread()
        
        # Mover worker a thread
        self.simulation_worker.moveToThread(self.worker_thread)
        
        # Conectar signals
        self.simulation_worker.results_ready.connect(
            self._on_simulation_finished
        )
        self.simulation_worker.progress.connect(
            self._on_simulation_progress
        )
        self.simulation_worker.error_occurred.connect(
            self._on_simulation_error
        )
    
    @pyqtSlot(dict)
    def _on_simulation_finished(self, results: dict):
        """Callback cuando simulación termina (MainThread)"""
        
        # Guardar resultados
        self.last_results = results
        
        # Actualizar visualización del mapa
        self.map_widget.bridge.add_coverage_layer.emit(
            antenna_id='aggregated',
            image_data_url=results['aggregated']['image_url'],
            lat_min=results['aggregated']['bounds']['lat_min'],
            lon_min=results['aggregated']['bounds']['lon_min'],
            lat_max=results['aggregated']['bounds']['lat_max'],
            lon_max=results['aggregated']['bounds']['lon_max']
        )
        
        # Mostrar estadísticas
        metadata = results['metadata']
        self.status_label.setText(
            f"✓ Simulación completada en {metadata['total_execution_time_seconds']:.2f}s | "
            f"Backend: {metadata['gpu_device']}"
        )
        
        # Habilitar exportación
        self.export_button.setEnabled(True)
```

### 4.5 Paso 5: Exportar Resultados

```python
# src/ui/main_window.py
@pyqtSlot()
def on_export_clicked(self):
    """Usuario hace click en 'Exportar Resultados'"""
    
    if not self.last_results:
        QMessageBox.warning(self, "Error", "No hay resultados para exportar")
        return
    
    export_manager = ExportManager(output_dir='data/exports')
    
    export_files = export_manager.export_all(
        project_name=self.project.name,
        results=self.last_results,
        terrain_loader=self.terrain_loader,
        grid_lats=self.grid_info['lats_2d'],
        grid_lons=self.grid_info['lons_2d']
    )
    
    # Validar exportación
    validation = export_manager.validate_export(export_files)
    
    if validation['valid']:
        message = (
            f"✓ Exportación completada\n\n"
            f"Archivos generados: {validation['total_files']}\n"
            f"Ubicación: {export_manager.output_dir}"
        )
        QMessageBox.information(self, "Exportación", message)
    else:
        message = "Errores durante exportación:\n" + "\n".join(validation['issues'])
        QMessageBox.critical(self, "Error", message)
```

## 5. Contratos de Interface: CoverageCalculator

```python
class CoverageCalculator:
    """
    Interface con contrato de entrada/salida explícito.
    """
    
    def calculate_single_antenna_coverage(
        self,
        antenna: Antenna,              # Objeto de dominio
        grid_lats: np.ndarray,         # shape (100, 100)
        grid_lons: np.ndarray,         # shape (100, 100)
        terrain_heights: np.ndarray,   # shape (100, 100)
        model,                         # Instancia de modelo de propagación
        model_params: dict             # Parámetros adicionales
    ) -> dict:
        """
        Calcula cobertura de una antena en toda la grilla.
        
        Garantías:
        - Entrada: todos los arrays tienen shape (100, 100)
        - Salida: RSRP en rango [-150, -40] dBm típicamente
        - No modifica arrays de entrada (copia internamente)
        - Maneja CPU/GPU transparentemente
        """
        
        # Validación de entrada
        assert grid_lats.shape == (100, 100), f"grid_lats shape: {grid_lats.shape}"
        assert grid_lons.shape == (100, 100), f"grid_lons shape: {grid_lons.shape}"
        assert terrain_heights.shape == (100, 100), f"terrain_heights shape: {terrain_heights.shape}"
        
        # Calcular distancia Haversine
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats, grid_lons
        )
        
        # Calcular path loss
        path_loss = model.calculate_path_loss(
            distances,
            antenna.frequency_mhz,
            antenna.height_agl,
            model_params.get('mobile_height', 1.5),
            model_params.get('environment', 'urban')
        )
        
        # Calcular ganancia de antena (patrón de radiación)
        antenna_gain = self._calculate_antenna_gain(
            antenna,
            grid_lats, grid_lons
        )
        
        # RSRP = Ptx + Gtx + Grx - Path_Loss
        rsrp = (
            antenna.tx_power_dbm +
            antenna.tx_gain_dbi +
            antenna_gain -
            path_loss
        )
        
        # Validar output
        assert rsrp.shape == (100, 100), f"rsrp shape: {rsrp.shape}"
        assert np.all(np.isfinite(rsrp)), "RSRP contiene NaN/Inf"
        assert np.min(rsrp) >= -150, f"RSRP mínimo: {np.min(rsrp)}"
        assert np.max(rsrp) <= 50, f"RSRP máximo: {np.max(rsrp)}"
        
        # Retornar
        return {
            'rsrp': rsrp.astype(np.float32),
            'path_loss': path_loss.astype(np.float32),
            'antenna_gain': antenna_gain.astype(np.float32),
        }
```

## 6. Manejo de Errores y Excepciones

```python
# Ubicación: src/workers/simulation_worker.py

def run_simulation(self, project, params):
    try:
        # ... simulación ...
    
    except FileNotFoundError as e:
        self.error_occurred.emit(f"Terrain file not found: {str(e)}")
    
    except ValueError as e:
        self.error_occurred.emit(f"Invalid simulation parameters: {str(e)}")
    
    except RuntimeError as e:
        if "CUDA" in str(e):
            self.error_occurred.emit(f"GPU error (fallback to CPU): {str(e)}")
            # Re-intentar con CPU
            compute_engine = ComputeEngine(use_gpu=False)
            # ...
        else:
            self.error_occurred.emit(f"Runtime error: {str(e)}")
    
    except Exception as e:
        self.error_occurred.emit(f"Unexpected error: {str(e)}")
        self.logger.exception("Simulation failed")
```

## 7. Timing Total del Sistema

```
┌─────────────────────────────────────────────────┐
│ Fase                    | Tiempo   | % Total    │
├─────────────────────────────────────────────────┤
│ 1. Cargar proyecto      | 10 ms    | 0.3%       │
│ 2. Cargar terreno       | 50 ms    | 1.7%       │
│ 3. Iniciar GPU          | 100 ms   | 3.3%       │
│ 4. Crear grilla         | 5 ms     | 0.2%       │
│ 5. Calcular (3 antenas) | 2400 ms  | 80%        │
│    ├─ Ant 1: 800 ms     |          |            │
│    ├─ Ant 2: 800 ms     |          |            │
│    └─ Ant 3: 800 ms     |          |            │
│ 6. Agregación + max     | 50 ms    | 1.7%       │
│ 7. Generar heatmap      | 150 ms   | 5%         │
│ 8. Emitir resultados    | 10 ms    | 0.3%       │
├─────────────────────────────────────────────────┤
│ TOTAL                   | ~2775 ms | 100%       │
│ (CPU: ~14000 ms)        |          |            │
│ SPEEDUP (GPU)           | 5×       |            │
└─────────────────────────────────────────────────┘
```

---

**Ver también**: [02_CORE_COMPUTE.md](02_CORE_COMPUTE.md), [09_PIPELINE_SIMULACION_FLUJO.md](09_PIPELINE_SIMULACION_FLUJO.md), [10_MODELO_EJECUCION_THREADS.md](10_MODELO_EJECUCION_THREADS.md)
