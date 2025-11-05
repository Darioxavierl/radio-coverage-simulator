from PyQt6.QtCore import QObject
import logging

class ProjectManager(QObject):
    """Gestor temporal de proyectos"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ProjectManager")