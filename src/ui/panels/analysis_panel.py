from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class AnalysisPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Análisis (TODO)"))
    
    def update_results(self, results):
        pass