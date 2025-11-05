import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
import logging

def main():
    # CRÍTICO: Configurar Qt ANTES de crear QApplication
    # Necesario para QtWebEngineWidgets
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    # Inicializar logging PRIMERO
    from utils.logger import setup_logger
    setup_logger()
    
    logging.info("="*50)
    logging.info("RF Coverage Tool - Starting")
    logging.info("="*50)
    
    app = QApplication(sys.argv)
    
    # Splash screen
    from ui.splash_screen import SplashScreen
    splash = SplashScreen()
    splash.update_status("Inicializando aplicación...")
    
    # Cargar configuración
    splash.update_status("Cargando configuración...")
    from utils.config_manager import ConfigManager
    config = ConfigManager()
    
    # Detectar GPU
    splash.update_status("Detectando hardware...")
    from utils.gpu_detector import GPUDetector
    gpu = GPUDetector()
    
    # Cargar modelos
    splash.update_status("Cargando modelos de propagación...")
    # ... inicializar modelos
    
    # Crear ventana principal
    splash.update_status("Preparando interfaz...")
    from ui.main_window import MainWindow
    window = MainWindow(config, gpu)
    
    # Cerrar splash después de 2 segundos
    QTimer.singleShot(2000, splash.close)
    QTimer.singleShot(2000, window.show)
    
    logging.info("Application ready")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())