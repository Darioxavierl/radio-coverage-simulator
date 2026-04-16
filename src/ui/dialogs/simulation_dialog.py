from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                             QComboBox, QSpinBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QDoubleSpinBox, QCheckBox)
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
        self.model_combo.addItem("COST-231 Walfisch-Ikegami", "cost231")
        self.model_combo.addItem("ITU-R P.1546", "itu_p1546")
        self.model_combo.addItem("3GPP TR 38.901", "three_gpp_38901")
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

        # Grupo de parámetros de COST-231 (solo visible cuando se selecciona)
        self.cost231_params_group = QGroupBox("Parámetros de COST-231 Walfisch-Ikegami")
        cost231_layout = QFormLayout()

        # Altura de edificios
        self.building_height_spin = QDoubleSpinBox()
        self.building_height_spin.setRange(5.0, 40.0)
        self.building_height_spin.setValue(15.0)
        self.building_height_spin.setSingleStep(1.0)
        self.building_height_spin.setSuffix(" m")
        self.building_height_spin.setToolTip("Altura típica de edificios en el área (para Cuenca: ~15m)")
        cost231_layout.addRow("Altura edificios:", self.building_height_spin)

        # Ancho de calle
        self.street_width_spin = QDoubleSpinBox()
        self.street_width_spin.setRange(5.0, 50.0)
        self.street_width_spin.setValue(12.0)
        self.street_width_spin.setSingleStep(1.0)
        self.street_width_spin.setSuffix(" m")
        self.street_width_spin.setToolTip("Ancho típico de calles (para Cuenca: ~12m)")
        cost231_layout.addRow("Ancho calle:", self.street_width_spin)

        # Orientación de calle
        self.street_orientation_spin = QDoubleSpinBox()
        self.street_orientation_spin.setRange(0.0, 90.0)
        self.street_orientation_spin.setValue(0.0)
        self.street_orientation_spin.setSingleStep(5.0)
        self.street_orientation_spin.setSuffix(" °")
        self.street_orientation_spin.setToolTip("Orientación de calle respecto a TX-RX (0°=alineada, 90°=perpendicular)")
        cost231_layout.addRow("Orientación calle:", self.street_orientation_spin)

        # Nota informativa
        cost231_note = QLabel("<small><i>Modelo para urban canyon. Considera difracción rooftop-to-street. "
                             "Frecuencias 800-2000 MHz, distancias 20m-5km.</i></small>")
        cost231_note.setWordWrap(True)
        cost231_note.setStyleSheet("color: #666; margin-top: 5px;")
        cost231_layout.addRow("", cost231_note)

        self.cost231_params_group.setLayout(cost231_layout)
        self.cost231_params_group.setVisible(False)  # Oculto por defecto
        layout.addWidget(self.cost231_params_group)

        # Grupo de parámetros de ITU-R P.1546 (solo visible cuando se selecciona)
        self.itu_p1546_params_group = QGroupBox("Parámetros de ITU-R P.1546")
        itu_p1546_layout = QFormLayout()

        # Tipo de ambiente
        self.itu_p1546_environment_combo = QComboBox()
        self.itu_p1546_environment_combo.addItem("Urbano (Urban)", "Urban")
        self.itu_p1546_environment_combo.addItem("Suburbano (Suburban)", "Suburban")
        self.itu_p1546_environment_combo.addItem("Rural (Open Area)", "Rural")
        self.itu_p1546_environment_combo.setCurrentIndex(0)
        itu_p1546_layout.addRow("Ambiente:", self.itu_p1546_environment_combo)

        # Tipo de terreno
        self.itu_p1546_terrain_combo = QComboBox()
        self.itu_p1546_terrain_combo.addItem("Suave (Smooth)", "smooth")
        self.itu_p1546_terrain_combo.addItem("Mixto (Mixed)", "mixed")
        self.itu_p1546_terrain_combo.addItem("Irregular (Irregular)", "irregular")
        self.itu_p1546_terrain_combo.setCurrentIndex(1)
        itu_p1546_layout.addRow("Terreno:", self.itu_p1546_terrain_combo)

        # Nota informativa
        itu_p1546_note = QLabel("<small><i>Modelo point-to-area para cobertura. "
                                "Frecuencias 30-4000 MHz, distancias 1-1000 km. "
                                "LOS/NLOS determinado automáticamente por radio horizon.</i></small>")
        itu_p1546_note.setWordWrap(True)
        itu_p1546_note.setStyleSheet("color: #666; margin-top: 5px;")
        itu_p1546_layout.addRow("", itu_p1546_note)

        self.itu_p1546_params_group.setLayout(itu_p1546_layout)
        self.itu_p1546_params_group.setVisible(False)  # Oculto por defecto
        layout.addWidget(self.itu_p1546_params_group)

        # Grupo de parámetros de 3GPP TR 38.901 (solo visible cuando se selecciona)
        self.three_gpp_params_group = QGroupBox("Parámetros de 3GPP TR 38.901")
        three_gpp_layout = QFormLayout()

        # Escenario (UMa, UMi, RMa)
        self.three_gpp_scenario_combo = QComboBox()
        self.three_gpp_scenario_combo.addItem("Urbano Macro (UMa)", "UMa")
        self.three_gpp_scenario_combo.addItem("Urbano Micro (UMi)", "UMi")
        self.three_gpp_scenario_combo.addItem("Rural Macro (RMa)", "RMa")
        self.three_gpp_scenario_combo.setCurrentIndex(0)
        three_gpp_layout.addRow("Escenario:", self.three_gpp_scenario_combo)

        # Altura de Base Station
        self.three_gpp_bs_height_spin = QDoubleSpinBox()
        self.three_gpp_bs_height_spin.setRange(5.0, 60.0)
        self.three_gpp_bs_height_spin.setValue(25.0)
        self.three_gpp_bs_height_spin.setSingleStep(1.0)
        self.three_gpp_bs_height_spin.setSuffix(" m")
        self.three_gpp_bs_height_spin.setToolTip("Altura de la estación base (típicamente 25m para UMa, 10m para UMi)")
        three_gpp_layout.addRow("Altura BS:", self.three_gpp_bs_height_spin)

        # Altura de User Equipment
        self.three_gpp_ue_height_spin = QDoubleSpinBox()
        self.three_gpp_ue_height_spin.setRange(1.0, 3.0)
        self.three_gpp_ue_height_spin.setValue(1.5)
        self.three_gpp_ue_height_spin.setSingleStep(0.1)
        self.three_gpp_ue_height_spin.setSuffix(" m")
        self.three_gpp_ue_height_spin.setToolTip("Altura del terminal móvil (típicamente 1.5m)")
        three_gpp_layout.addRow("Altura UE:", self.three_gpp_ue_height_spin)

        # Modo determinista con terreno
        self.three_gpp_dem_checkbox = QCheckBox("Usar DEM (Modo Determinista)")
        self.three_gpp_dem_checkbox.setChecked(False)
        self.three_gpp_dem_checkbox.setToolTip("Integrar datos de elevación del terreno para correcciones de difracción (más realista pero más lento)")
        three_gpp_layout.addRow(self.three_gpp_dem_checkbox)

        # Nota informativa
        three_gpp_note = QLabel("<small><i>Modelo 5G point-to-area con LOS/NLOS probabilístico. "
                                "Frecuencias 0.5-100 GHz, distancias 10m-10km. "
                                "Diseñado para bandas n78 (3.5GHz), n257 (28GHz) y n258 (73GHz).</i></small>")
        three_gpp_note.setWordWrap(True)
        three_gpp_note.setStyleSheet("color: #666; margin-top: 5px;")
        three_gpp_layout.addRow("", three_gpp_note)

        self.three_gpp_params_group.setLayout(three_gpp_layout)
        self.three_gpp_params_group.setVisible(False)  # Oculto por defecto
        layout.addWidget(self.three_gpp_params_group)
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

        # Mostrar/ocultar parámetros según el modelo seleccionado
        model_key = self.model_combo.currentData()
        self.okumura_params_group.setVisible(model_key == 'okumura_hata')
        self.cost231_params_group.setVisible(model_key == 'cost231')
        self.itu_p1546_params_group.setVisible(model_key == 'itu_p1546')
        self.three_gpp_params_group.setVisible(model_key == 'three_gpp_38901')

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
                           'Considera altura de antena, tipo de ambiente y elevación del terreno.',
            'cost231': 'Modelo semi-determinístico para urban canyon. '
                      'Análisis de difracción Walfisch-Ikegami. '
                      'Válido para frecuencias 800-2000 MHz, distancias 20m-5km. '
                      'Considera altura de edificios, ancho de calles y orientación.',
            'itu_p1546': 'Modelo point-to-area empírico ITU-R. '
                        'Válido para frecuencias 30-4000 MHz y distancias 1-1000 km. '
                        'LOS/NLOS determinado automáticamente. Aplicable a radiodifusión, móviles y punto fijo.',
            'three_gpp_38901': 'Modelo 5G de 3GPP TR 38.901 con LOS/NLOS probabilístico. '
                              'Válido para frecuencias 0.5-100 GHz y distancias 10m-10km. '
                              'Soporta escenarios UMa, UMi y RMa. Optimizado para bandas n78, n257, n258.'
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

        # Agregar parámetros de COST-231 si está seleccionado
        if self.model_combo.currentData() == 'cost231':
            config['building_height'] = self.building_height_spin.value()
            config['street_width'] = self.street_width_spin.value()
            config['street_orientation'] = self.street_orientation_spin.value()

        # Agregar parámetros de ITU-R P.1546 si está seleccionado
        if self.model_combo.currentData() == 'itu_p1546':
            config['environment'] = self.itu_p1546_environment_combo.currentData()
            config['terrain_type'] = self.itu_p1546_terrain_combo.currentData()

        # Agregar parámetros de 3GPP TR 38.901 si está seleccionado
        if self.model_combo.currentData() == 'three_gpp_38901':
            config['scenario'] = self.three_gpp_scenario_combo.currentData()
            config['h_bs'] = self.three_gpp_bs_height_spin.value()
            config['h_ue'] = self.three_gpp_ue_height_spin.value()
            config['use_dem'] = self.three_gpp_dem_checkbox.isChecked()

        return config