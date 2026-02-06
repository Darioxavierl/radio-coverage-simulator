from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QWidget, QCheckBox,
                             QComboBox, QGroupBox, QFormLayout, QSpinBox,
                             QMessageBox)
from PyQt6.QtCore import Qt
import logging

class SettingsDialog(QDialog):
    def __init__(self, config, compute_engine, parent=None):
        super().__init__(parent)
        self.config = config
        self.compute_engine = compute_engine
        self.logger = logging.getLogger("SettingsDialog")
        
        self.setWindowTitle("Configuración")
        self.setMinimumSize(600, 400)
        
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        """Configura la interfaz"""
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        
        # Tab 1: Compute
        compute_tab = self._create_compute_tab()
        tabs.addTab(compute_tab, "Cómputo")
        
        # Tab 2: UI
        ui_tab = self._create_ui_tab()
        tabs.addTab(ui_tab, "Interfaz")
        
        # Tab 3: Paths
        paths_tab = self._create_paths_tab()
        tabs.addTab(paths_tab, "Rutas")
        
        layout.addWidget(tabs)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.ok_btn = QPushButton("Aceptar")
        self.ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def _create_compute_tab(self):
        """Tab de configuración de cómputo"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # GPU Settings
        gpu_group = QGroupBox("Configuración GPU/CPU")
        gpu_layout = QFormLayout()
        
        # Use GPU checkbox
        self.use_gpu_check = QCheckBox()
        self.use_gpu_check.setEnabled(self.compute_engine.gpu_detector.cupy_available)
        gpu_layout.addRow("Usar GPU:", self.use_gpu_check)
        
        # GPU Info
        gpu_info = self.compute_engine.gpu_detector.get_device_info_string()
        gpu_info_label = QLabel(gpu_info)
        gpu_info_label.setWordWrap(True)
        gpu_layout.addRow("Dispositivo:", gpu_info_label)
        
        # Auto detect
        self.auto_detect_check = QCheckBox()
        gpu_layout.addRow("Auto-detectar:", self.auto_detect_check)
        
        # Fallback to CPU
        self.fallback_check = QCheckBox()
        gpu_layout.addRow("Fallback a CPU:", self.fallback_check)
        
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group)
        
        # Warning if GPU not available
        if not self.compute_engine.gpu_detector.cupy_available:
            warning = QLabel("⚠️ GPU no disponible. CuPy no está instalado o CUDA no fue detectado.")
            warning.setWordWrap(True)
            warning.setStyleSheet("color: orange; padding: 10px; background: #2b2b2b; border-radius: 5px;")
            layout.addWidget(warning)
        
        layout.addStretch()
        return widget
    
    def _create_ui_tab(self):
        """Tab de configuración de interfaz"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        ui_group = QGroupBox("Configuración de Interfaz")
        ui_layout = QFormLayout()
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        ui_layout.addRow("Tema:", self.theme_combo)
        
        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItems(["es", "en"])
        ui_layout.addRow("Idioma:", self.language_combo)
        
        # Default zoom
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 20)
        ui_layout.addRow("Zoom predeterminado:", self.zoom_spin)
        
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)
        
        layout.addStretch()
        return widget
    
    def _create_paths_tab(self):
        """Tab de rutas"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        paths_group = QGroupBox("Rutas del Sistema")
        paths_layout = QFormLayout()
        
        terrain_label = QLabel(self.config.settings['paths'].get('terrain_data', 'N/A'))
        terrain_label.setWordWrap(True)
        paths_layout.addRow("Datos de terreno:", terrain_label)
        
        exports_label = QLabel(self.config.settings['paths'].get('exports', 'N/A'))
        exports_layout.setWordWrap(True)
        paths_layout.addRow("Exportaciones:", exports_label)
        
        logs_label = QLabel(self.config.settings['paths'].get('logs', 'N/A'))
        logs_label.setWordWrap(True)
        paths_layout.addRow("Logs:", logs_label)
        
        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)
        
        layout.addStretch()
        return widget
    
    def _load_current_settings(self):
        """Carga la configuración actual"""
        compute_settings = self.config.settings.get('compute', {})
        ui_settings = self.config.settings.get('ui', {})
        
        # Compute
        self.use_gpu_check.setChecked(compute_settings.get('use_gpu', True))
        self.auto_detect_check.setChecked(compute_settings.get('auto_detect', True))
        self.fallback_check.setChecked(compute_settings.get('fallback_to_cpu', True))
        
        # UI
        theme = ui_settings.get('theme', 'dark')
        index = self.theme_combo.findText(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        
        lang = self.config.settings['application'].get('language', 'es')
        index = self.language_combo.findText(lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        
        self.zoom_spin.setValue(ui_settings.get('map_default_zoom', 13))
    
    def get_settings(self):
        """Retorna la configuración actualizada"""
        # Actualizar settings
        self.config.settings['compute']['use_gpu'] = self.use_gpu_check.isChecked()
        self.config.settings['compute']['auto_detect'] = self.auto_detect_check.isChecked()
        self.config.settings['compute']['fallback_to_cpu'] = self.fallback_check.isChecked()
        
        self.config.settings['ui']['theme'] = self.theme_combo.currentText()
        self.config.settings['application']['language'] = self.language_combo.currentText()
        self.config.settings['ui']['map_default_zoom'] = self.zoom_spin.value()
        
        return self.config.settings
    
    def accept(self):
        """Guardar y cerrar"""
        old_use_gpu = self.compute_engine.use_gpu
        new_use_gpu = self.use_gpu_check.isChecked()
        
        # Aplicar cambio de GPU si es diferente
        if old_use_gpu != new_use_gpu:
            success = self.compute_engine.switch_compute_mode(new_use_gpu)
            if not success:
                QMessageBox.warning(self, "Advertencia", 
                                   "No se pudo cambiar a modo GPU. Continuando con CPU.")
            else:
                mode = "GPU" if new_use_gpu else "CPU"
                self.logger.info(f"Compute mode changed to {mode}")
        
        # Guardar configuración
        self.config.save_settings(self.get_settings())
        
        super().accept()