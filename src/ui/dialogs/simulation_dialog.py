from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

class SimulationDialog(QDialog):
    def __init__(self, antennas, parent=None):
        super().__init__(parent)
        self.antennas = antennas
        self.setWindowTitle("Configurar Simulación")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Simular {len(antennas)} antena(s)"))
        
        ok_btn = QPushButton("Ejecutar")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
    
    def get_config(self):
        return {
            'model': 'okumura_hata',
            'resolution': 100
        }