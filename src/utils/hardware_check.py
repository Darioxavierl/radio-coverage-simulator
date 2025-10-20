import importlib
import subprocess
import sys

def get_compute_backend(logger, min_cuda_version=(13, 0)):
    """Selecciona el backend (CuPy o NumPy) según disponibilidad."""
    try:
        import cupy

        # Comprobar número de GPUs
        device_count = cupy.cuda.runtime.getDeviceCount()
        if device_count == 0:
            logger.info("No se detectaron GPUs NVIDIA.")
            import numpy as xp
            return xp

        # Obtener info de la GPU y versión CUDA
        props = cupy.cuda.runtime.getDeviceProperties(0)
        gpu_name = props["name"].decode("utf-8")
        cuda_version = cupy.cuda.runtime.runtimeGetVersion() / 1000.0  # ej. 13.0
        logger.info(f"GPU detectada: {gpu_name} | CUDA {cuda_version:.1f}")

        # Verificar versión mínima
        if cuda_version < float(f"{min_cuda_version[0]}.{min_cuda_version[1]}"):
            logger.info(f"Versión CUDA insuficiente (requiere {min_cuda_version[0]}.{min_cuda_version[1]} o superior).")
            import numpy as xp
        else:
            logger.info("Usando GPU con CuPy.")
            import cupy as xp

    except ModuleNotFoundError:
        logger.info("CuPy no está instalado. Usando NumPy.")
        import numpy as xp
    except Exception as e:
        logger.info(f"Error al inicializar GPU: {e}")
        import numpy as xp

    return xp
    

if __name__ == "__main__":

    
    from logger import setup_logger

    logger = setup_logger(__name__)
    xp = get_compute_backend(logger)
    a = xp.arange(1e6)
    b = xp.sqrt(a)
    print(b)
