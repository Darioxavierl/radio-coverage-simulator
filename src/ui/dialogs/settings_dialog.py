from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

class SettingsDialog(QDialog):
    def __init__(self, config, compute_engine, parent=None):
        super().__init__(parent)
        self.config = config
        self.compute_engine = compute_engine
        self.setWindowTitle("Configuración")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Diálogo de configuración (TODO)"))
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
    
    def get_settings(self):
        return self.config.settings