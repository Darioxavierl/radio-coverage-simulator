import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

def setup_logger(log_dir: str = "logs", level=logging.INFO):
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Archivo con fecha
    log_file = log_path / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Formato detallado
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler rotativo (10MB, 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Handler consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger