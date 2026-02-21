import pytest
import yaml
import tomli_w # for writing test tomls
import os
from config_loader import ConfigLoader

def test_config_loader_merge(tmp_path):
    # YAML config
    config_file = tmp_path / "config.yaml"
    config_data = {
        'webcam_sources': [0],
        'schedule': ['0 12 * * *'],
        'lora_settings': {'rank': 4, 'alpha': 8, 'target_modules': ['fc1']}
    }
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    # TOML target config
    toml_file = tmp_path / "the.mountain.toml"
    toml_data = {
        'mountain': {'name': 'Mount Rainier', 'height': 14411},
        'webcams': [{'url': 'http://rainier-webcam.jpg', 'name': 'Rainier View'}],
        'weather': {'primary_metar': 'KTCM'}
    }
    with open(toml_file, 'wb') as f:
        f.write(tomli_w.dumps(toml_data).encode())
    
    loader = ConfigLoader(str(config_file), str(toml_file))
    
    # Sources should be merged and unique (0 and the URL)
    assert len(loader.webcam_sources) == 2
    assert 0 in loader.webcam_sources
    assert 'http://rainier-webcam.jpg' in loader.webcam_sources
    
    # Metar station should prefer TOML
    assert loader.metar_station == 'KTCM'
    
    # Mountain data
    assert loader.mountain_data['name'] == 'Mount Rainier'

def test_config_loader_no_toml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_data = {
        'webcam_sources': [0],
        'schedule': ['0 12 * * *'],
        'lora_settings': {'rank': 4, 'alpha': 8, 'target_modules': ['fc1']},
        'metar_station': 'KSEA'
    }
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    loader = ConfigLoader(str(config_file))
    assert loader.webcam_sources == [0]
    assert loader.metar_station == 'KSEA'
