import pytest
import tomli_w
import os
from train.config_loader import ConfigLoader

def test_config_loader_merge(tmp_path):
    # Main TOML config
    config_file = tmp_path / "config.toml"
    config_data = {
        'webcam_sources': ['old_cam.jpg'],
        'schedule_seconds': 1800,
        'capture_interval_seconds': 300,
        'gradient_accumulation_steps': 4,
        'checkpoint_dir': 'checkpoints',
        'lora_settings': {'rank': 4, 'alpha': 8, 'target_modules': ['fc1']}
    }
    with open(config_file, 'wb') as f:
        f.write(tomli_w.dumps(config_data).encode())
    
    # Mountain TOML config
    toml_file = tmp_path / "mountain.toml"
    toml_data = {
        'mountain': {'name': 'Mount Rainier', 'height': 14411},
        'webcam': {'url': 'http://rainier-webcam.jpg', 'name': 'Rainier View'},
        'weather': {'station_id': 'KTCM'}
    }
    with open(toml_file, 'wb') as f:
        f.write(tomli_w.dumps(toml_data).encode())
    
    loader = ConfigLoader(str(config_file), str(toml_file))
    
    # webcam_url should prefer TOML
    assert loader.webcam_url == 'http://rainier-webcam.jpg'
    
    # Metar station should prefer TOML
    assert loader.metar_station == 'KTCM'
    
    # Mountain data
    assert loader.mountain_data['name'] == 'Mount Rainier'

def test_config_loader_no_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_data = {
        'webcam_sources': ['fallback.jpg'],
        'schedule_seconds': 1800,
        'capture_interval_seconds': 300,
        'gradient_accumulation_steps': 4,
        'checkpoint_dir': 'checkpoints',
        'lora_settings': {'rank': 4, 'alpha': 8, 'target_modules': ['fc1']},
        'metar_station': 'KSEA'
    }
    with open(config_file, 'wb') as f:
        f.write(tomli_w.dumps(config_data).encode())
    
    loader = ConfigLoader(str(config_file))
    assert loader.webcam_url == 'fallback.jpg'
    assert loader.metar_station == 'KSEA'
