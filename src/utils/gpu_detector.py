import logging

# Detección automática de CuPy - sin forzar CPU
_cupy_checked = False
_cupy_module = None
_cupy_available = False


def _try_import_cupy():
    """Intenta importar cupy de forma segura"""
    global _cupy_checked, _cupy_module, _cupy_available
    
    if _cupy_checked:
        return _cupy_module, _cupy_available
    
    _cupy_checked = True
    
    try:
        import cupy as cp
        # Verificar que GPU esté realmente disponible
        _ = cp.cuda.Device()
        _cupy_module = cp
        _cupy_available = True
        logging.info("CuPy imported successfully - GPU available")
        return cp, True
    except Exception as e:
        logging.info(f"CuPy not available - using CPU mode: {type(e).__name__}: {e}")
        _cupy_module = None
        _cupy_available = False
        return None, False


class GPUDetector:
    def __init__(self):
        self.has_cuda = False
        self.cupy_available = False
        self.device_name = "CPU"
        self.device_info = {}
        self._detect()
    
    def _detect(self):
        try:
            cp, available = _try_import_cupy()
            
            if not available:
                raise ImportError("CuPy not available")
            self.cupy_available = True
            self.has_cuda = True
            
            # Obtener información del dispositivo de forma segura
            try:
                device = cp.cuda.Device()
                # Método correcto para obtener atributos del dispositivo
                self.device_info = {
                    'id': device.id,
                    'compute_capability': device.compute_capability,
                    'pci_bus_id': device.pci_bus_id
                }
                
                # Intentar obtener el nombre del dispositivo
                try:
                    # En CuPy más reciente
                    props = cp.cuda.runtime.getDeviceProperties(device.id)
                    self.device_name = props['name'].decode('utf-8')
                except:
                    # Fallback
                    self.device_name = f"CUDA Device {device.id}"
                    
            except Exception as e:
                logging.warning(f"Could not get device details: {e}")
                self.device_name = "CUDA Device (Unknown)"
            
            logging.info(f"GPU detected: {self.device_name}")
            if self.device_info:
                logging.info(f"  Device ID: {self.device_info.get('id', 'N/A')}")
                logging.info(f"  Compute Capability: {self.device_info.get('compute_capability', 'N/A')}")
            
        except ImportError:
            logging.warning("CuPy not available. Using NumPy/CPU.")
        except Exception as e:
            logging.error(f"GPU detection error: {e}")
    
    def get_compute_module(self):
        """Retorna cupy o numpy según disponibilidad"""
        if self.cupy_available:
            cp, available = _try_import_cupy()
            if available:
                return cp
        
        import numpy as np
        return np
    
    def get_device_info_string(self):
        """Retorna información formateada del dispositivo"""
        if self.has_cuda:
            info = f"GPU: {self.device_name}"
            if 'compute_capability' in self.device_info:
                cc = self.device_info['compute_capability']
                info += f" (CC {cc[0]}.{cc[1]})"
            return info
        else:
            return "CPU (No CUDA available)"