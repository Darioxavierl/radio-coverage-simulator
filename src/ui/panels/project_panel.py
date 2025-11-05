from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QMenu, QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
import logging

class ProjectPanel(QWidget):
    """Panel que muestra el árbol del proyecto"""
    
    # Señales
    antenna_selected = pyqtSignal(str)
    antenna_delete_requested = pyqtSignal(str)
    site_selected = pyqtSignal(str)
    
    def __init__(self, antenna_manager, site_manager, parent=None):
        super().__init__(parent)
        self.antenna_manager = antenna_manager
        self.site_manager = site_manager
        self.logger = logging.getLogger("ProjectPanel")
        
        self._setup_ui()
        self._connect_signals()
        self.refresh()
    
    def _setup_ui(self):
        """Configura la interfaz"""
        layout = QVBoxLayout(self)
        
        # Árbol del proyecto
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nombre", "Tipo"])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.add_site_btn = QPushButton("Agregar Sitio")
        self.add_site_btn.clicked.connect(self._add_site)
        button_layout.addWidget(self.add_site_btn)
        
        self.add_antenna_btn = QPushButton("Agregar Antena")
        self.add_antenna_btn.clicked.connect(self._add_antenna)
        button_layout.addWidget(self.add_antenna_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Conecta señales"""
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def refresh(self):
        """Refresca el contenido del árbol"""
        self.tree.clear()
        
        # Nodo raíz de sitios
        sites_root = QTreeWidgetItem(self.tree, ["Sitios", ""])
        sites_root.setExpanded(True)
        
        # Agregar sitios
        for site in self.site_manager.get_all_sites():
            site_item = QTreeWidgetItem(sites_root, [site.name, "Site"])
            site_item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'site', 'id': site.id})
            
            # Antenas del sitio
            for antenna_id in site.antenna_ids:
                antenna = self.antenna_manager.get_antenna(antenna_id)
                if antenna:
                    ant_item = QTreeWidgetItem(site_item, [antenna.name, "Antenna"])
                    ant_item.setData(0, Qt.ItemDataRole.UserRole, 
                                   {'type': 'antenna', 'id': antenna.id})
        
        # Nodo de antenas sin sitio
        orphan_root = QTreeWidgetItem(self.tree, ["Antenas Independientes", ""])
        orphan_root.setExpanded(True)
        
        for antenna in self.antenna_manager.get_all_antennas():
            if not antenna.site_id:
                ant_item = QTreeWidgetItem(orphan_root, [antenna.name, "Antenna"])
                ant_item.setData(0, Qt.ItemDataRole.UserRole,
                               {'type': 'antenna', 'id': antenna.id})
    
    def _on_item_clicked(self, item, column):
        """Maneja clic en item"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            if data['type'] == 'antenna':
                self.antenna_selected.emit(data['id'])
            elif data['type'] == 'site':
                self.site_selected.emit(data['id'])
    
    def _on_item_double_clicked(self, item, column):
        """Maneja doble clic en item"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            if data['type'] == 'antenna':
                self._show_properties(data['id'])
            elif data['type'] == 'site':
                # TODO: Abrir propiedades de sitio
                pass
    
    def _show_context_menu(self, position):
        """Muestra menú contextual"""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        menu = QMenu()
        
        if data['type'] == 'antenna':
            properties_action = QAction("Propiedades", self)
            properties_action.triggered.connect(lambda: self._show_properties(data['id']))
            menu.addAction(properties_action)
            
            duplicate_action = QAction("Duplicar", self)
            duplicate_action.triggered.connect(lambda: self._duplicate_antenna(data['id']))
            menu.addAction(duplicate_action)
            
            menu.addSeparator()
            
            delete_action = QAction("Eliminar", self)
            delete_action.triggered.connect(lambda: self.antenna_delete_requested.emit(data['id']))
            menu.addAction(delete_action)
        
        menu.exec(self.tree.viewport().mapToGlobal(position))
    
    def _add_site(self):
        """Agrega un nuevo sitio"""
        # TODO: Mostrar diálogo para crear sitio
        pass
    
    def _add_antenna(self):
        """Agrega una nueva antena"""
        # Emitir señal para activar modo agregar
        pass
    
    def _show_properties(self, entity_id):
        """Muestra propiedades de la entidad"""
        antenna = self.antenna_manager.get_antenna(entity_id)
        if antenna:
            from src.ui.dialogs.antenna_properties_dialog import AntennaPropertiesDialog
            
            # Obtener ventana principal como parent
            main_window = self.window()
            
            dialog = AntennaPropertiesDialog(antenna, main_window)
            
            if dialog.exec():
                # Actualizar propiedades
                updated_props = dialog.get_properties()
                self.antenna_manager.update_antenna(entity_id, **updated_props)
                self.refresh()
                
                self.logger.info(f"Antenna properties updated: {entity_id}")
    
    def _duplicate_antenna(self, antenna_id):
        """Duplica una antena"""
        new_id = self.antenna_manager.duplicate_antenna(antenna_id)
        if new_id:
            self.refresh()