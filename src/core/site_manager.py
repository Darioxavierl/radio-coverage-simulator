from PyQt6.QtCore import QObject, pyqtSignal
import logging

class SiteManager(QObject):
    """Gestor temporal de sitios"""
    
    site_added = pyqtSignal(str)
    site_removed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.sites = {}
        self.logger = logging.getLogger("SiteManager")
    
    def get_all_sites(self):
        return list(self.sites.values())