from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QToolBar, QStatusBar, QDockWidget, QMessageBox,
                             QFileDialog, QProgressBar, QLabel)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QActionGroup
from src.ui.widgets.map_widget import MapMode
import logging

class MainWindow(QMainWindow):
    """Ventana principal de la aplicación"""
    
    def __init__(self, config_manager, gpu_detector):
        super().__init__()
        self.config = config_manager
        self.gpu = gpu_detector
        self.logger = logging.getLogger("MainWindow")
        
        # Managers
        self.project_manager = None
        self.antenna_manager = None
        self.site_manager = None
        self.coverage_calculator = None
        self.compute_engine = None
        
        # Estado
        self.current_project = None
        self.simulation_running = False
        
        self._init_managers()
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
        
        self.logger.info("MainWindow initialized")
    
    def _init_managers(self):
        """Inicializa los managers del sistema"""
        from src.core.compute_engine import ComputeEngine
        from src.core.antenna_manager import AntennaManager
        from src.core.site_manager import SiteManager
        from src.core.project_manager import ProjectManager
        from src.core.coverage_calculator import CoverageCalculator
        
        # Compute engine
        use_gpu = self.config.settings['compute'].get('use_gpu', True)
        self.compute_engine = ComputeEngine(use_gpu=use_gpu)
        
        # Managers
        self.antenna_manager = AntennaManager()
        self.site_manager = SiteManager()
        self.project_manager = ProjectManager()
        self.coverage_calculator = CoverageCalculator(self.compute_engine)
        
        self.logger.info("Managers initialized")
    
    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("RF Coverage Tool")
        self.setMinimumSize(1400, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Mapa (centro)
        from src.ui.widgets.map_widget import MapWidget
        self.map_widget = MapWidget()
        main_layout.addWidget(self.map_widget, stretch=3)
        
        # Crear toolbars
        self._create_toolbars()
        
        # Crear paneles laterales (dockable)
        self._create_dock_widgets()
        
        # Status bar
        self._create_status_bar()
        
        # Menú
        self._create_menus()
    
    def _create_menus(self):
        """Crea la barra de menús"""
        menubar = self.menuBar()
        
        # Menú File
        file_menu = menubar.addMenu("&Archivo")
        
        new_action = QAction("&Nuevo Proyecto", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Abrir Proyecto...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Guardar Proyecto", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        import_terrain_action = QAction("Importar &Terreno...", self)
        import_terrain_action.triggered.connect(self.import_terrain)
        file_menu.addAction(import_terrain_action)
        
        file_menu.addSeparator()
        
        export_menu = file_menu.addMenu("&Exportar")
        export_kml_action = QAction("KML", self)
        export_kml_action.triggered.connect(lambda: self.export_results('kml'))
        export_menu.addAction(export_kml_action)
        
        export_geotiff_action = QAction("GeoTIFF", self)
        export_geotiff_action.triggered.connect(lambda: self.export_results('geotiff'))
        export_menu.addAction(export_geotiff_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menú Edit
        edit_menu = menubar.addMenu("&Editar")
        
        settings_action = QAction("&Configuración...", self)
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)
        
        # Menú Antenna
        antenna_menu = menubar.addMenu("&Antena")
        
        add_antenna_action = QAction("&Agregar Antena", self)
        add_antenna_action.setShortcut("Ctrl+A")
        add_antenna_action.triggered.connect(self.start_add_antenna_mode)
        antenna_menu.addAction(add_antenna_action)
        
        delete_antenna_action = QAction("&Eliminar Antena", self)
        delete_antenna_action.setShortcut("Delete")
        delete_antenna_action.triggered.connect(self.delete_selected_antenna)
        antenna_menu.addAction(delete_antenna_action)
        
        antenna_menu.addSeparator()
        
        properties_action = QAction("&Propiedades...", self)
        properties_action.setShortcut("Ctrl+P")
        properties_action.triggered.connect(self.show_antenna_properties)
        antenna_menu.addAction(properties_action)
        
        # Menú Simulation
        simulation_menu = menubar.addMenu("&Simulación")
        
        run_simulation_action = QAction("&Ejecutar Simulación", self)
        run_simulation_action.setShortcut("F5")
        run_simulation_action.triggered.connect(self.run_simulation)
        simulation_menu.addAction(run_simulation_action)
        
        stop_simulation_action = QAction("&Detener Simulación", self)
        stop_simulation_action.setShortcut("Ctrl+F5")
        stop_simulation_action.triggered.connect(self.stop_simulation)
        simulation_menu.addAction(stop_simulation_action)
        
        simulation_menu.addSeparator()
        
        analysis_action = QAction("&Análisis de Cobertura...", self)
        analysis_action.triggered.connect(self.show_coverage_analysis)
        simulation_menu.addAction(analysis_action)
        
        # Menú View
        view_menu = menubar.addMenu("&Vista")
        
        # Se agregarán automáticamente las acciones de los dock widgets
        
        # Menú Help
        help_menu = menubar.addMenu("A&yuda")
        
        about_action = QAction("&Acerca de...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbars(self):
        """Crea las barras de herramientas"""
        # Toolbar principal
        main_toolbar = QToolBar("Herramientas Principales")
        main_toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, main_toolbar)
        
        # Acciones de archivo
        new_action = QAction("Nuevo", self)
        new_action.triggered.connect(self.new_project)
        main_toolbar.addAction(new_action)
        
        open_action = QAction("Abrir", self)
        open_action.triggered.connect(self.open_project)
        main_toolbar.addAction(open_action)
        
        save_action = QAction("Guardar", self)
        save_action.triggered.connect(self.save_project)
        main_toolbar.addAction(save_action)
        
        main_toolbar.addSeparator()
        
        # Toolbar del mapa
        map_toolbar = QToolBar("Herramientas de Mapa")
        map_toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, map_toolbar)
        
        # Modo navegación
        pan_action = QAction("Navegar", self)
        pan_action.setCheckable(True)
        pan_action.setChecked(True)
        pan_action.triggered.connect(lambda: self.set_map_mode(MapMode.PAN))
        map_toolbar.addAction(pan_action)
        
        # Modo agregar antena
        add_antenna_action = QAction("Agregar Antena", self)
        add_antenna_action.setCheckable(True)
        add_antenna_action.triggered.connect(self.start_add_antenna_mode)
        map_toolbar.addAction(add_antenna_action)
        
        # Modo mover
        move_action = QAction("Mover", self)
        move_action.setCheckable(True)
        move_action.triggered.connect(lambda: self.set_map_mode(MapMode.MOVE_ANTENNA))
        map_toolbar.addAction(move_action)
        
        # Modo seleccionar
        select_action = QAction("Seleccionar", self)
        select_action.setCheckable(True)
        select_action.triggered.connect(lambda: self.set_map_mode(MapMode.SELECT))
        map_toolbar.addAction(select_action)
        
        map_toolbar.addSeparator()
        
        # Simulación
        simulate_action = QAction("Simular", self)
        simulate_action.triggered.connect(self.run_simulation)
        map_toolbar.addAction(simulate_action)
        
        # Agrupar acciones de modo (solo una activa a la vez)
        self.map_mode_group = QActionGroup(self)
        self.map_mode_group.addAction(pan_action)
        self.map_mode_group.addAction(add_antenna_action)
        self.map_mode_group.addAction(move_action)
        self.map_mode_group.addAction(select_action)
    
    def _create_dock_widgets(self):
        """Crea los paneles acoplables"""
        # Panel de proyecto (izquierda)
        from src.ui.panels.project_panel import ProjectPanel
        self.project_panel = ProjectPanel(self.antenna_manager, self.site_manager)
        project_dock = QDockWidget("Proyecto", self)
        project_dock.setWidget(self.project_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, project_dock)
        
        # Panel de capas (izquierda, abajo)
        from src.ui.panels.layers_panel import LayersPanel
        self.layers_panel = LayersPanel()
        layers_dock = QDockWidget("Capas", self)
        layers_dock.setWidget(self.layers_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, layers_dock)
        
        # Panel de propiedades (derecha)
        from src.ui.panels.properties_panel import PropertiesPanel
        self.properties_panel = PropertiesPanel()
        properties_dock = QDockWidget("Propiedades", self)
        properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, properties_dock)
        
        # Panel de análisis (derecha, abajo)
        from src.ui.panels.analysis_panel import AnalysisPanel
        self.analysis_panel = AnalysisPanel()
        analysis_dock = QDockWidget("Análisis", self)
        analysis_dock.setWidget(self.analysis_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, analysis_dock)
    
    def _create_status_bar(self):
        """Crea la barra de estado"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Mensaje permanente
        self.status_label = QLabel("Listo")
        status_bar.addWidget(self.status_label)
        
        # Info del sistema
        compute_mode = "GPU" if self.compute_engine.use_gpu else "CPU"
        gpu_label = QLabel(f"Compute: {compute_mode}")
        status_bar.addPermanentWidget(gpu_label)
        
        # Coordenadas del cursor
        self.coords_label = QLabel("Lat: 0.000000, Lon: 0.000000")
        status_bar.addPermanentWidget(self.coords_label)
        
        # Barra de progreso (oculta por defecto)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)
    
    def _connect_signals(self):
        """Conecta señales entre componentes"""
        # Señales del mapa
        self.map_widget.antenna_placed.connect(self.on_antenna_placed)
        self.map_widget.antenna_moved.connect(self.on_antenna_moved)
        self.map_widget.antenna_selected.connect(self.on_antenna_selected)
        
        # Señales del antenna manager
        self.antenna_manager.antenna_added.connect(self.on_antenna_added)
        self.antenna_manager.antenna_removed.connect(self.on_antenna_removed)
        self.antenna_manager.antenna_modified.connect(self.on_antenna_modified)
        
        # Señales del project panel
        self.project_panel.antenna_selected.connect(self.select_antenna)
        self.project_panel.antenna_delete_requested.connect(self.delete_antenna)
    
    def _load_settings(self):
        """Carga configuración inicial"""
        # Centrar mapa en ubicación por defecto
        default_center = self.config.settings['ui']['default_map_center']
        default_zoom = self.config.settings['ui']['map_default_zoom']
        self.map_widget.center_on_location(
            default_center[0], default_center[1], default_zoom
        )
    
    # ===== Slots para manejo de antenas =====
    
    def start_add_antenna_mode(self):
        """Activa modo de agregar antena"""
        from src.ui.widgets.map_widget import MapMode
        self.map_widget.set_mode(MapMode.ADD_ANTENNA)
        self.status_label.setText("Haga clic en el mapa para colocar una antena")

    def select_antenna(self, antenna_id: str):
        """Selecciona una antena"""
        self.antenna_manager.select_antenna(antenna_id)
        antenna = self.antenna_manager.get_antenna(antenna_id)
        if antenna:
            # Mostrar propiedades en el panel
            self.properties_panel.show_antenna_properties(antenna)
            # Centrar mapa en la antena
            self.map_widget.center_on_location(antenna.latitude, antenna.longitude, 16)
            self.status_label.setText(f"Antena seleccionada: {antenna.name}")

    def delete_antenna(self, antenna_id: str):
        """Elimina una antena"""
        antenna = self.antenna_manager.get_antenna(antenna_id)
        if antenna:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Confirmar eliminación",
                f"¿Está seguro de eliminar la antena '{antenna.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.antenna_manager.remove_antenna(antenna_id)
                self.status_label.setText(f"Antena '{antenna.name}' eliminada")
    
    @pyqtSlot(float, float)
    def on_antenna_placed(self, lat: float, lon: float):
        """Callback cuando se coloca una antena en el mapa"""
        self.logger.info(f"Antenna placed at: {lat}, {lon}")
        
        # Crear antena
        antenna_id = self.antenna_manager.create_antenna_at_location(lat, lon)
        antenna = self.antenna_manager.get_antenna(antenna_id)
        
        # Agregar al mapa
        self.map_widget.add_antenna(
            antenna.id, antenna.latitude, antenna.longitude,
            antenna.name, antenna.color
        )
        
        self.status_label.setText(f"Antena '{antenna.name}' agregada")
    
    @pyqtSlot(str, float, float)
    def on_antenna_moved(self, antenna_id: str, lat: float, lon: float):
        """Callback cuando se mueve una antena en el mapa"""
        self.antenna_manager.move_antenna(antenna_id, lat, lon)
        self.logger.info(f"Antenna {antenna_id} moved to: {lat}, {lon}")
    
    @pyqtSlot(str)
    def on_antenna_selected(self, antenna_id: str):
        """Callback cuando se selecciona una antena"""
        antenna = self.antenna_manager.get_antenna(antenna_id)
        if antenna:
            self.properties_panel.show_antenna_properties(antenna)
            self.status_label.setText(f"Antena seleccionada: {antenna.name}")
    
    def on_antenna_added(self, antenna_id: str):
        """Actualiza UI cuando se agrega una antena"""
        self.project_panel.refresh()
    
    def on_antenna_removed(self, antenna_id: str):
        """Actualiza UI cuando se elimina una antena"""
        self.map_widget.remove_antenna(antenna_id)
        self.project_panel.refresh()
    
    def on_antenna_modified(self, antenna_id: str):
        """Actualiza UI cuando se modifica una antena"""
        antenna = self.antenna_manager.get_antenna(antenna_id)
        if antenna:
            self.map_widget.update_antenna(
                antenna.id, antenna.latitude, antenna.longitude,
                antenna.azimuth, antenna.color
            )
    
    def delete_selected_antenna(self):
        """Elimina la antena seleccionada"""
        selected_id = self.antenna_manager.selected_antenna_id
        if selected_id:
            self.antenna_manager.remove_antenna(selected_id)
    
    # ===== Manejo de proyectos =====
    
    def new_project(self):
        """Crea un nuevo proyecto"""
        # Preguntar si guardar proyecto actual
        if self.current_project and self.project_has_changes():
            reply = QMessageBox.question(
                self, "Guardar cambios",
                "¿Desea guardar los cambios del proyecto actual?",
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # Crear nuevo proyecto
        from src.models.project import Project
        self.current_project = Project(name="Nuevo Proyecto")
        
        # Limpiar todo
        self.antenna_manager.antennas.clear()
        self.project_panel.refresh()
        
        self.logger.info("New project created")
        self.status_label.setText("Nuevo proyecto creado")
    
    def open_project(self):
        """Abre un proyecto existente"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Abrir Proyecto", "data/projects",
            "RF Projects (*.rfproj)"
        )
        
        if filename:
            try:
                from src.models.project import Project
                self.current_project = Project.load_from_file(filename)
                
                # Cargar antenas y sitios
                self.antenna_manager.antennas = self.current_project.antennas
                self.site_manager.sites = self.current_project.sites
                
                # Actualizar mapa
                for antenna in self.antenna_manager.get_all_antennas():
                    self.map_widget.add_antenna(
                        antenna.id, antenna.latitude, antenna.longitude,
                        antenna.name, antenna.color
                    )
                
                # Centrar mapa
                self.map_widget.center_on_location(
                    self.current_project.center_lat,
                    self.current_project.center_lon,
                    self.current_project.zoom_level
                )
                
                # Actualizar UI
                self.project_panel.refresh()
                self.setWindowTitle(f"RF Coverage Tool - {self.current_project.name}")
                
                self.logger.info(f"Project loaded: {filename}")
                self.status_label.setText(f"Proyecto cargado: {self.current_project.name}")
                
            except Exception as e:
                self.logger.error(f"Error loading project: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo cargar el proyecto:\n{e}")
    
    def save_project(self):
        """Guarda el proyecto actual"""
        if not self.current_project:
            self.save_project_as()
            return
        
        try:
            # Actualizar datos del proyecto
            self.current_project.antennas = self.antenna_manager.antennas
            self.current_project.sites = self.site_manager.sites
            
            # Guardar
            filepath = f"data/projects/{self.current_project.name}.rfproj"
            self.current_project.save_to_file(filepath)
            
            self.logger.info(f"Project saved: {filepath}")
            self.status_label.setText("Proyecto guardado")
            
        except Exception as e:
            self.logger.error(f"Error saving project: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n{e}")
    
    def save_project_as(self):
        """Guarda el proyecto con un nuevo nombre"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar Proyecto Como", "data/projects",
            "RF Projects (*.rfproj)"
        )
        
        if filename:
            if not filename.endswith('.rfproj'):
                filename += '.rfproj'
            
            try:
                self.current_project.save_to_file(filename)
                self.logger.info(f"Project saved as: {filename}")
                self.status_label.setText(f"Proyecto guardado: {filename}")
            except Exception as e:
                self.logger.error(f"Error saving project: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")
    
    # ===== Simulación =====
    
    def run_simulation(self):
        """Ejecuta la simulación de cobertura"""
        if self.simulation_running:
            QMessageBox.warning(self, "Advertencia", "Ya hay una simulación en ejecución")
            return
        
        antennas = self.antenna_manager.get_enabled_antennas()
        if not antennas:
            QMessageBox.warning(self, "Advertencia", "No hay antenas para simular")
            return
        
        # Mostrar diálogo de simulación
        from src.ui.dialogs.simulation_dialog import SimulationDialog
        dialog = SimulationDialog(antennas, self)
        
        if dialog.exec():
            self.logger.info("Starting simulation...")
            self.simulation_running = True
            self.status_label.setText("Ejecutando simulación...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Ejecutar simulación en thread separado
            from PyQt6.QtCore import QThread
            from src.workers.simulation_worker import SimulationWorker
            
            self.simulation_thread = QThread()
            self.simulation_worker = SimulationWorker(
                antennas=antennas,
                coverage_calculator=self.coverage_calculator,
                terrain_data=None,  # TODO: cargar terrain
                config=dialog.get_config()
            )
            
            self.simulation_worker.moveToThread(self.simulation_thread)
            
            # Conectar señales
            self.simulation_thread.started.connect(self.simulation_worker.run)
            self.simulation_worker.progress.connect(self.update_simulation_progress)
            self.simulation_worker.status_message.connect(self.status_label.setText)
            self.simulation_worker.finished.connect(self.on_simulation_finished)
            self.simulation_worker.error.connect(self.on_simulation_error)
            
            # Iniciar thread
            self.simulation_thread.start()
    
    @pyqtSlot(int)
    def update_simulation_progress(self, value: int):
        """Actualiza barra de progreso de simulación"""
        self.progress_bar.setValue(value)
    
    @pyqtSlot(dict)
    def on_simulation_finished(self, results: dict):
        """Callback cuando termina la simulación"""
        self.logger.info("Simulation completed")
        self.simulation_running = False
        self.progress_bar.setVisible(False)
        self.status_label.setText("Simulación completada")
        
        # Mostrar resultados en el mapa
        for antenna_id, coverage in results['individual'].items():
            self.map_widget.show_coverage(antenna_id, coverage)
        
        # Actualizar panel de análisis
        self.analysis_panel.update_results(results)
        
        # Limpiar thread
        self.simulation_thread.quit()
        self.simulation_thread.wait()
        
        QMessageBox.information(self, "Simulación", "Simulación completada exitosamente")
    
    @pyqtSlot(str)
    def on_simulation_error(self, error_msg: str):
        """Callback cuando hay error en simulación"""
        self.logger.error(f"Simulation error: {error_msg}")
        self.simulation_running = False
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error en simulación")
        
        # Limpiar thread
        self.simulation_thread.quit()
        self.simulation_thread.wait()
        
        QMessageBox.critical(self, "Error", f"Error en la simulación:\n{error_msg}")
    
    def stop_simulation(self):
        """Detiene la simulación en ejecución"""
        if self.simulation_running and hasattr(self, 'simulation_worker'):
            self.simulation_worker.stop()
            self.status_label.setText("Deteniendo simulación...")
    
    # ===== Otras funciones =====
    
    def import_terrain(self):
        """Importa archivo de terreno"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importar Terreno", "data/terrain",
            "Terrain Files (*.dt1 *.dt2 *.dem *.tif *.hgt)"
        )
        
        if filename:
            try:
                from src.core.terrain_loader import TerrainLoader
                terrain_loader = TerrainLoader()
                terrain_data = terrain_loader.load(filename)
                
                self.logger.info(f"Terrain loaded: {filename}")
                self.status_label.setText("Terreno cargado exitosamente")
                
                # Guardar referencia en proyecto
                if self.current_project:
                    self.current_project.terrain_file = filename
                
            except Exception as e:
                self.logger.error(f"Error loading terrain: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo cargar el terreno:\n{e}")
    
    def export_results(self, format_type: str):
        """Exporta resultados de simulación"""
        if not hasattr(self, 'last_simulation_results'):
            QMessageBox.warning(self, "Advertencia", "No hay resultados para exportar")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, f"Exportar como {format_type.upper()}", "data/exports",
            f"{format_type.upper()} Files (*.{format_type})"
        )
        
        if filename:
            try:
                from src.utils.export_manager import ExportManager
                exporter = ExportManager()
                
                if format_type == 'kml':
                    exporter.export_kml(self.last_simulation_results, filename)
                elif format_type == 'geotiff':
                    exporter.export_geotiff(self.last_simulation_results, filename)
                
                self.logger.info(f"Results exported to: {filename}")
                self.status_label.setText(f"Resultados exportados a {format_type.upper()}")
                
            except Exception as e:
                self.logger.error(f"Export error: {e}")
                QMessageBox.critical(self, "Error", f"Error al exportar:\n{e}")
    
    def set_map_mode(self, mode):
        """Cambia el modo del mapa"""
        self.map_widget.set_mode(mode)
    
    def show_settings(self):
        """Muestra diálogo de configuración"""
        from src.ui.dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self.compute_engine, self)
        
        if dialog.exec():
            self.logger.info("Settings updated")
            self.config.save_settings(dialog.get_settings())
    
    def show_antenna_properties(self):
        """Muestra propiedades de la antena seleccionada"""
        antenna_id = self.antenna_manager.selected_antenna_id
        if not antenna_id:
            QMessageBox.information(self, "Info", "Seleccione una antena primero")
            return
        
        antenna = self.antenna_manager.get_antenna(antenna_id)
        if antenna:
            from src.ui.dialogs.antenna_properties_dialog import AntennaPropertiesDialog
            dialog = AntennaPropertiesDialog(antenna, self)
            
            if dialog.exec():
                # Actualizar propiedades
                updated_props = dialog.get_properties()
                self.antenna_manager.update_antenna(antenna_id, **updated_props)
    
    def show_coverage_analysis(self):
        """Muestra análisis detallado de cobertura"""
        # TODO: Implementar ventana de análisis
        pass
    
    def show_about(self):
        """Muestra información sobre la aplicación"""
        QMessageBox.about(
            self, "Acerca de RF Coverage Tool",
            """<h3>RF Coverage Tool v1.0</h3>
            <p>Herramienta profesional de planificación RF</p>
            <p><b>Características:</b></p>
            <ul>
            <li>Modelos de propagación tradicionales (Okumura-Hata, COST-231, ITU-R)</li>
            <li>Modelos 3GPP TR 38.901 para 5G</li>
            <li>Aceleración por GPU con CuPy</li>
            <li>Análisis multi-banda e interferencia</li>
            <li>Exportación KML, GeoTIFF, JSON</li>
            </ul>
            <p><b>Compute Engine:</b> {}</p>
            """.format("GPU (CUDA)" if self.compute_engine.use_gpu else "CPU")
        )
    
    def project_has_changes(self) -> bool:
        """Verifica si el proyecto tiene cambios sin guardar"""
        # TODO: Implementar tracking de cambios
        return False
    
    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        if self.project_has_changes():
            reply = QMessageBox.question(
                self, "Cerrar",
                "¿Desea guardar los cambios antes de salir?",
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()