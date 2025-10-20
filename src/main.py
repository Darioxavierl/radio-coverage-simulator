import sys
import os

from PyQt6.QtWidgets import QApplication

from gui.main.app_main import MainWindow
from utils.logger import setup_logger
from utils.hardware_check import get_compute_backend

if __name__ == "__main__":
    logger = setup_logger(__name__)
    logger.info("Iniciando simulador...")
    xp = get_compute_backend(logger=logger)
    app = QApplication(sys.argv)
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    window = MainWindow(ROOT_DIR, logger)
    window.show()
    sys.exit(app.exec())