from typing import Protocol
import logging

class ComputeEngine:
    def __init__(self, use_gpu: bool = True):
        from utils.gpu_detector import GPUDetector
        
        self.gpu_detector = GPUDetector()
        self.use_gpu = use_gpu and self.gpu_detector.cupy_available
        self.xp = self.gpu_detector.get_compute_module() if self.use_gpu else None
        
        if not self.use_gpu:
            import numpy as np
            self.xp = np
        
        logging.info(f"Compute engine initialized: {'GPU' if self.use_gpu else 'CPU'}")
    
    def switch_compute_mode(self, use_gpu: bool):
        """Permite cambiar CPU/GPU en runtime"""
        if use_gpu and not self.gpu_detector.cupy_available:
            logging.warning("GPU requested but not available")
            return False
        
        self.use_gpu = use_gpu
        self.xp = self.gpu_detector.get_compute_module() if use_gpu else None
        if not use_gpu:
            import numpy as np
            self.xp = np
        
        logging.info(f"Switched to: {'GPU' if self.use_gpu else 'CPU'}")
        return True