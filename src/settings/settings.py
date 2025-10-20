import json
from types import SimpleNamespace

class Settings:
    def __init__(self, json_path):
        self.main_window = type('', (), {})()  # objeto vacío para main_window
        self.load(json_path)

    def load(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
        self.__dict__.update(self.dict_to_obj(data).__dict__)

    def dict_to_obj(self, d):
        if isinstance(d, dict):
            ns = SimpleNamespace()
            for k, v in d.items():
                setattr(ns, k, self.dict_to_obj(v))
            return ns
        elif isinstance(d, list):
            return [self.dict_to_obj(i) for i in d]
        else:
            return d