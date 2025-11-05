from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
import logging

class SplashScreen(QSplashScreen):
    def __init__(self):
        # Puedes crear una imagen o usar color sólido
        pixmap = QPixmap(600, 400)
        pixmap.fill(Qt.GlobalColor.darkBlue)
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.show()
    
    def update_status(self, message: str):
        """Actualiza mensaje en splash"""
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            Qt.GlobalColor.white
        )
        logging.info(f"Splash: {message}")