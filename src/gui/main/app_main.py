from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
from gui.main.app_main_functions import Functions
from settings.settings import Settings


class MainWindow(QMainWindow):
    """
    Ventana Principal
    """
    def __init__(self, root_path, logger):
        super().__init__()
        self.root_path = root_path
        self.settings = Settings(f"{self.root_path}/config/main.json")
        self.funciones = Functions(self)
        self.logger = logger

        self.setWindowTitle(self.settings.main.title)
        self.resize(self.settings.main.width, self.settings.main.height)

        self.show_frame()

    def show_frame(self):
        '''
        Inicializa los widgets de la ventana principal
        '''
        self.logger.info("[MainWindow] Construyendo layout principal...")
        self.layout = QVBoxLayout()
        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)
        
