from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QDoubleSpinBox, QComboBox,
                             QPushButton, QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt
from src.models.site import Site
import logging


class SitePropertiesDialog(QDialog):
    """Diálogo de propiedades de sitio/emplazamiento."""

    SITE_TYPES = ["Macro", "Micro", "Pico", "Indoor"]
    ENVIRONMENTS = ["Urban", "Suburban", "Rural"]

    def __init__(self, site: Site, parent=None, antenna_manager=None):
        super().__init__(parent)
        self.site = site
        self.antenna_manager = antenna_manager
        self.logger = logging.getLogger("SitePropertiesDialog")

        self.setWindowTitle(f"Propiedades de sitio – {site.name}")
        self.setMinimumWidth(420)

        self._setup_ui()
        self._load_values()

    # ── Construcción de la UI ────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Grupo: Identificación ────────────────────────────────────────────
        id_group = QGroupBox("Identificación")
        id_form = QFormLayout(id_group)

        self.name_edit = QLineEdit()
        id_form.addRow("Nombre:", self.name_edit)

        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(6)
        id_form.addRow("Latitud:", self.lat_spin)

        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        self.lon_spin.setDecimals(6)
        id_form.addRow("Longitud:", self.lon_spin)

        layout.addWidget(id_group)

        # ── Grupo: Características físicas ───────────────────────────────────
        phys_group = QGroupBox("Características físicas")
        phys_form = QFormLayout(phys_group)

        self.elev_spin = QDoubleSpinBox()
        self.elev_spin.setRange(-500.0, 9000.0)
        self.elev_spin.setDecimals(1)
        self.elev_spin.setSuffix(" m s.n.m.")
        phys_form.addRow("Elevación del terreno:", self.elev_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0.0, 500.0)
        self.height_spin.setDecimals(1)
        self.height_spin.setSuffix(" m")
        phys_form.addRow("Altura de estructura:", self.height_spin)

        self.type_combo = QComboBox()
        self.type_combo.addItems(self.SITE_TYPES)
        phys_form.addRow("Tipo de sitio:", self.type_combo)

        self.env_combo = QComboBox()
        self.env_combo.addItems(self.ENVIRONMENTS)
        phys_form.addRow("Entorno:", self.env_combo)

        layout.addWidget(phys_group)

        # ── Grupo: Metadatos ─────────────────────────────────────────────────
        meta_group = QGroupBox("Metadatos")
        meta_form = QFormLayout(meta_group)

        self.address_edit = QLineEdit()
        meta_form.addRow("Dirección:", self.address_edit)

        self.notes_edit = QLineEdit()
        meta_form.addRow("Notas:", self.notes_edit)

        layout.addWidget(meta_group)

        # ── Grupo: Antenas asociadas ─────────────────────────────────────────
        if self.antenna_manager is not None:
            antennas = self.antenna_manager.get_all_antennas()
            ant_group = QGroupBox(f"Antenas asociadas  ({len(antennas)} disponibles)")
            ant_layout = QVBoxLayout(ant_group)

            self.antenna_list = QListWidget()
            self.antenna_list.setMaximumHeight(130)
            self.antenna_list.setToolTip("Marque las antenas que pertenecen a este sitio.")

            for antenna in antennas:
                label = f"{antenna.name}  —  {antenna.frequency_mhz:.0f} MHz"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, antenna.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if antenna.id in self.site.antenna_ids
                    else Qt.CheckState.Unchecked
                )
                self.antenna_list.addItem(item)

            ant_layout.addWidget(self.antenna_list)
            layout.addWidget(ant_group)
        else:
            self.antenna_list = None

        # ── Botones ──────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        ok_btn = QPushButton("Aceptar")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    # ── Datos ────────────────────────────────────────────────────────────────

    def _load_values(self):
        """Carga los valores actuales del sitio en los widgets."""
        self.name_edit.setText(self.site.name)
        self.lat_spin.setValue(self.site.latitude)
        self.lon_spin.setValue(self.site.longitude)
        self.elev_spin.setValue(self.site.ground_elevation)
        self.height_spin.setValue(self.site.structure_height)

        idx = self.type_combo.findText(self.site.site_type)
        self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)

        idx = self.env_combo.findText(self.site.environment)
        self.env_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self.address_edit.setText(self.site.address)
        self.notes_edit.setText(self.site.notes)

    def get_properties(self) -> dict:
        """Retorna los valores editados como diccionario para update_site()."""
        return {
            'name': self.name_edit.text().strip() or "Sitio sin nombre",
            'latitude': self.lat_spin.value(),
            'longitude': self.lon_spin.value(),
            'ground_elevation': self.elev_spin.value(),
            'structure_height': self.height_spin.value(),
            'site_type': self.type_combo.currentText(),
            'environment': self.env_combo.currentText(),
            'address': self.address_edit.text(),
            'notes': self.notes_edit.text(),
        }

    def get_selected_antenna_ids(self) -> list:
        """Retorna los IDs de antenas marcadas en la lista."""
        if self.antenna_list is None:
            return []
        result = []
        for i in range(self.antenna_list.count()):
            item = self.antenna_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result
