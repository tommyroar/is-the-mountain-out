import tomli
from typing import List, Dict, Any, Optional

class ConfigLoader:
    def __init__(self, config_path: str, target_toml_path: Optional[str] = None):
        self.config_path = config_path
        self.target_toml_path = target_toml_path
        
        self.config = self._load_toml_config(self.config_path)
        self.target_data = self._load_toml_config(self.target_toml_path) if target_toml_path else {}
        
        self._validate_config()

    def _load_toml_config(self, path: str) -> Dict[str, Any]:
        with open(path, 'rb') as f:
            return tomli.load(f)

    def _validate_config(self):
        # Basic config validation
        required_keys = ['schedule_seconds', 'lora_settings', 'capture_interval_seconds', 'gradient_accumulation_steps']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

    @property
    def webcam_sources(self) -> List[Any]:
        # Merge sources from main config and target mountain TOML
        sources = self.config.get('webcam_sources', [])
        if 'webcams' in self.target_data:
            sources.extend([cam['url'] for cam in self.target_data['webcams']])
        return list(set(sources)) # Unique sources

    @property
    def schedule_seconds(self) -> int:
        return self.config['schedule_seconds']

    @property
    def capture_interval_seconds(self) -> int:
        return self.config['capture_interval_seconds']

    @property
    def gradient_accumulation_steps(self) -> int:
        return self.config['gradient_accumulation_steps']

    @property
    def lora_settings(self) -> Dict[str, Any]:
        return self.config['lora_settings']

    @property
    def metar_station(self) -> str:
        # Prefer station from mountain TOML if available
        if 'weather' in self.target_data and 'primary_metar' in self.target_data['weather']:
            return self.target_data['weather']['primary_metar']
        return self.config.get('metar_station', 'KSEA')

    @property
    def mountain_data(self) -> Dict[str, Any]:
        return self.target_data.get('mountain', {})
