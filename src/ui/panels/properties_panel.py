from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Propiedades (TODO)"))
    
    def show_antenna_properties(self, antenna):
        pass