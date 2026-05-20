import numpy as np
import base64
from io import BytesIO
import logging

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt


class LOSCalculator:
    """
    Calcula mapas de línea de visión (LOS) basados en el perfil del terreno DEM.

    Operación puramente geométrica: no depende del modelo de propagación.
    Reutiliza TerrainLoader.get_radial_profiles() que ya está vectorizado.

    Acepta un ComputeEngine opcional para usar CuPy (GPU) o NumPy (CPU) de forma
    transparente, siguiendo el mismo patrón que CoverageCalculator.
    """

    def __init__(self, compute_engine=None):
        self.logger = logging.getLogger("LOSCalculator")
        self.engine = compute_engine

    @property
    def xp(self):
        """Módulo de cómputo activo: NumPy o CuPy según la configuración del motor."""
        if self.engine is not None:
            return self.engine.xp
        return np

    def compute_los_map(self, tx_lat, tx_lon, tx_height_agl, tx_terrain_elev,
                        grid_lats, grid_lons, terrain_loader, n_samples=50):
        """
        Calcula el mapa LOS para una antena sobre una grilla de puntos receptores.

        Un punto es LOS si la línea recta TX→RX no es interceptada por el terreno
        en ningún punto intermedio del perfil de elevación.

        Args:
            tx_lat, tx_lon:     Coordenadas del transmisor (escalares)
            tx_height_agl:      Altura de la antena sobre el terreno [m AGL]
            tx_terrain_elev:    Elevación del terreno en el transmisor [m ASL]
            grid_lats:          Array 2D (H, W) de latitudes de la grilla
            grid_lons:          Array 2D (H, W) de longitudes de la grilla
            terrain_loader:     Instancia de TerrainLoader con datos DEM cargados
            n_samples:          Número de puntos de muestreo por perfil (default: 50)

        Returns:
            np.ndarray float32 (H, W): 1.0 = LOS visible, 0.0 = ocultado por terreno
        """
        if terrain_loader is None or not terrain_loader.is_loaded():
            self.logger.warning("Terreno no cargado — devolviendo mapa todo-LOS")
            return np.ones(grid_lats.shape, dtype=np.float32)

        H, W = grid_lats.shape

        # terrain_loader.get_radial_profiles() espera arrays NumPy
        use_gpu = self.engine is not None and self.engine.use_gpu
        if use_gpu:
            rx_lats_flat = self.xp.asnumpy(grid_lats).flatten()
            rx_lons_flat = self.xp.asnumpy(grid_lons).flatten()
        else:
            rx_lats_flat = np.asarray(grid_lats).flatten()
            rx_lons_flat = np.asarray(grid_lons).flatten()

        # Altura absoluta del TX [m ASL]
        z_tx = float(tx_terrain_elev) + float(tx_height_agl)

        # Perfiles de elevación TX→RX: shape (N, n_samples) — devuelto en NumPy
        profiles_np = terrain_loader.get_radial_profiles(
            tx_lat, tx_lon, rx_lats_flat, rx_lons_flat, n_samples
        )

        # Transferir al módulo de cómputo activo (GPU si disponible)
        profiles = self.xp.asarray(profiles_np)

        # Elevación del terreno en cada receptor [m ASL]
        z_rx = profiles[:, -1]  # (N,)

        # Parámetro lineal t ∈ [0, 1] a lo largo del perfil TX→RX
        t = self.xp.linspace(0.0, 1.0, n_samples)  # (n_samples,)

        # Línea de visión directa TX→RX:  z_los[i,j] = z_tx + t[j]*(z_rx[i] - z_tx)
        z_los = z_tx + t[None, :] * (z_rx[:, None] - z_tx)  # (N, n_samples)

        # Obstaculización: algún punto INTERMEDIO supera la línea directa
        # Se excluyen los extremos (j=0 = TX, j=-1 = RX) para evitar falsos positivos
        obstructed = self.xp.any(profiles[:, 1:-1] > z_los[:, 1:-1], axis=1)  # (N,)

        los_flat = (~obstructed).astype(self.xp.float32)

        # Devolver siempre NumPy: generate_los_image y los overlays necesitan CPU
        if use_gpu:
            los_np = self.xp.asnumpy(los_flat)
        else:
            los_np = np.asarray(los_flat)

        return los_np.reshape(H, W)

    def generate_los_image(self, los_map, alpha=0.7):
        """
        Genera imagen PNG del mapa LOS como data URL base64.

        Colores:
            Verde   (#00aa44): LOS — visibilidad directa con la antena
            Naranja (#ff6600): Sombra — bloqueado por el terreno

        Args:
            los_map:  Array 2D float32 (H, W); 1.0 = LOS, 0.0 = sombra
            alpha:    Transparencia global de la imagen (0.0–1.0)

        Returns:
            str: PNG como data URL (data:image/png;base64,...), o "" si hay error
        """
        H, W = los_map.shape
        rgba = np.zeros((H, W, 4), dtype=np.float32)

        los_mask = los_map > 0.5
        shadow_mask = ~los_mask

        # Verde: #00aa44 → (0, 170, 68) / 255
        rgba[los_mask, 0] = 0.0
        rgba[los_mask, 1] = 170 / 255.0
        rgba[los_mask, 2] = 68 / 255.0
        rgba[los_mask, 3] = alpha

        # Naranja: #ff6600 → (255, 102, 0) / 255
        rgba[shadow_mask, 0] = 1.0
        rgba[shadow_mask, 1] = 102 / 255.0
        rgba[shadow_mask, 2] = 0.0
        rgba[shadow_mask, 3] = alpha

        try:
            fig, ax = plt.subplots(figsize=(10, 10), dpi=100)
            ax.imshow(rgba, origin='lower', interpolation='nearest')
            ax.axis('off')
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight',
                        pad_inches=0, transparent=True)
            plt.close(fig)

            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode('utf-8')
            return f"data:image/png;base64,{b64}"

        except Exception as e:
            self.logger.error(f"Error generando imagen LOS: {e}")
            return ""
