from typing import Protocol
import logging
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from utils.gpu_detector import GPUDetector

class ComputeEngine(QObject):
    # Signal when GPU/CPU mode changes
    gpu_mode_changed = pyqtSignal(bool)  # True = GPU, False = CPU

    def __init__(self, use_gpu: bool = True):
        super().__init__()

        self.gpu_detector = GPUDetector()
        self.use_gpu = use_gpu and self.gpu_detector.cupy_available

        if self.use_gpu:
            self.xp = self.gpu_detector.get_compute_module()
        else:
            self.xp = np

        logging.info(f"Compute engine initialized: {'GPU' if self.use_gpu else 'CPU'}")
    
    def switch_compute_mode(self, use_gpu: bool):
        """Permite cambiar CPU/GPU en runtime"""
        if use_gpu and not self.gpu_detector.cupy_available:
            logging.warning("GPU requested but not available")
            return False

        self.use_gpu = use_gpu

        if self.use_gpu:
            self.xp = self.gpu_detector.get_compute_module()
        else:
            self.xp = np

        logging.info(f"Switched to: {'GPU' if self.use_gpu else 'CPU'}")

        # Emit signal to notify UI of mode change
        self.gpu_mode_changed.emit(self.use_gpu)

        return True