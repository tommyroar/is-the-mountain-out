import yaml
import tomli
from croniter import croniter
from typing import List, Dict, Any, Optional

class ConfigLoader:
    def __init__(self, config_path: str, target_toml_path: Optional[str] = None):
        self.config_path = config_path
        self.target_toml_path = target_toml_path
        
        self.config = self._load_yaml_config()
        self.target_data = self._load_toml_config() if target_toml_path else {}
        
        self._validate_config()

    def _load_yaml_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _load_toml_config(self) -> Dict[str, Any]:
        with open(self.target_toml_path, 'rb') as f:
            return tomli.load(f)

    def _validate_config(self):
        # Basic YAML config validation
        required_keys = ['schedule', 'lora_settings']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

        # Validate schedule strings
        for cron_str in self.config['schedule']:
            if not croniter.is_valid(cron_str):
                raise ValueError(f"Invalid crontab string: {cron_str}")

    @property
    def webcam_sources(self) -> List[Any]:
        # Merge sources from YAML and TOML
        sources = self.config.get('webcam_sources', [])
        if 'webcams' in self.target_data:
            sources.extend([cam['url'] for cam in self.target_data['webcams']])
        return list(set(sources)) # Unique sources

    @property
    def schedule(self) -> List[str]:
        return self.config['schedule']

    @property
    def lora_settings(self) -> Dict[str, Any]:
        return self.config['lora_settings']

    @property
    def metar_station(self) -> str:
        # Prefer station from TOML if available
        if 'weather' in self.target_data and 'primary_metar' in self.target_data['weather']:
            return self.target_data['weather']['primary_metar']
        return self.config.get('metar_station', 'KSEA')

    @property
    def mountain_data(self) -> Dict[str, Any]:
        return self.target_data.get('mountain', {})
