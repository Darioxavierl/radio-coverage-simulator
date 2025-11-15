from abc import ABC, abstractmethod
from typing import Dict, Any
import numpy as np
import logging

class PropagationModel(ABC):
    def __init__(self, name: str, config: Dict[str, Any], compute_module=None):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"models.{name}")
        # Módulo de cómputo (numpy o cupy)
        if compute_module is None:
            self.xp = np
        else:
            self.xp = compute_module
    
    @abstractmethod
    def calculate_path_loss(self, distance, frequency, **kwargs):
        """Calcula pérdida de trayecto"""
        pass
    
    @abstractmethod
    def get_coverage_map(self, antenna_params, terrain_data, compute_engine):
        """Genera mapa de cobertura"""
        pass
    
    def validate_parameters(self, **params) -> bool:
        """Valida parámetros antes de calcular"""
        pass