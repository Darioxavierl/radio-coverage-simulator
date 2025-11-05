from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
                             QPushButton, QGroupBox, QLabel, QTabWidget, QWidget)
from PyQt6.QtCore import Qt
from src.models.antenna import Antenna, Technology, AntennaType
import logging

class AntennaPropertiesDialog(QDialog):
    """Diálogo de propiedades de antena"""
    
    def __init__(self, antenna: Antenna, parent=None):
        super().__init__(parent)
        self.antenna = antenna
        self.logger = logging.getLogger("AntennaPropertiesDialog")
        
        self.setWindowTitle(f"Propiedades - {antenna.name}")
        self.setMinimumSize(500, 600)
        
        self._setup_ui()
        self._load_values()
    
    def _setup_ui(self):
        """Configura la interfaz"""
        layout = QVBoxLayout(self)
        
        # Tabs para organizar parámetros
        tabs = QTabWidget()
        
        # Tab 1: General
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Tab 2: RF Parameters
        rf_tab = self._create_rf_tab()
        tabs.addTab(rf_tab, "Parámetros RF")
        
        # Tab 3: Antenna Pattern
        pattern_tab = self._create_pattern_tab()
        tabs.addTab(pattern_tab, "Patrón de Antena")
        
        layout.addWidget(tabs)
        
        # Botones
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("Aceptar")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Tab de información general"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Nombre
        self.name_edit = QLineEdit()
        layout.addRow("Nombre:", self.name_edit)
        
        # Ubicación
        location_group = QGroupBox("Ubicación")
        loc_layout = QFormLayout()
        
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90, 90)
        self.lat_spin.setDecimals(6)
        loc_layout.addRow("Latitud:", self.lat_spin)
        
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setDecimals(6)
        loc_layout.addRow("Longitud:", self.lon_spin)
        
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(1, 200)
        self.height_spin.setSuffix(" m")
        self.height_spin.setDecimals(1)
        loc_layout.addRow("Altura sobre suelo:", self.height_spin)
        
        location_group.setLayout(loc_layout)
        layout.addRow(location_group)
        
        # Notas
        self.notes_edit = QLineEdit()
        layout.addRow("Notas:", self.notes_edit)
        
        return widget
    
    def _create_rf_tab(self) -> QWidget:
        """Tab de parámetros RF"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Tecnología
        self.technology_combo = QComboBox()
        for tech in Technology:
            self.technology_combo.addItem(tech.value, tech)
        layout.addRow("Tecnología:", self.technology_combo)
        
        # Frecuencia
        self.frequency_spin = QDoubleSpinBox()
        self.frequency_spin.setRange(30, 100000)
        self.frequency_spin.setSuffix(" MHz")
        self.frequency_spin.setDecimals(1)
        layout.addRow("Frecuencia:", self.frequency_spin)
        
        # Ancho de banda
        self.bandwidth_spin = QDoubleSpinBox()
        self.bandwidth_spin.setRange(1, 100)
        self.bandwidth_spin.setSuffix(" MHz")
        self.bandwidth_spin.setDecimals(1)
        layout.addRow("Ancho de banda:", self.bandwidth_spin)
        
        # Potencia TX
        self.tx_power_spin = QDoubleSpinBox()
        self.tx_power_spin.setRange(0, 80)
        self.tx_power_spin.setSuffix(" dBm")
        self.tx_power_spin.setDecimals(1)
        layout.addRow("Potencia TX:", self.tx_power_spin)
        
        # Info adicional
        info_label = QLabel(
            "<small><b>Referencia de potencias:</b><br>"
            "- Macro GSM/LTE: 43-46 dBm<br>"
            "- Micro: 37-40 dBm<br>"
            "- Pico/Femto: 20-30 dBm</small>"
        )
        info_label.setStyleSheet("color: gray; padding: 10px;")
        layout.addRow(info_label)
        
        return widget
    
    def _create_pattern_tab(self) -> QWidget:
        """Tab de patrón de antena"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Tipo de antena
        self.antenna_type_combo = QComboBox()
        for ant_type in AntennaType:
            self.antenna_type_combo.addItem(ant_type.value.title(), ant_type)
        layout.addRow("Tipo:", self.antenna_type_combo)
        
        # Ganancia
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0, 30)
        self.gain_spin.setSuffix(" dBi")
        self.gain_spin.setDecimals(1)
        layout.addRow("Ganancia:", self.gain_spin)
        
        # Orientación
        orientation_group = QGroupBox("Orientación")
        orient_layout = QFormLayout()
        
        self.azimuth_spin = QDoubleSpinBox()
        self.azimuth_spin.setRange(0, 360)
        self.azimuth_spin.setSuffix(" °")
        self.azimuth_spin.setDecimals(1)
        self.azimuth_spin.setWrapping(True)
        orient_layout.addRow("Azimuth:", self.azimuth_spin)
        
        self.mech_tilt_spin = QDoubleSpinBox()
        self.mech_tilt_spin.setRange(-20, 20)
        self.mech_tilt_spin.setSuffix(" °")
        self.mech_tilt_spin.setDecimals(1)
        orient_layout.addRow("Tilt mecánico:", self.mech_tilt_spin)
        
        self.elec_tilt_spin = QDoubleSpinBox()
        self.elec_tilt_spin.setRange(-20, 20)
        self.elec_tilt_spin.setSuffix(" °")
        self.elec_tilt_spin.setDecimals(1)
        orient_layout.addRow("Tilt eléctrico:", self.elec_tilt_spin)
        
        orientation_group.setLayout(orient_layout)
        layout.addRow(orientation_group)
        
        # Beamwidth
        beam_group = QGroupBox("Patrón de radiación")
        beam_layout = QFormLayout()
        
        self.h_beamwidth_spin = QDoubleSpinBox()
        self.h_beamwidth_spin.setRange(30, 360)
        self.h_beamwidth_spin.setSuffix(" °")
        self.h_beamwidth_spin.setDecimals(1)
        beam_layout.addRow("Beamwidth horizontal:", self.h_beamwidth_spin)
        
        self.v_beamwidth_spin = QDoubleSpinBox()
        self.v_beamwidth_spin.setRange(1, 90)
        self.v_beamwidth_spin.setSuffix(" °")
        self.v_beamwidth_spin.setDecimals(1)
        beam_layout.addRow("Beamwidth vertical:", self.v_beamwidth_spin)
        
        beam_group.setLayout(beam_layout)
        layout.addRow(beam_group)
        
        return widget
    
    def _load_values(self):
        """Carga valores actuales de la antena"""
        # General
        self.name_edit.setText(self.antenna.name)
        self.lat_spin.setValue(self.antenna.latitude)
        self.lon_spin.setValue(self.antenna.longitude)
        self.height_spin.setValue(self.antenna.height_agl)
        self.notes_edit.setText(self.antenna.notes)
        
        # RF
        tech_index = self.technology_combo.findData(self.antenna.technology)
        if tech_index >= 0:
            self.technology_combo.setCurrentIndex(tech_index)
        
        self.frequency_spin.setValue(self.antenna.frequency_mhz)
        self.bandwidth_spin.setValue(self.antenna.bandwidth_mhz)
        self.tx_power_spin.setValue(self.antenna.tx_power_dbm)
        
        # Pattern
        type_index = self.antenna_type_combo.findData(self.antenna.antenna_type)
        if type_index >= 0:
            self.antenna_type_combo.setCurrentIndex(type_index)
        
        self.gain_spin.setValue(self.antenna.gain_dbi)
        self.azimuth_spin.setValue(self.antenna.azimuth)
        self.mech_tilt_spin.setValue(self.antenna.mechanical_tilt)
        self.elec_tilt_spin.setValue(self.antenna.electrical_tilt)
        self.h_beamwidth_spin.setValue(self.antenna.horizontal_beamwidth)
        self.v_beamwidth_spin.setValue(self.antenna.vertical_beamwidth)
    
    def get_properties(self) -> dict:
        """Retorna propiedades actualizadas"""
        return {
            'name': self.name_edit.text(),
            'latitude': self.lat_spin.value(),
            'longitude': self.lon_spin.value(),
            'height_agl': self.height_spin.value(),
            'notes': self.notes_edit.text(),
            'technology': self.technology_combo.currentData(),
            'frequency_mhz': self.frequency_spin.value(),
            'bandwidth_mhz': self.bandwidth_spin.value(),
            'tx_power_dbm': self.tx_power_spin.value(),
            'antenna_type': self.antenna_type_combo.currentData(),
            'gain_dbi': self.gain_spin.value(),
            'azimuth': self.azimuth_spin.value(),
            'mechanical_tilt': self.mech_tilt_spin.value(),
            'electrical_tilt': self.elec_tilt_spin.value(),
            'horizontal_beamwidth': self.h_beamwidth_spin.value(),
            'vertical_beamwidth': self.v_beamwidth_spin.value()
        }