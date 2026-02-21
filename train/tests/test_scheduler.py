import pytest
import torch
import torch.optim as optim
from unittest.mock import MagicMock, patch
from scheduler import Trainer

@patch('scheduler.ConfigLoader')
@patch('scheduler.ConvNextLoRAModel')
@patch('scheduler.WeatherFetcher')
def test_trainer_initialization(mock_weather, mock_model_cls, mock_config):
    """Verify that the trainer initializes correctly."""
    mock_config.return_value.metar_station = 'KSEA'
    mock_config.return_value.lora_settings = {
        'rank': 8, 'alpha': 16, 'target_modules': ['fc1']
    }
    
    mock_model = MagicMock()
    mock_model.model.parameters.return_value = [torch.nn.Parameter(torch.randn(1))]
    mock_model_cls.return_value = mock_model
    
    trainer = Trainer('dummy_path.toml', 'dummy_mountain.toml')
    
    assert mock_model_cls.called
    assert mock_weather.called

@patch('scheduler.WebcamStream')
@patch('scheduler.WeatherFetcher')
def test_run_single_cycle_execution(mock_weather_cls, mock_webcam):
    """Verify that run_single_cycle captures multiple frames and performs a training step."""
    with patch('scheduler.ConfigLoader') as mock_config:
        mock_config.return_value.webcam_sources = [0, 1]
        mock_config.return_value.metar_station = 'KSEA'
        mock_config.return_value.lora_settings = {
            'rank': 8, 'alpha': 16, 'target_modules': ['fc1']
        }
        
        with patch('scheduler.ConvNextLoRAModel') as mock_model_cls:
            mock_model = MagicMock()
            mock_model.model.parameters.return_value = [torch.nn.Parameter(torch.randn(1))]
            mock_model.train_step.return_value = 0.5
            mock_model_cls.return_value = mock_model
            
            mock_weather = MagicMock()
            mock_weather_vector = torch.tensor([0.8, 0.9])
            mock_weather.get_weather_vector.return_value = mock_weather_vector
            mock_weather_cls.return_value = mock_weather
            
            trainer = Trainer('dummy_path.toml')
            trainer.optimizer = MagicMock()
            
            mock_stream = MagicMock()
            mock_tensor = torch.randn(1, 3, 224, 224)
            mock_stream.capture_to_tensor.return_value = mock_tensor
            mock_webcam.return_value = mock_stream
            
            trainer.run_single_cycle(label=1)
            
            assert mock_stream.capture_to_tensor.call_count == 2
            args, _ = mock_model.train_step.call_args
            image_batch, weather_batch, label_batch, _ = args
            assert image_batch.shape == (2, 3, 224, 224)
            assert weather_batch.shape == (2, 2)
            assert label_batch.shape == (2,)

@patch('scheduler.WebcamStream')
@patch('scheduler.WeatherFetcher')
@patch('time.sleep', side_effect=InterruptedError) 
def test_live_training_loop_cycle(mock_sleep, mock_weather_cls, mock_webcam):
    """Verify that live_training_loop captures multiple frames and performs a batch training step."""
    with patch('scheduler.ConfigLoader') as mock_config:
        mock_config.return_value.webcam_sources = [0, 1]
        mock_config.return_value.metar_station = 'KSEA'
        mock_config.return_value.lora_settings = {
            'rank': 8, 'alpha': 16, 'target_modules': ['fc1']
        }
        mock_config.return_value.capture_interval_seconds = 0
        mock_config.return_value.gradient_accumulation_steps = 1
        
        with patch('scheduler.ConvNextLoRAModel') as mock_model_cls:
            mock_model = MagicMock()
            mock_model.model.parameters.return_value = [torch.nn.Parameter(torch.randn(1))]
            mock_model.train_step.return_value = 0.5
            mock_model_cls.return_value = mock_model
            
            mock_weather = MagicMock()
            mock_weather_vector = torch.tensor([0.8, 0.9])
            mock_weather.get_weather_vector.return_value = mock_weather_vector
            mock_weather_cls.return_value = mock_weather
            
            trainer = Trainer('dummy_path.toml')
            trainer.optimizer = MagicMock()
            
            mock_stream = MagicMock()
            mock_tensor = torch.randn(1, 3, 224, 224)
            mock_stream.capture_to_tensor.return_value = mock_tensor
            mock_webcam.return_value = mock_stream
            
            with pytest.raises(InterruptedError):
                trainer.live_training_loop(label=1)
            
            assert mock_stream.capture_to_tensor.call_count == 2
