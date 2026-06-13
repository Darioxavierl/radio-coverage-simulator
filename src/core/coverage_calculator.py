import time
import numpy as np
from typing import Dict, List, Tuple
from models.antenna import Antenna
from core.compute_engine import ComputeEngine
import logging

class CoverageCalculator:
    """Calcula mapas de cobertura para múltiples antenas"""
    
    def __init__(self, compute_engine: ComputeEngine):
        self.engine = compute_engine
        self.logger = logging.getLogger("CoverageCalculator")
    
    @property
    def xp(self):
        """Acceso dinámico al módulo de cómputo actual"""
        return self.engine.xp
    
    def calculate_single_antenna_coverage(
        self,
        antenna: Antenna,
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model,
        model_params: dict = None,
        return_details: bool = False,
        terrain_loader=None,
        pathloss_timer_out: dict = None,
    ) -> np.ndarray:
        """
        Calcula cobertura para una antena

        Args:
            antenna: Objeto Antenna
            grid_lats: Array 2D con latitudes del grid
            grid_lons: Array 2D con longitudes del grid
            terrain_heights: Array 2D con elevaciones del terreno
            model: Modelo de propagación
            model_params: Parámetros adicionales para el modelo
            return_details: Si es True, retorna también path loss y ganancia

        Returns:
            Array 2D con RSRP en dBm para cada punto del grid o un dict detallado
        """
        self.logger.info(f"Calculating coverage for {antenna.name}")

        # Valores por defecto para model_params
        if model_params is None:
            model_params = {}

        # Convertir a GPU si está disponible
        # float32: activa FP32 nativo en GPU (33x más rápido que FP64 emulado en GTX 1660)
        # Precisión suficiente: path loss en dB, error físico ±2-5 dB >> error float32 (~1e-6)
        if self.engine.use_gpu:
            grid_lats       = self.xp.asarray(grid_lats,       dtype=self.xp.float32)
            grid_lons       = self.xp.asarray(grid_lons,       dtype=self.xp.float32)
            terrain_heights = self.xp.asarray(terrain_heights, dtype=self.xp.float32)

        # Calcular distancias
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats, grid_lons
        )

        # Obtener elevación del terreno en la ubicación de la antena
        if terrain_loader is not None and terrain_loader.is_loaded():
            tx_elevation = terrain_loader.get_elevation(antenna.latitude, antenna.longitude)
            self.logger.info(f"Antenna elevation: {tx_elevation:.1f} m MSL")
        else:
            tx_elevation = 0.0  # Default si no hay terrain_loader
            self.logger.info(f"Antenna elevation: {tx_elevation} m MSL (default - no terrain_loader)")

        # Preparar parámetros para model.calculate_path_loss
        path_loss_args = {
            'distances': distances,
            'frequency': antenna.frequency_mhz,
            'tx_height': antenna.height_agl,
            'tx_elevation': tx_elevation,
            'terrain_heights': terrain_heights
        }

        # Calcular perfiles radiales y distancias reales si hay TerrainLoader disponible
        if terrain_loader is not None and terrain_loader.is_loaded():
            gl = self.xp.asnumpy(grid_lats) if self.engine.use_gpu else grid_lats
            gl_lons = self.xp.asnumpy(grid_lons) if self.engine.use_gpu else grid_lons
            self.logger.info(f"Before get_radial_profiles: gl.shape={gl.shape}, gl.ravel().shape={gl.ravel().shape}")
            
            # ✅ FIX ITU: Detectar si es ITU-R P.1546 para extender perfiles hasta 15 km (SOLO para este modelo)
            model_class_name = model.__class__.__name__ if hasattr(model, '__class__') else str(type(model))
            is_itu_p1546 = 'ITU' in model_class_name or 'itu' in model_class_name.lower() or 'p1546' in model_class_name.lower()
            max_dist = 15000 if is_itu_p1546 else None
            self.logger.info(f"Terrain profiles: model={model_class_name}, is_itu_p1546={is_itu_p1546}, max_distance_m={max_dist}")
            
            # FASE A4 FIX: Obtener perfiles radiales
            terrain_profiles = terrain_loader.get_radial_profiles(
                antenna.latitude, antenna.longitude,
                gl.ravel(), gl_lons.ravel(),
                max_distance_m=max_dist
            )
            self.logger.info(f"After get_radial_profiles: terrain_profiles.shape={terrain_profiles.shape}")
            
            # FASE A4 FIX (NUEVO): Obtener distancias Haversine REALES para cada muestra radial
            profile_distances = terrain_loader.get_profile_distances(
                antenna.latitude, antenna.longitude,
                gl.ravel(), gl_lons.ravel(),
                max_distance_m=max_dist
            )
            self.logger.info(f"After get_profile_distances: profile_distances.shape={profile_distances.shape}")
            
            # FASE 2 FIX (NUEVO): Obtener perfiles suavizados (Gaussian filter) para h_eff más estable
            smoothed_terrain_profiles = terrain_loader.get_smoothed_profiles(
                terrain_profiles,
                window_size_m=1000.0,
                profile_distances=profile_distances
            )
            self.logger.info(f"After get_smoothed_profiles: smoothed_terrain_profiles.shape={smoothed_terrain_profiles.shape}")
            
            # Convertir todos los parámetros al módulo correcto (NumPy o CuPy)
            # float32 consistente con grid_lats/lons para mantener precision uniforme en GPU
            terrain_profiles          = self.xp.asarray(terrain_profiles,          dtype=self.xp.float32)
            profile_distances         = self.xp.asarray(profile_distances,         dtype=self.xp.float32)
            smoothed_terrain_profiles = self.xp.asarray(smoothed_terrain_profiles, dtype=self.xp.float32)
            self.logger.info(f"After xp.asarray: terrain_profiles.shape={terrain_profiles.shape}, "
                           f"profile_distances.shape={profile_distances.shape}, "
                           f"smoothed_terrain_profiles.shape={smoothed_terrain_profiles.shape}")
            
            # PASO CRÍTICO: Pasar DEM parámetros reales al modelo (MÁXIMO REALISMO)
            path_loss_args['terrain_profiles'] = terrain_profiles
            path_loss_args['profile_distances'] = profile_distances
            path_loss_args['smoothed_terrain_profiles'] = smoothed_terrain_profiles
        else:
            self.logger.info(f"terrain_loader check: is_None={terrain_loader is None}, is_loaded={terrain_loader.is_loaded() if terrain_loader else 'N/A'}")

        # Agregar parámetros adicionales del modelo
        path_loss_args.update(model_params)

        # Calcular path loss usando modelo
        # Timer honesto: sincronizar cola GPU antes y despues para medir solo el kernel
        if self.engine.use_gpu:
            self.xp.cuda.Stream.null.synchronize()  # vaciar cola GPU pendiente
        _pl_t0 = time.perf_counter()

        result = model.calculate_path_loss(**path_loss_args)

        if self.engine.use_gpu:
            self.xp.cuda.Stream.null.synchronize()  # esperar que el kernel termine
        _pl_elapsed = round(time.perf_counter() - _pl_t0, 4)
        if pathloss_timer_out is not None:
            pathloss_timer_out['pathloss_s'] = _pl_elapsed

        # Algunos modelos retornan dict, otros ndarray directamente
        path_loss = result['path_loss'] if isinstance(result, dict) else result

        # Aplicar patrón de antena 3D (horizontal + vertical, 3GPP TR 38.901 §7.3.2)
        antenna_gain = self._apply_antenna_pattern(
            antenna, grid_lats, grid_lons,
            distances=distances,
            terrain_heights=terrain_heights,
            tx_elevation=tx_elevation
        )

        # RSRP = Tx Power + Antenna Gain - Path Loss
        rsrp = antenna.tx_power_dbm + antenna_gain - path_loss

        # OPTIMIZACION: Mantener en GPU si use_gpu=True (conversión al final en multi-antenna)
        # No conversión aquí

        if return_details:
            return {
                'rsrp': rsrp,
                'path_loss': path_loss,
                'antenna_gain': antenna_gain,
            }

        return rsrp
    
    def calculate_multi_antenna_coverage(
        self,
        antennas: List[Antenna],
        grid_lats: np.ndarray,
        grid_lons: np.ndarray,
        terrain_heights: np.ndarray,
        model,
        model_params: dict = None,
        precomputed_rsrp: Dict[str, np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """
        Calcula cobertura para múltiples antenas y determina el best server por píxel.

        Args:
            antennas: Lista de antenas
            grid_lats: Array 2D con latitudes del grid
            grid_lons: Array 2D con longitudes del grid
            terrain_heights: Array 2D con elevaciones del terreno
            model: Modelo de propagación
            model_params: Parámetros adicionales para el modelo
            precomputed_rsrp: Dict opcional {antenna_id -> rsrp_array_2D} con los arrays
                de RSRP ya calculados (e.g. por el SimulationWorker con terrain_loader y
                parámetros correctos por antena). Si se proporciona, se omite el recálculo
                interno y se agregan directamente estos arrays. Esto garantiza que el
                heatmap agregado sea el máximo pixel a pixel de los individuales correctos.

        Returns:
            Dict con:
            - 'best_server': ID de antena con mejor señal en cada punto
            - 'rsrp': RSRP de la mejor antena en cada punto
            - 'individual': Dict con cobertura de cada antena (rsrp arrays)
        """
        self.logger.info(f"Aggregating coverage for {len(antennas)} antennas "
                         f"({'precomputed' if precomputed_rsrp is not None else 'recalculating'})")

        results = {'individual': {}}

        if precomputed_rsrp is not None:
            # Usar los arrays ya calculados correctamente (con terrain_loader, tx_elevation real, etc.)
            # Se filtra por antenas habilitadas y con coverage activo, igual que la rama de recálculo.
            for antenna in antennas:
                if antenna.enabled and antenna.show_coverage and antenna.id in precomputed_rsrp:
                    results['individual'][antenna.id] = precomputed_rsrp[antenna.id]
        else:
            # Calcular cobertura individual desde cero (modo standalone / tests)
            for antenna in antennas:
                if antenna.enabled and antenna.show_coverage:
                    coverage = self.calculate_single_antenna_coverage(
                        antenna, grid_lats, grid_lons, terrain_heights, model, model_params
                    )
                    results['individual'][antenna.id] = coverage

        # Calcular best server (máximo RSRP en cada píxel)
        if results['individual']:
            coverage_stack = np.stack(list(results['individual'].values()))
            antenna_ids = list(results['individual'].keys())

            best_indices = np.argmax(coverage_stack, axis=0)
            results['rsrp'] = np.max(coverage_stack, axis=0)

            results['best_server'] = np.empty(best_indices.shape, dtype=object)
            for i, ant_id in enumerate(antenna_ids):
                mask = best_indices == i
                results['best_server'][mask] = ant_id

        return results
    
    def _calculate_distances(self, ant_lat, ant_lon, grid_lats, grid_lons):
        """Calcula distancias usando fórmula Haversine"""
        R = 6371000  # Radio tierra en metros
        
        lat1 = self.xp.radians(ant_lat)
        lon1 = self.xp.radians(ant_lon)
        lat2 = self.xp.radians(grid_lats)
        lon2 = self.xp.radians(grid_lons)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = self.xp.sin(dlat/2)**2 + self.xp.cos(lat1) * self.xp.cos(lat2) * self.xp.sin(dlon/2)**2
        c = 2 * self.xp.arctan2(self.xp.sqrt(a), self.xp.sqrt(1-a))
        
        return R * c
    
    def _apply_antenna_pattern(self, antenna: Antenna, grid_lats, grid_lons,
                               distances=None, terrain_heights=None, tx_elevation=0.0):
        """Aplica patrón de radiación 3D de la antena (horizontal + vertical).

        Implementa la aproximación gaussiana de 3GPP TR 38.901 §7.3.2, válida
        para todos los modelos de propagación (no exclusiva de 5G).

        Formula horizontal:
            A_H(φ) = -min[ 12·(φ / φ_3dB)², 30 dB ]
        Formula vertical (sólo cuando se pasan distances y terrain_heights):
            A_V(θ) = -min[ 12·((θ - θ_tilt) / θ_3dB)², 30 dB ]
        Patron total:
            G(φ,θ) = G_max - min[ -(A_H + A_V), 30 dB ]

        Args:
            antenna: Objeto Antenna con los parámetros RF.
            grid_lats: Array 2D con latitudes del grid.
            grid_lons: Array 2D con longitudes del grid.
            distances: Array 2D con distancias horizontales TX→RX en metros (Haversine).
                       Necesario para calcular el patrón vertical.
            terrain_heights: Array 2D con elevaciones del terreno en cada punto del grid (m MSL).
                             Necesario para calcular el ángulo de elevación al receptor.
            tx_elevation: Elevación del terreno en la posición de la antena (m MSL).
                          Se suma a height_agl para obtener la altura absoluta del TX.
        """
        # --- Patrón horizontal ---
        azimuth_to_points = self._calculate_azimuths(
            antenna.latitude, antenna.longitude,
            grid_lats, grid_lons
        )

        angle_diff = self.xp.abs(azimuth_to_points - antenna.azimuth)
        angle_diff = self.xp.minimum(angle_diff, 360 - angle_diff)

        if antenna.antenna_type.value == "omnidirectional":
            # Sin variación azimutal ni vertical; ganancia isotrópica en todas las direcciones
            return antenna.gain_dbi + self.xp.zeros_like(angle_diff)

        # Atenuación horizontal — denominador = beamwidth completo (3GPP TR 38.901 §7.3.2)
        h_atten = -self.xp.minimum(
            12 * (angle_diff / antenna.horizontal_beamwidth) ** 2,
            30.0
        )

        # --- Patrón vertical (sólo con información de distancia/terreno) ---
        if distances is not None and terrain_heights is not None:
            h_tx_abs = float(tx_elevation) + antenna.height_agl
            delta_h = h_tx_abs - terrain_heights  # positivo cuando TX está por encima del RX

            # Ángulo de elevación TX→RX: positivo cuando RX está por debajo del TX
            elevation_angle = self.xp.degrees(
                self.xp.arctan2(delta_h, self.xp.maximum(distances, 1.0))
            )

            # Tilt efectivo total (positivo = apuntando hacia abajo)
            effective_tilt = antenna.mechanical_tilt + antenna.electrical_tilt
            theta_diff = elevation_angle - effective_tilt

            v_atten = -self.xp.minimum(
                12 * (theta_diff / antenna.vertical_beamwidth) ** 2,
                30.0
            )

            # Patrón total 3D — cap conjunto a 30 dB (3GPP TR 38.901 §7.3.2)
            combined = -self.xp.minimum(-(h_atten + v_atten), 30.0)
        else:
            # Sin datos de terreno/distancia → sólo patrón horizontal (retrocompatible)
            combined = h_atten

        return antenna.gain_dbi + combined
    
    def _calculate_azimuths(self, ant_lat, ant_lon, grid_lats, grid_lons):
        """Calcula azimuth desde antena a cada punto"""
        lat1 = self.xp.radians(ant_lat)
        lon1 = self.xp.radians(ant_lon)
        lat2 = self.xp.radians(grid_lats)
        lon2 = self.xp.radians(grid_lons)

        dlon = lon2 - lon1

        # Bearing inicial geodésico (forward azimuth) en esfera.
        y = self.xp.sin(dlon) * self.xp.cos(lat2)
        x = (
            self.xp.cos(lat1) * self.xp.sin(lat2)
            - self.xp.sin(lat1) * self.xp.cos(lat2) * self.xp.cos(dlon)
        )

        azimuth = self.xp.degrees(self.xp.arctan2(y, x))
        azimuth = (azimuth + 360) % 360
        
        return azimuth

    def calculate_single_antenna_quick(
        self,
        antenna,
        center_lat: float,
        center_lon: float,
        radius_km: float = 5.0,
        resolution: int = 100,
        model=None,
        model_params: dict = None,
        terrain_loader=None
    ):
        """
        Cálculo rápido de cobertura en área cuadrada

        Args:
            antenna: Objeto Antenna
            center_lat, center_lon: Centro del área (normalmente la antena)
            radius_km: Radio en km desde el centro
            resolution: Puntos por lado del grid (100x100 = 10,000 puntos)
            model: Modelo de propagación a usar
            model_params: Parámetros adicionales para el modelo (environment, city_type, etc.)
            terrain_loader: TerrainLoader para obtener elevaciones (opcional)

        Returns:
            dict con 'lats', 'lons', 'rsrp' (arrays numpy)
        """
        self.logger.info(f"Quick coverage calculation for {antenna.name}")

        # Valores por defecto para model_params
        if model_params is None:
            model_params = {}

        # Convertir km a grados (aproximado)
        # 1 grado ≈ 111 km
        delta_deg = radius_km / 111.0

        # Crear grid
        lat_min = center_lat - delta_deg
        lat_max = center_lat + delta_deg
        lon_min = center_lon - delta_deg
        lon_max = center_lon + delta_deg

        lats = np.linspace(lat_min, lat_max, resolution)
        lons = np.linspace(lon_min, lon_max, resolution)

        grid_lats, grid_lons = np.meshgrid(lats, lons)

        # Obtener elevaciones del terreno
        if terrain_loader and terrain_loader.is_loaded():
            self.logger.debug("Loading terrain elevations for grid...")
            terrain_heights = terrain_loader.get_elevations_fast(grid_lats, grid_lons)
        else:
            terrain_heights = np.zeros_like(grid_lats)

        # Transferir a GPU si disponible
        if self.engine.use_gpu:
            self.logger.debug("Using GPU for calculation")
            grid_lats_gpu = self.xp.asarray(grid_lats)
            grid_lons_gpu = self.xp.asarray(grid_lons)
            terrain_heights_gpu = self.xp.asarray(terrain_heights)
        else:
            grid_lats_gpu = grid_lats
            grid_lons_gpu = grid_lons
            terrain_heights_gpu = terrain_heights

        # Calcular distancias
        distances = self._calculate_distances(
            antenna.latitude, antenna.longitude,
            grid_lats_gpu, grid_lons_gpu
        )

        # Preparar parámetros para model.calculate_path_loss
        # PHASE 3: Aplicar frequency override si está disponible
        frequency_to_use = model_params.get('frequency_override_mhz', None) or antenna.frequency_mhz

        path_loss_args = {
            'distances': distances,
            'frequency': frequency_to_use,
            'tx_height': antenna.height_agl,
            'terrain_heights': terrain_heights_gpu
        }

        # Calcular perfiles radiales si hay TerrainLoader disponible
        if terrain_loader is not None and terrain_loader.is_loaded():
            # Convertir a NumPy primero (terrain_loader espera NumPy, no GPU arrays)
            lats_cpu = self.xp.asnumpy(grid_lats) if self.engine.use_gpu else grid_lats
            lons_cpu = self.xp.asnumpy(grid_lons) if self.engine.use_gpu else grid_lons
            terrain_profiles = terrain_loader.get_radial_profiles(
                antenna.latitude, antenna.longitude,
                lats_cpu.ravel(), lons_cpu.ravel()
            )
            # Convertir terrain_profiles al módulo correcto (NumPy o CuPy)
            terrain_profiles = self.xp.asarray(terrain_profiles)
            path_loss_args['terrain_profiles'] = terrain_profiles
            self.logger.debug(f"terrain_profiles shape: {terrain_profiles.shape}")

        # Agregar parámetros adicionales del modelo (Okumura-Hata)
        path_loss_args.update(model_params)

        result = model.calculate_path_loss(**path_loss_args)
        # Algunos modelos retornan dict, otros ndarray directamente
        path_loss = result['path_loss'] if isinstance(result, dict) else result

        # Obtener elevación TX para patrón vertical
        if terrain_loader is not None and terrain_loader.is_loaded():
            tx_elevation_quick = terrain_loader.get_elevation(antenna.latitude, antenna.longitude)
        else:
            tx_elevation_quick = 0.0

        # Aplicar patrón de antena 3D (horizontal + vertical, 3GPP TR 38.901 §7.3.2)
        antenna_gain = self._apply_antenna_pattern(
            antenna, grid_lats_gpu, grid_lons_gpu,
            distances=distances,
            terrain_heights=terrain_heights_gpu,
            tx_elevation=tx_elevation_quick
        )

        # RSRP = Tx Power + Antenna Gain - Path Loss
        rsrp = antenna.tx_power_dbm + antenna_gain - path_loss

        # Convertir de vuelta a CPU
        if self.engine.use_gpu:
            rsrp = self.xp.asnumpy(rsrp)
            grid_lats = self.xp.asnumpy(grid_lats_gpu)
            grid_lons = self.xp.asnumpy(grid_lons_gpu)
            path_loss = self.xp.asnumpy(path_loss)
            antenna_gain = self.xp.asnumpy(antenna_gain)

        return {
            'lats': grid_lats,
            'lons': grid_lons,
            'rsrp': rsrp,
            'path_loss': path_loss,
            'antenna_gain': antenna_gain,
            'antenna_id': antenna.id
        }