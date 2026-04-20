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

        # Cargar TerrainLoader
        self.terrain_loader = None
        if terrain_data is not None:
            self.terrain_loader = terrain_data
        else:
            # Intentar cargar archivo de terreno por defecto
            terrain_file = Path('data/terrain/cuenca_terrain.tif')
            if terrain_file.exists():
                self.logger.info("Loading default terrain file...")
                self.terrain_loader = TerrainLoader(str(terrain_file))
                if self.terrain_loader.is_loaded():
                    stats = self.terrain_loader.get_stats()
                    self.logger.info(f"Terrain loaded: elevation range {stats['min']:.0f}-{stats['max']:.0f}m")
                else:
                    self.terrain_loader = None
            else:
                self.logger.warning("No terrain file found, using flat terrain (elevation = 0)")
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

            self.status_message.emit("Calculando cobertura...")
            self.progress.emit(30)

            results = {'individual': {}}
            antenna_times = {}  # NUEVO: Rastrear tiempos por antena

            # Calcular para cada antena
            for i, antenna in enumerate(self.antennas):
                if self.should_stop:
                    return

                # NUEVO: Capturar tiempo de inicio de antena
                antenna_start = time.perf_counter()

                self.status_message.emit(f"Calculando antena {i+1}/{len(self.antennas)}...")

                # Cálculo rápido centrado en la antena
                radius_km = self.config.get('radius_km', 5.0)
                resolution = self.config.get('resolution', 100)

                # Parámetros adicionales para Okumura-Hata
                model_params = {}
                if self.config.get('model') == 'okumura_hata':
                    model_params['environment'] = self.config.get('environment', 'Urban')
                    model_params['city_type'] = self.config.get('city_type', 'medium')
                    model_params['mobile_height'] = self.config.get('mobile_height', 1.5)

                    # Obtener tx_elevation del terreno
                    if self.terrain_loader and self.terrain_loader.is_loaded():
                        tx_elevation = self.terrain_loader.get_elevation(
                            antenna.latitude, antenna.longitude
                        )
                        model_params['tx_elevation'] = tx_elevation
                        self.logger.debug(f"TX elevation for {antenna.name}: {tx_elevation:.1f}m")
                    else:
                        model_params['tx_elevation'] = 0.0

                # Parámetros adicionales para COST-231
                if self.config.get('model') == 'cost231':
                    model_params['building_height'] = self.config.get('building_height', 15.0)
                    model_params['street_width'] = self.config.get('street_width', 12.0)
                    model_params['street_orientation'] = self.config.get('street_orientation', 0.0)

                    # Obtener tx_elevation del terreno
                    if self.terrain_loader and self.terrain_loader.is_loaded():
                        tx_elevation = self.terrain_loader.get_elevation(
                            antenna.latitude, antenna.longitude
                        )
                        model_params['tx_elevation'] = tx_elevation
                        self.logger.debug(f"TX elevation for {antenna.name}: {tx_elevation:.1f}m")
                    else:
                        model_params['tx_elevation'] = 0.0

                # Parámetros adicionales para ITU-R P.1546
                if self.config.get('model') == 'itu_p1546':
                    model_params['environment'] = self.config.get('environment', 'Urban')
                    model_params['terrain_type'] = self.config.get('terrain_type', 'mixed')

                    # Obtener tx_elevation del terreno
                    if self.terrain_loader and self.terrain_loader.is_loaded():
                        tx_elevation = self.terrain_loader.get_elevation(
                            antenna.latitude, antenna.longitude
                        )
                        model_params['tx_elevation'] = tx_elevation
                        self.logger.debug(f"TX elevation for {antenna.name}: {tx_elevation:.1f}m")
                    else:
                        model_params['tx_elevation'] = 0.0

                # Parámetros adicionales para 3GPP TR 38.901
                if self.config.get('model') == 'three_gpp_38901':
                    model_params['scenario'] = self.config.get('scenario', 'UMa')
                    model_params['h_bs'] = self.config.get('h_bs', 25.0)
                    model_params['h_ue'] = self.config.get('h_ue', 1.5)
                    model_params['use_dem'] = self.config.get('use_dem', False)

                    self.logger.debug(f"3GPP config: scenario={model_params['scenario']}, "
                                    f"h_bs={model_params['h_bs']}m, h_ue={model_params['h_ue']}m, "
                                    f"use_dem={model_params['use_dem']}")

                coverage = self.calculator.calculate_single_antenna_quick(
                    antenna=antenna,
                    center_lat=antenna.latitude,
                    center_lon=antenna.longitude,
                    radius_km=radius_km,
                    resolution=resolution,
                    model=model,
                    model_params=model_params,
                    terrain_loader=self.terrain_loader  # Pasar terrain_loader
                )

                # Generar imagen de heatmap
                heatmap_gen = HeatmapGenerator()

                image_url = heatmap_gen.generate_heatmap_image(
                    coverage['rsrp'],
                    colormap='jet',
                    vmin=-120,
                    vmax=-60,
                    alpha=0.6
                )

                # Agregar bounds e image_url
                coverage['image_url'] = image_url
                coverage['bounds'] = [
                    [coverage['lats'].min(), coverage['lons'].min()],
                    [coverage['lats'].max(), coverage['lons'].max()]
                ]

                results['individual'][antenna.id] = coverage

                # NUEVO: Capturar tiempo de antena
                antenna_time = time.perf_counter() - antenna_start
                antenna_times[antenna.id] = round(antenna_time, 3)
                self.logger.debug(f"Antenna {antenna.name} calculated in {antenna_time:.3f}s")

                progress = 30 + int((i + 1) / len(self.antennas) * 60)
                self.progress.emit(progress)

            # NUEVO: Capturar duración total y agregar metadata
            total_time = time.perf_counter() - sim_start

            results['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'gpu_used': gpu_used,
                'gpu_device': gpu_device,
                'total_execution_time_seconds': round(total_time, 2),
                'antenna_times_seconds': antenna_times,
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
        # Determinar bounds
        lats = [ant.latitude for ant in self.antennas]
        lons = [ant.longitude for ant in self.antennas]
        
        min_lat, max_lat = min(lats) - 0.05, max(lats) + 0.05
        min_lon, max_lon = min(lons) - 0.05, max(lons) + 0.05
        
        # Resolución configurable
        resolution = self.config.get('resolution', 100)  # puntos por grado
        
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