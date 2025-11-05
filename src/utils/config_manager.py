import json
from pathlib import Path
from typing import Any, Dict

class ConfigManager:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.settings = self.load_json("settings.json")
        self.models_config = self.load_json("models_config.json")
        
    def load_json(self, filename: str) -> Dict[str, Any]:
        path = self.config_dir / filename
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_settings(self, settings: Dict[str, Any]):
        path = self.config_dir / "settings.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)