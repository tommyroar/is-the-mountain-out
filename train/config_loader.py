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
        required_keys = ['schedule_seconds', 'lora_settings', 'capture_interval_seconds', 'gradient_accumulation_steps', 'checkpoint_dir']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

    @property
    def webcam_url(self) -> str:
        # Prefer webcam from mountain TOML if available
        if 'webcam' in self.target_data and 'url' in self.target_data['webcam']:
            return self.target_data['webcam']['url']
        # Fallback to first source in main config if it exists (legacy support)
        sources = self.config.get('webcam_sources', [])
        return sources[0] if sources else ""

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
    def checkpoint_dir(self) -> str:
        return self.config['checkpoint_dir']

    @property
    def metar_station(self) -> str:
        # Prefer station from mountain TOML if available
        if 'weather' in self.target_data and 'station_id' in self.target_data['weather']:
            return self.target_data['weather']['station_id']
        return self.config.get('metar_station', 'KSEA')

    @property
    def mountain_data(self) -> Dict[str, Any]:
        return self.target_data.get('mountain', {})
