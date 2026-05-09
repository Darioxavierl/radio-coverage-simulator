import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

class ConfigManager:
    DEFAULT_SETTINGS = {
        "application": {
            "name": "RF Coverage Tool",
            "version": "1.0.0",
            "language": "es",
        },
        "compute": {
            "use_gpu": False,
        },
        "ui": {
            "theme": "dark",
            "map_default_zoom": 13,
            "default_map_center": [-2.9001, -79.0059],
        },
        "paths": {
            "terrain_data": "data/terrain",
            "exports": "data/exports",
            "logs": "logs",
        },
        "logging": {
            "level": "INFO",
            "max_file_size_mb": 10,
            "backup_count": 5,
        },
    }

    DEFAULT_MODELS_CONFIG = {}

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger("ConfigManager")

        self.settings = self.load_json("settings.json", self.DEFAULT_SETTINGS)
        self.models_config = self.load_json("models_config.json", self.DEFAULT_MODELS_CONFIG)
        
    def load_json(self, filename: str, default_data: Dict[str, Any]) -> Dict[str, Any]:
        path = self.config_dir / filename
        data = deepcopy(default_data)

        if not path.exists():
            self.logger.warning(f"Config file not found, using defaults: {path}")
            return data

        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {path}: {e}. Using defaults.")
            return data
        except OSError as e:
            self.logger.error(f"Error reading {path}: {e}. Using defaults.")
            return data

        if not isinstance(loaded, dict):
            self.logger.error(f"Invalid config format in {path}: root must be an object. Using defaults.")
            return data

        return self._deep_merge(data, loaded)

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge recursivo donde override tiene prioridad."""
        merged = deepcopy(base)
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def save_settings(self, settings: Dict[str, Any]):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        merged_settings = self._deep_merge(self.DEFAULT_SETTINGS, settings)
        path = self.config_dir / "settings.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(merged_settings, f, indent=4, ensure_ascii=False)

        self.settings = merged_settings