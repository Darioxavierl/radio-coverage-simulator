from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                             QComboBox, QSpinBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from pathlib import Path

class SimulationDialog(QDialog):
    def __init__(self, antennas, parent=None):
        super().__init__(parent)
        self.antennas = antennas
        self.setWindowTitle("Configurar Simulación")
        self.setMinimumSize(500, 600)

        self._check_terrain()
        self._setup_ui()

    def _check_terrain(self):
        """Verifica si hay datos de terreno disponibles"""
        from core.terrain_loader import TerrainLoader

        self.terrain_available = False
        self.terrain_stats = {}

        terrain_file = Path('data/terrain/cuenca_terrain.tif')
        if terrain_file.exists():
            try:
                loader = TerrainLoader(str(terrain_file))
                if loader.is_loaded():
                    self.terrain_available = True
                    self.terrain_stats = loader.get_stats()
                    loader.close()
            except Exception:
                pass
    
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

        # Grupo de parámetros de Okumura-Hata (solo visible cuando se selecciona)
        self.okumura_params_group = QGroupBox("Parámetros de Okumura-Hata")
        okumura_layout = QFormLayout()

        # Tipo de ambiente
        self.environment_combo = QComboBox()
        self.environment_combo.addItem("Urbano (Urban)", "Urban")
        self.environment_combo.addItem("Suburbano (Suburban)", "Suburban")
        self.environment_combo.addItem("Rural (Open Area)", "Rural")
        self.environment_combo.setCurrentIndex(0)
        self.environment_combo.currentIndexChanged.connect(self._on_environment_changed)
        okumura_layout.addRow("Ambiente:", self.environment_combo)

        # Tipo de ciudad (solo para Urban)
        self.city_type_label = QLabel("Tipo de ciudad:")
        self.city_type_combo = QComboBox()
        self.city_type_combo.addItem("Ciudad Mediana/Pequeña", "medium")
        self.city_type_combo.addItem("Ciudad Grande (Metrópolis)", "large")
        self.city_type_combo.setCurrentIndex(0)
        okumura_layout.addRow(self.city_type_label, self.city_type_combo)

        # Altura del móvil
        self.mobile_height_spin = QDoubleSpinBox()
        self.mobile_height_spin.setRange(1.0, 10.0)
        self.mobile_height_spin.setValue(1.5)
        self.mobile_height_spin.setSingleStep(0.5)
        self.mobile_height_spin.setSuffix(" m")
        self.mobile_height_spin.setToolTip("Altura del receptor móvil (típicamente 1.5m para vehículos)")
        okumura_layout.addRow("Altura móvil:", self.mobile_height_spin)

        # Nota informativa
        info_note = QLabel("<small><i>Nota: El modelo usa la elevación del terreno para calcular altura efectiva de la antena</i></small>")
        info_note.setWordWrap(True)
        info_note.setStyleSheet("color: #666; margin-top: 5px;")
        okumura_layout.addRow("", info_note)

        self.okumura_params_group.setLayout(okumura_layout)
        self.okumura_params_group.setVisible(False)  # Oculto por defecto
        layout.addWidget(self.okumura_params_group)

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

        # Grupo de información del terreno
        terrain_group = QGroupBox("Datos de Terreno")
        terrain_layout = QVBoxLayout()

        if self.terrain_available:
            # Indicador de terreno disponible
            status_label = QLabel("<b style='color: green;'>[OK] Datos de elevación cargados</b>")
            terrain_layout.addWidget(status_label)

            # Estadísticas
            stats_text = f"Elevación: {self.terrain_stats.get('min', 0):.0f} - {self.terrain_stats.get('max', 0):.0f} m\n"
            stats_text += f"Promedio: {self.terrain_stats.get('mean', 0):.0f} m"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("color: #555; font-size: 10px;")
            terrain_layout.addWidget(stats_label)

            info_text = "<small><i>El modelo Okumura-Hata usará estos datos para calcular altura efectiva de la antena</i></small>"
        else:
            # Indicador de terreno no disponible
            status_label = QLabel("<b style='color: orange;'>[!] Sin datos de elevación</b>")
            terrain_layout.addWidget(status_label)

            info_text = "<small><i>Se asumirá terreno plano (elevación = 0m). Coloque 'cuenca_terrain.tif' en data/terrain/</i></small>"

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666;")
        terrain_layout.addWidget(info_label)

        terrain_group.setLayout(terrain_layout)
        layout.addWidget(terrain_group)

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

        # Mostrar/ocultar parámetros de Okumura-Hata
        model_key = self.model_combo.currentData()
        self.okumura_params_group.setVisible(model_key == 'okumura_hata')

        # Ajustar tamaño del diálogo
        self.adjustSize()

    def _on_environment_changed(self):
        """Actualiza visibilidad del tipo de ciudad según el ambiente"""
        environment = self.environment_combo.currentData()

        # El tipo de ciudad solo es relevante para Urban
        is_urban = (environment == 'Urban')
        self.city_type_label.setVisible(is_urban)
        self.city_type_combo.setVisible(is_urban)
    
    def _update_model_description(self):
        """Actualiza la descripción del modelo seleccionado"""
        model_key = self.model_combo.currentData()

        descriptions = {
            'free_space': 'Modelo teórico para propagación en espacio libre sin obstáculos. '
                         'Apropiado para enlaces punto a punto con línea de vista directa.',
            'okumura_hata': 'Modelo empírico para sistemas móviles celulares. '
                           'Válido para frecuencias 150-2000 MHz y distancias 1-20 km. '
                           'Considera altura de antena, tipo de ambiente y elevación del terreno.'
        }

        self.model_description.setText(descriptions.get(model_key, ''))

    def get_config(self):
        """Retorna la configuración seleccionada"""
        config = {
            'model': self.model_combo.currentData(),
            'radius_km': self.radius_spin.value(),
            'resolution': self.resolution_spin.value()
        }

        # Agregar parámetros de Okumura-Hata si está seleccionado
        if self.model_combo.currentData() == 'okumura_hata':
            config['environment'] = self.environment_combo.currentData()
            config['city_type'] = self.city_type_combo.currentData()
            config['mobile_height'] = self.mobile_height_spin.value()

        return config