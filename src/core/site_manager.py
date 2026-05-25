from typing import Optional, Dict, List
from models.site import Site
from PyQt6.QtCore import QObject, pyqtSignal
import logging
import uuid


class SiteManager(QObject):
    """Gestor de sitios del proyecto"""

    site_added = pyqtSignal(str)    # site_id
    site_removed = pyqtSignal(str)  # site_id
    site_modified = pyqtSignal(str) # site_id

    def __init__(self):
        super().__init__()
        self.sites: Dict[str, Site] = {}
        self.logger = logging.getLogger("SiteManager")

    # ── Consultas ───────────────────────────────────────────────────────────

    def get_site(self, site_id: str) -> Optional[Site]:
        """Obtiene un sitio por su ID."""
        return self.sites.get(site_id)

    def get_all_sites(self) -> List[Site]:
        """Retorna lista de todos los sitios activos."""
        return list(self.sites.values())

    # ── Ciclo de vida ────────────────────────────────────────────────────────

    def add_site(self, site: Site) -> str:
        """Registra un sitio. Retorna el ID asignado."""
        self.sites[site.id] = site
        self.logger.info(f"Site added: {site.name} ({site.id})")
        self.site_added.emit(site.id)
        return site.id

    def create_site_at_location(self, lat: float, lon: float) -> str:
        """Crea un sitio genérico en las coordenadas indicadas y lo registra."""
        site = Site(
            latitude=lat,
            longitude=lon,
            name=f"Sitio {len(self.sites) + 1}",
        )
        return self.add_site(site)

    def update_site(self, site_id: str, **kwargs) -> bool:
        """Actualiza atributos de un sitio existente mediante setattr."""
        site = self.sites.get(site_id)
        if site is None:
            return False
        for key, value in kwargs.items():
            if hasattr(site, key):
                setattr(site, key, value)
        self.logger.info(f"Site updated: {site_id}")
        self.site_modified.emit(site_id)
        return True

    def remove_site(self, site_id: str, antenna_manager=None) -> bool:
        """Elimina el sitio y desvincula sus antenas (sin borrarlas).

        Si se proporciona *antenna_manager*, pone ``site_id=None`` en todas las
        antenas que referenciaban al sitio eliminado, manteniéndolas como
        antenas independientes.
        """
        site = self.sites.get(site_id)
        if site is None:
            return False

        # Desvincular antenas si se tiene acceso al AntennaManager
        if antenna_manager is not None:
            for ant_id in list(site.antenna_ids):
                antenna = antenna_manager.antennas.get(ant_id)
                if antenna is not None:
                    antenna.site_id = None

        del self.sites[site_id]
        self.logger.info(f"Site removed: {site_id}")
        self.site_removed.emit(site_id)
        return True

    # ── Gestión del vínculo Site ↔ Antenna ──────────────────────────────────

    def add_antenna_to_site(self, site_id: str, antenna_id: str) -> bool:
        """Añade una antena al sitio (lado Site.antenna_ids)."""
        site = self.sites.get(site_id)
        if site is None:
            return False
        if antenna_id not in site.antenna_ids:
            site.antenna_ids.append(antenna_id)
            self.site_modified.emit(site_id)
        return True

    def remove_antenna_from_site(self, site_id: str, antenna_id: str) -> bool:
        """Quita una antena del sitio (lado Site.antenna_ids)."""
        site = self.sites.get(site_id)
        if site is None:
            return False
        if antenna_id in site.antenna_ids:
            site.antenna_ids.remove(antenna_id)
            self.site_modified.emit(site_id)
        return True