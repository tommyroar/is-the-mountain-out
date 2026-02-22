import pytest
from unittest.mock import MagicMock, patch
from collect.collector import collect, live
from pathlib import Path
import os
import shutil
from datetime import datetime, UTC

@patch('collect.collector.ConfigLoader')
@patch('collect.collector.WebcamStream')
@patch('collect.collector.WeatherFetcher')
def test_collect_execution_utc_structure(mock_weather_cls, mock_webcam, mock_config, tmp_path):
    """Verify that collect function uses the new UTC-based directory structure."""
    mock_config.return_value.webcam_url = 'http://cam.jpg'
    mock_config.return_value.metar_station = 'KSEA'
    
    mock_weather = MagicMock()
    mock_weather.fetch_latest_metar.return_value = "METAR KSEA 211953Z CLR 10/05"
    mock_weather_cls.return_value = mock_weather
    
    mock_stream = MagicMock()
    mock_stream.capture_raw.return_value = MagicMock()
    mock_webcam.return_value = mock_stream
    
    with patch('cv2.imwrite') as mock_imwrite:
        collect(config='mountain.toml', data_root=str(tmp_path))
        
        # Structure: data/YYYYMMDD/HHMMSS_UTC/
        now_utc = datetime.now(UTC)
        date_str = now_utc.strftime("%Y%m%d")
        
        date_dir = tmp_path / date_str
        assert date_dir.exists()
        
        time_dir = next(date_dir.iterdir())
        assert time_dir.name.endswith("_UTC")
        assert (time_dir / "images").exists()
        assert (time_dir / "metar").exists()
        assert (time_dir / "metar" / "metar.txt").exists()
        assert mock_imwrite.called

@patch('collect.collector.ConfigLoader')
@patch('collect.collector.WebcamStream')
@patch('collect.collector.WeatherFetcher')
@patch('time.sleep', side_effect=KeyboardInterrupt)
def test_live_collection_loop(mock_sleep, mock_weather_cls, mock_webcam, mock_config, tmp_path):
    """Verify that live command runs a loop and stops on KeyboardInterrupt."""
    mock_config.return_value.webcam_url = 'http://cam.jpg'
    mock_config.return_value.metar_station = 'KSEA'
    mock_config.return_value.collection_seconds = 1
    
    mock_weather = MagicMock()
    mock_weather.fetch_latest_metar.return_value = "METAR KSEA"
    mock_weather_cls.return_value = mock_weather
    
    mock_stream = MagicMock()
    mock_stream.capture_raw.return_value = MagicMock()
    mock_webcam.return_value = mock_stream
    
    with patch('cv2.imwrite'):
        # This will run one iteration and then 'sleep' will raise KeyboardInterrupt
        live(config='mountain.toml', data_root=str(tmp_path))
        
        # Check if directories were created for the first run
        now_utc = datetime.now(UTC)
        date_str = now_utc.strftime("%Y%m%d")
        assert (tmp_path / date_str).exists()
