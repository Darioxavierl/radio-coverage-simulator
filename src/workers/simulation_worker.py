from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
import logging
from typing import List, Dict
from models.antenna import Antenna
from core.models.traditional.free_space import FreeSpacePathLossModel
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
        self.terrain_data = terrain_data
        self.config = config
        self.should_stop = False
        self.logger = logging.getLogger("SimulationWorker")
    
    def run(self):
        """Ejecuta la simulación"""
        try:
            self.logger.info(f"Starting simulation for {len(self.antennas)} antennas")
            self.status_message.emit("Preparando simulación...")
            self.progress.emit(10)
            
            # Modelo de propagación - usar el seleccionado en config
            model = self._get_propagation_model()
            
            self.status_message.emit("Calculando cobertura...")
            self.progress.emit(30)
            
            results = {'individual': {}}
            
            # Calcular para cada antena
            for i, antenna in enumerate(self.antennas):
                if self.should_stop:
                    return
                
                self.status_message.emit(f"Calculando antena {i+1}/{len(self.antennas)}...")
                
                # Cálculo rápido centrado en la antena
                radius_km = self.config.get('radius_km', 5.0)
                resolution = self.config.get('resolution', 100)
                
                coverage = self.calculator.calculate_single_antenna_quick(
                    antenna=antenna,
                    center_lat=antenna.latitude,
                    center_lon=antenna.longitude,
                    radius_km=radius_km,
                    resolution=resolution,
                    model=model
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
                
                progress = 30 + int((i + 1) / len(self.antennas) * 60)
                self.progress.emit(progress)
            
            self.progress.emit(100)
            self.logger.info("Simulation completed")
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
        if self.terrain_data is not None:
            terrain_heights = self._interpolate_terrain(grid_lats, grid_lons)
        else:
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
            return OkumuraHataModel(compute_module=self.calculator.xp)
        
        # Default: Free Space
        self.logger.warning(f"Unknown model '{model_name}', using Free Space")
        from core.models.traditional.free_space import FreeSpacePathLossModel
        return FreeSpacePathLossModel(compute_module=self.calculator.xp)
    
    def _interpolate_terrain(self, grid_lats, grid_lons):
        """Interpola alturas de terreno para el grid"""
        # TODO: Implementar interpolación real
        return np.zeros_like(grid_lats)