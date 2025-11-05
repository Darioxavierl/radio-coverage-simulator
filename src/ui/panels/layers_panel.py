from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class LayersPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Panel de Capas (TODO)"))