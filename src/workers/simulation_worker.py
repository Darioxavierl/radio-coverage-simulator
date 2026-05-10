from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
import logging
from typing import List, Dict
from pathlib import Path
from models.antenna import Antenna
from core.models.traditional.free_space import FreeSpacePathLossModel
from core.terrain_loader import TerrainLoader
from utils.heatmap_generator import HeatmapGenerator

class SimulationWorker(QObject):
    """Worker que ejecuta simulaciones en thread separado"""

    # Señales
    progress = pyqtSignal(int)
    status_message = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, antennas: List[Antenna], coverage_calculator,
                 terrain_data, config: Dict):
        super().__init__()
        self.antennas = antennas
        self.calculator = coverage_calculator
        self.config = config
        self.should_stop = False
        self.logger = logging.getLogger("SimulationWorker")

        # PHASE 4: Cargar TerrainLoader
        self.terrain_loader = None
        if terrain_data is not None and terrain_data.is_loaded():
            self.terrain_loader = terrain_data
            stats = self.terrain_loader.get_stats()
            self.logger.info(f"Using terrain from GUI: elevation range {stats['min']:.0f}-{stats['max']:.0f}m")
        else:
            # Intentar cargar archivo de terreno por defecto
            terrain_file = Path('data/terrain/cuenca_terrain.tif')
            if terrain_file.exists():
                try:
                    self.logger.info("Loading default terrain file...")
                    self.terrain_loader = TerrainLoader(str(terrain_file))
                    if self.terrain_loader.is_loaded():
                        stats = self.terrain_loader.get_stats()
                        self.logger.info(f"Default terrain loaded: elevation range {stats['min']:.0f}-{stats['max']:.0f}m")
                    else:
                        self.logger.warning("Default terrain file validation failed")
                        self.terrain_loader = None
                except Exception as e:
                    self.logger.warning(f"Failed to load default terrain: {e}")
                    self.terrain_loader = None
            else:
                self.logger.warning("No terrain file found at data/terrain/cuenca_terrain.tif, using flat terrain")
                self.terrain_loader = None
    
    def run(self):
        """Ejecuta la simulación"""
        import time
        from datetime import datetime

        try:
            # NUEVO: Capturar timestamp inicial y modo GPU
            sim_start = time.perf_counter()
            gpu_used = self.calculator.engine.use_gpu
            gpu_device = self.calculator.engine.gpu_detector.get_device_info_string() if gpu_used else "CPU Only"

            self.logger.info(f"Starting simulation for {len(self.antennas)} antennas on {'GPU' if gpu_used else 'CPU'}")
            self.status_message.emit("Preparando simulación...")
            self.progress.emit(10)

            # Modelo de propagación - usar el seleccionado en config
            model = self._get_propagation_model()

            # PHASE 7: Crear grid GLOBAL una sola vez
            self.logger.info("Creating global simulation grid...")
            grid_lats, grid_lons, terrain_heights = self._create_simulation_grid()
            terrain_time = time.perf_counter() - sim_start  # NUEVA: Checkpoint terrain loading
            self.logger.info(f"Global grid created: {grid_lats.shape} points (terrain load: {terrain_time:.3f}s)")

            self.status_message.emit("Calculando cobertura...")
            self.progress.emit(30)

            results = {'individual': {}}
            antenna_times = {}  # NUEVO: Rastrear tiempos por antena
            antenna_coverage_times = {}  # NUEVA: Timing de cálculo (sin render)
            antenna_render_times = {}  # NUEVA: Timing de render

            # PHASE 7: Preparar parámetros base para modelo (fuera del loop)
            frequency_override_mhz = self.config.get('frequency_override_mhz', None)
            if frequency_override_mhz and frequency_override_mhz > 0:
                self.logger.debug(f"Using frequency override: {frequency_override_mhz} MHz")

            base_model_params = {}
            if self.config.get('model') == 'okumura_hata':
                base_model_params['environment'] = self.config.get('environment', 'Urban')
                base_model_params['city_type'] = self.config.get('city_type', 'medium')
                base_model_params['mobile_height'] = self.config.get('mobile_height', 1.5)

            elif self.config.get('model') == 'cost231':
                base_model_params['building_height'] = self.config.get('building_height', 15.0)
                base_model_params['street_width'] = self.config.get('street_width', 12.0)
                base_model_params['street_orientation'] = self.config.get('street_orientation', 0.0)

            elif self.config.get('model') == 'itu_p1546':
                base_model_params['environment'] = self.config.get('environment', 'Urban')
                base_model_params['terrain_type'] = self.config.get('terrain_type', 'mixed')

            elif self.config.get('model') == 'three_gpp_38901':
                base_model_params['scenario'] = self.config.get('scenario', 'UMa')
                base_model_params['h_bs'] = self.config.get('h_bs', 25.0)
                base_model_params['h_ue'] = self.config.get('h_ue', 1.5)
                base_model_params['use_dem'] = self.config.get('use_dem', False)
                self.logger.debug(f"3GPP config: scenario={base_model_params['scenario']}, "
                                f"h_bs={base_model_params['h_bs']}m, h_ue={base_model_params['h_ue']}m")

            if frequency_override_mhz and frequency_override_mhz > 0:
                base_model_params['frequency_override_mhz'] = frequency_override_mhz

            # Calcular para cada antena
            for i, antenna in enumerate(self.antennas):
                if self.should_stop:
                    return

                # NUEVO: Capturar tiempo de inicio de antena
                antenna_start = time.perf_counter()

                self.status_message.emit(f"Calculando antena {i+1}/{len(self.antennas)}...")

                # Copiar parámetros base y agregar parámetros específicos de esta antena
                model_params = base_model_params.copy()

                # Obtener tx_elevation del terreno para esta antena
                if self.terrain_loader and self.terrain_loader.is_loaded():
                    tx_elevation = self.terrain_loader.get_elevation(
                        antenna.latitude, antenna.longitude
                    )
                    model_params['tx_elevation'] = tx_elevation
                    self.logger.debug(f"TX elevation for {antenna.name}: {tx_elevation:.1f}m")
                else:
                    model_params['tx_elevation'] = 0.0

                # PHASE 7: Usar grid GLOBAL en lugar de crear uno centrado en antena
                coverage_start = time.perf_counter()  # NUEVA: Checkpoint inicio coverage calc
                coverage_result = self.calculator.calculate_single_antenna_coverage(
                    antenna=antenna,
                    grid_lats=grid_lats,
                    grid_lons=grid_lons,
                    terrain_heights=terrain_heights,
                    model=model,
                    model_params=model_params,
                    return_details=True,
                )
                coverage_calc_time = time.perf_counter() - coverage_start  # NUEVA: Timing coverage calc
                antenna_coverage_times[antenna.id] = round(coverage_calc_time, 3)

                rsrp = coverage_result['rsrp']
                
                # OPTIMIZACION: Convertir a NumPy para render (matplotlib requiere NumPy)
                if self.calculator.engine.use_gpu:
                    rsrp_numpy = self.calculator.xp.asnumpy(rsrp)
                    path_loss_numpy = self.calculator.xp.asnumpy(coverage_result['path_loss'])
                    antenna_gain_numpy = self.calculator.xp.asnumpy(coverage_result['antenna_gain'])
                else:
                    rsrp_numpy = rsrp
                    path_loss_numpy = coverage_result['path_loss']
                    antenna_gain_numpy = coverage_result['antenna_gain']

                # Generar imagen de heatmap
                render_start = time.perf_counter()  # NUEVA: Checkpoint inicio render
                heatmap_gen = HeatmapGenerator()

                image_url = heatmap_gen.generate_heatmap_image(
                    rsrp_numpy,
                    colormap='jet',
                    vmin=-120,
                    vmax=-60,
                    alpha=0.6
                )
                render_time = time.perf_counter() - render_start  # NUEVA: Timing render
                antenna_render_times[antenna.id] = round(render_time, 3)

                # Construir estructura de coverage compatible con versión anterior
                coverage = {
                    'lats': grid_lats,
                    'lons': grid_lons,
                    'rsrp': rsrp_numpy,
                    'path_loss': path_loss_numpy,
                    'antenna_gain': antenna_gain_numpy,
                    'antenna': {
                        'id': antenna.id,
                        'name': antenna.name,
                        'frequency_mhz': antenna.frequency_mhz,
                        'tx_power_dbm': antenna.tx_power_dbm,
                        'tx_height_m': antenna.height_agl,
                    },
                    'image_url': image_url,
                    'bounds': [
                        [grid_lats.min(), grid_lons.min()],
                        [grid_lats.max(), grid_lons.max()]
                    ]
                }

                results['individual'][antenna.id] = coverage

                # NUEVO: Capturar tiempo de antena
                antenna_time = time.perf_counter() - antenna_start
                antenna_times[antenna.id] = round(antenna_time, 3)
                self.logger.debug(f"Antenna {antenna.name} calculated in {antenna_time:.3f}s")

                progress = 30 + int((i + 1) / len(self.antennas) * 50)
                self.progress.emit(progress)

            # PHASE 7: Calcular heatmap agregado para múltiples antenas
            aggregation_start = time.perf_counter()  # NUEVA: Checkpoint inicio aggregation
            if len(self.antennas) > 1:
                self.status_message.emit("Calculando cobertura agregada...")
                self.logger.info("Computing aggregated coverage for multi-antenna deployment")

                # Llamar método de agregación que ya existe
                aggregated_results = self.calculator.calculate_multi_antenna_coverage(
                    antennas=self.antennas,
                    grid_lats=grid_lats,
                    grid_lons=grid_lons,
                    terrain_heights=terrain_heights,
                    model=model,
                    model_params=model_params
                )

                # Generar heatmap agregado
                heatmap_gen = HeatmapGenerator()
                aggregated_image = heatmap_gen.generate_heatmap_image(
                    aggregated_results['rsrp'],
                    colormap='jet',
                    vmin=-120,
                    vmax=-60,
                    alpha=0.6
                )

                results['aggregated'] = {
                    'lats': grid_lats,
                    'lons': grid_lons,
                    'image_url': aggregated_image,
                    'bounds': [
                        [grid_lats.min(), grid_lons.min()],
                        [grid_lats.max(), grid_lons.max()]
                    ],
                    'rsrp': aggregated_results['rsrp'],
                    'best_server': aggregated_results['best_server']
                }

                # Derivar métricas agregadas a partir de la antena dominante por píxel.
                antenna_ids = list(results['individual'].keys())
                if antenna_ids:
                    rsrp_stack = np.stack([
                        results['individual'][ant_id]['rsrp'] for ant_id in antenna_ids
                    ], axis=0)
                    best_indices = np.argmax(rsrp_stack, axis=0)
                    expanded_indices = np.expand_dims(best_indices, axis=0)

                    path_loss_stack = np.stack([
                        results['individual'][ant_id]['path_loss'] for ant_id in antenna_ids
                    ], axis=0)
                    antenna_gain_stack = np.stack([
                        results['individual'][ant_id]['antenna_gain'] for ant_id in antenna_ids
                    ], axis=0)

                    results['aggregated']['path_loss'] = np.take_along_axis(
                        path_loss_stack,
                        expanded_indices,
                        axis=0
                    )[0]
                    results['aggregated']['antenna_gain'] = np.take_along_axis(
                        antenna_gain_stack,
                        expanded_indices,
                        axis=0
                    )[0]

                self.logger.info("Aggregated coverage generated successfully")
            else:
                # Para una sola antena, copiar la individual como agregada
                antenna_id = self.antennas[0].id
                results['aggregated'] = results['individual'][antenna_id]
                self.logger.info("Single antenna deployment: using individual coverage as aggregated")

            aggregation_time = time.perf_counter() - aggregation_start  # NUEVA: Timing aggregation
            self.progress.emit(90)

            # NUEVO: Capturar duración total y agregar metadata
            total_time = time.perf_counter() - sim_start

            results['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'gpu_used': gpu_used,
                'gpu_device': gpu_device,
                'total_execution_time_seconds': round(total_time, 2),
                'terrain_loading_time_seconds': round(terrain_time, 3),
                'antenna_total_times_seconds': antenna_times,
                'antenna_coverage_times_seconds': antenna_coverage_times,
                'antenna_render_times_seconds': antenna_render_times,
                'multi_antenna_aggregation_time_seconds': round(aggregation_time, 3),
                'num_antennas': len(self.antennas),
                'grid_parameters': {
                    'radius_km': self.config.get('radius_km', 5.0),
                    'resolution': self.config.get('resolution', 100),
                    'total_grid_points': (self.config.get('resolution', 100)) ** 2
                },
                'model_used': self.config.get('model', 'unknown'),
                'model_parameters': {
                    k: v for k, v in self.config.items()
                    if k in ['environment', 'city_type', 'scenario', 'h_bs', 'h_ue',
                            'building_height', 'street_width', 'terrain_type']
                }
            }

            self.progress.emit(100)
            self.logger.info(f"Simulation completed in {total_time:.2f}s")
            self.finished.emit(results)

        except Exception as e:
            self.logger.error(f"Simulation error: {e}", exc_info=True)
            self.error.emit(str(e))
        
    def stop(self):
        """Detiene la simulación"""
        self.should_stop = True
        self.logger.info("Simulation stop requested")
    
    def _create_simulation_grid(self):
        """Crea grid de puntos para simulación"""
        # Determinar bounds a partir de la distribución actual de antenas
        lats = [ant.latitude for ant in self.antennas]
        lons = [ant.longitude for ant in self.antennas]

        center_lat = (min(lats) + max(lats)) / 2.0
        center_lon = (min(lons) + max(lons)) / 2.0

        # Honrar el radio configurado sin recortar despliegues existentes.
        radius_km = float(self.config.get('radius_km', 5.0) or 5.0)
        lat_radius_deg = radius_km / 111.0

        cos_lat = np.cos(np.radians(center_lat))
        if abs(cos_lat) < 1e-6:
            cos_lat = 1e-6
        lon_radius_deg = radius_km / (111.0 * abs(cos_lat))

        half_span_lat = max((max(lats) - min(lats)) / 2.0, lat_radius_deg)
        half_span_lon = max((max(lons) - min(lons)) / 2.0, lon_radius_deg)

        min_lat, max_lat = center_lat - half_span_lat, center_lat + half_span_lat
        min_lon, max_lon = center_lon - half_span_lon, center_lon + half_span_lon
        
        # Resolución configurable
        resolution = self.config.get('resolution', 100)
        
        grid_lats = np.linspace(min_lat, max_lat, resolution)
        grid_lons = np.linspace(min_lon, max_lon, resolution)
        
        grid_lats, grid_lons = np.meshgrid(grid_lats, grid_lons)

        # Cargar alturas de terreno
        if self.terrain_loader and self.terrain_loader.is_loaded():
            self.logger.info("Interpolating terrain elevations for grid...")
            terrain_heights = self.terrain_loader.get_elevations_fast(grid_lats, grid_lons)
            self.logger.info(f"  Grid elevation range: {terrain_heights.min():.0f} - {terrain_heights.max():.0f}m")
        else:
            self.logger.warning("Using flat terrain (no elevation data)")
            terrain_heights = np.zeros_like(grid_lats)

        return grid_lats, grid_lons, terrain_heights
    
    def _get_propagation_model(self):
        """Obtiene el modelo de propagación configurado"""
        model_name = self.config.get('model', 'free_space')

        self.logger.info(f"Using propagation model: {model_name}")

        if model_name == 'free_space':
            from core.models.traditional.free_space import FreeSpacePathLossModel
            return FreeSpacePathLossModel(compute_module=self.calculator.xp)

        elif model_name == 'okumura_hata':
            from core.models.traditional.okumura_hata import OkumuraHataModel

            # Extraer parámetros de Okumura-Hata desde config
            okumura_config = {}
            if 'environment' in self.config:
                okumura_config['environment'] = self.config['environment']
            if 'city_type' in self.config:
                okumura_config['city_type'] = self.config['city_type']
            if 'mobile_height' in self.config:
                okumura_config['mobile_height'] = self.config['mobile_height']

            self.logger.info(f"Okumura-Hata config: {okumura_config}")

            return OkumuraHataModel(config=okumura_config, compute_module=self.calculator.xp)

        elif model_name == 'cost231':
            from core.models.traditional.cost231 import COST231WalfischIkegamiModel

            # Extraer parámetros de COST-231 desde config
            cost231_config = {}
            if 'building_height' in self.config:
                cost231_config['building_height'] = self.config['building_height']
            else:
                cost231_config['building_height'] = 15.0

            if 'street_width' in self.config:
                cost231_config['street_width'] = self.config['street_width']
            else:
                cost231_config['street_width'] = 12.0

            if 'street_orientation' in self.config:
                cost231_config['street_orientation'] = self.config['street_orientation']
            else:
                cost231_config['street_orientation'] = 0.0

            self.logger.info(f"COST-231 config: {cost231_config}")

            return COST231WalfischIkegamiModel(config=cost231_config, compute_module=self.calculator.xp)

        elif model_name == 'itu_p1546':
            from core.models.traditional.itu_r_p1546 import ITUR_P1546Model

            # Extraer parámetros de ITU-R P.1546 desde config
            itu_config = {}
            if 'environment' in self.config:
                itu_config['environment'] = self.config['environment']
            else:
                itu_config['environment'] = 'Urban'

            if 'terrain_type' in self.config:
                itu_config['terrain_type'] = self.config['terrain_type']
            else:
                itu_config['terrain_type'] = 'mixed'

            self.logger.info(f"ITU-R P.1546 config: {itu_config}")

            return ITUR_P1546Model(config=itu_config, compute_module=self.calculator.xp)

        elif model_name == 'three_gpp_38901':
            from core.models.gpp_3gpp.three_gpp_38901 import ThreGPP38901Model

            # Extraer parámetros de 3GPP TR 38.901 desde config
            three_gpp_config = {}
            if 'scenario' in self.config:
                three_gpp_config['scenario'] = self.config['scenario']
            else:
                three_gpp_config['scenario'] = 'UMa'

            if 'h_bs' in self.config:
                three_gpp_config['h_bs'] = self.config['h_bs']
            else:
                # Default según escenario
                scenario = three_gpp_config['scenario']
                defaults = {'UMa': 25, 'UMi': 10, 'RMa': 35}
                three_gpp_config['h_bs'] = defaults.get(scenario, 25)

            if 'h_ue' in self.config:
                three_gpp_config['h_ue'] = self.config['h_ue']
            else:
                three_gpp_config['h_ue'] = 1.5

            if 'use_dem' in self.config:
                three_gpp_config['use_dem'] = self.config['use_dem']
            else:
                three_gpp_config['use_dem'] = False

            self.logger.info(f"3GPP TR 38.901 config: {three_gpp_config}")

            return ThreGPP38901Model(config=three_gpp_config, numpy_module=self.calculator.xp)

        # Default: Free Space
        self.logger.warning(f"Unknown model '{model_name}', using Free Space")
        from core.models.traditional.free_space import FreeSpacePathLossModel
        return FreeSpacePathLossModel(compute_module=self.calculator.xp)