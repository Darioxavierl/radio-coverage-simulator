from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QComboBox, QSpinBox, QFormLayout, QGroupBox,
                             QHBoxLayout)
from PyQt6.QtCore import Qt

class SimulationDialog(QDialog):
    def __init__(self, antennas, parent=None):
        super().__init__(parent)
        self.antennas = antennas
        self.setWindowTitle("Configurar Simulación")
        self.setMinimumSize(450, 350)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo"""
        layout = QVBoxLayout(self)
        
        # Información general
        info_label = QLabel(f"<b>Simular cobertura para {len(self.antennas)} antena(s)</b>")
        layout.addWidget(info_label)
        
        # Grupo de configuración del modelo
        model_group = QGroupBox("Modelo de Propagación")
        model_layout = QFormLayout()
        
        # Selector de modelo
        self.model_combo = QComboBox()
        self.model_combo.addItem("Free Space Path Loss", "free_space")
        self.model_combo.addItem("Okumura-Hata", "okumura_hata")
        self.model_combo.setCurrentIndex(0)  # Free Space por defecto
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addRow("Modelo:", self.model_combo)
        
        # Descripción del modelo
        self.model_description = QLabel()
        self.model_description.setWordWrap(True)
        self.model_description.setStyleSheet("color: gray; font-size: 10px;")
        self._update_model_description()
        model_layout.addRow("", self.model_description)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Grupo de parámetros de simulación
        params_group = QGroupBox("Parámetros de Simulación")
        params_layout = QFormLayout()
        
        # Radio de simulación
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(1, 50)
        self.radius_spin.setValue(5)
        self.radius_spin.setSuffix(" km")
        params_layout.addRow("Radio:", self.radius_spin)
        
        # Resolución del grid
        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(50, 500)
        self.resolution_spin.setValue(100)
        self.resolution_spin.setSingleStep(50)
        self.resolution_spin.setSuffix(" puntos")
        params_layout.addRow("Resolución:", self.resolution_spin)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        layout.addStretch()
        
        # Botones
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Ejecutar Simulación")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    def _on_model_changed(self):
        """Actualiza la descripción cuando cambia el modelo"""
        self._update_model_description()
    
    def _update_model_description(self):
        """Actualiza la descripción del modelo seleccionado"""
        model_key = self.model_combo.currentData()
        
        descriptions = {
            'free_space': 'Modelo teórico para propagación en espacio libre sin obstáculos. '
                         'Apropiado para enlaces punto a punto con línea de vista directa.',
            'okumura_hata': 'Modelo empírico para entornos urbanos y suburbanos. '
                           'Apropiado para frecuencias 150-1500 MHz y distancias 1-20 km.'
        }
        
        self.model_description.setText(descriptions.get(model_key, ''))
    
    def get_config(self):
        """Retorna la configuración seleccionada"""
        return {
            'model': self.model_combo.currentData(),
            'radius_km': self.radius_spin.value(),
            'resolution': self.resolution_spin.value()
        }