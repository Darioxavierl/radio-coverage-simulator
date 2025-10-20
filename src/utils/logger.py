import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name="simulador", level=logging.DEBUG):
    """
    Configura un logger rotativo para toda la aplicación.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicados si ya fue configurado
    if logger.handlers:
        return logger

    # Formato estándar del log
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # --- Archivo de log rotativo ---
    log_file = os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d}.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # --- Consola (para debug) ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    # Agregar handlers al logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger