import pytest
import torch
import torch.optim as optim
from unittest.mock import MagicMock, patch
from scheduler import TrainingScheduler

@patch('scheduler.ConfigLoader')
@patch('scheduler.ConvNextLoRAModel')
@patch('scheduler.BackgroundScheduler')
@patch('scheduler.WeatherFetcher')
def test_scheduler_initialization(mock_weather, mock_aps, mock_model_cls, mock_config):
    """Verify that the scheduler initializes and sets up jobs correctly."""
    mock_config.return_value.schedule = ['0 12 * * *']
    mock_config.return_value.metar_station = 'KSEA'
    mock_config.return_value.lora_settings = {
        'rank': 8, 'alpha': 16, 'target_modules': ['fc1']
    }
    
    # Mock model parameters
    mock_model = MagicMock()
    mock_model.model.parameters.return_value = [torch.nn.Parameter(torch.randn(1))]
    mock_model_cls.return_value = mock_model
    
    trainer = TrainingScheduler('dummy_path.yaml', 'dummy_mountain.toml')
    
    # Check if jobs were added
    trainer.scheduler.add_job.assert_called_once()
    assert mock_model_cls.called
    assert mock_weather.called

@patch('scheduler.WebcamStream')
@patch('scheduler.WeatherFetcher')
def test_batch_training_cycle_execution(mock_weather_cls, mock_webcam):
    """Verify that training_cycle captures multiple frames and performs a batch training step."""
    with patch('scheduler.ConfigLoader') as mock_config:
        mock_config.return_value.webcam_sources = [0, 1]
        mock_config.return_value.metar_station = 'KSEA'
        mock_config.return_value.schedule = ['* * * * *']
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
            
            trainer = TrainingScheduler('dummy_path.yaml')
            
            # Mock successful webcam captures
            mock_stream = MagicMock()
            mock_tensor = torch.randn(1, 3, 224, 224)
            mock_stream.capture_to_tensor.return_value = mock_tensor
            mock_webcam.return_value = mock_stream
            
            trainer.optimizer = MagicMock()
            
            # Run the training cycle
            trainer.training_cycle(label=1)
            
            # Verify interactions
            assert mock_stream.capture_to_tensor.call_count == 2
            # Batch should contain 2 samples
            args, _ = mock_model.train_step.call_args
            image_batch, weather_batch, label_batch, _ = args
            assert image_batch.shape == (2, 3, 224, 224)
            assert weather_batch.shape == (2, 2)
            assert label_batch.shape == (2,)
