import time
import torch
import torch.optim as optim
from apscheduler.schedulers.background import BackgroundScheduler
from croniter import croniter
from datetime import datetime
from typing import Optional, List

from config_loader import ConfigLoader
from webcam import WebcamStream
from model import ConvNextLoRAModel
from weather import WeatherFetcher

class TrainingScheduler:
    def __init__(self, config_path: str, target_toml_path: Optional[str] = None):
        self.config_loader = ConfigLoader(config_path, target_toml_path)
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        
        # Initialize components
        self.model_wrapper = ConvNextLoRAModel(
            num_classes=2,
            rank=self.config_loader.lora_settings['rank'],
            alpha=self.config_loader.lora_settings['alpha'],
            target_modules=self.config_loader.lora_settings['target_modules'],
            device=self.device
        )
        self.optimizer = optim.Adam(self.model_wrapper.model.parameters(), lr=0.001)
        self.weather_fetcher = WeatherFetcher(self.config_loader.metar_station)
        
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        for cron_str in self.config_loader.schedule:
            fields = cron_str.split()
            if len(fields) == 5:
                self.scheduler.add_job(
                    self.training_cycle,
                    'cron',
                    minute=fields[0],
                    hour=fields[1],
                    day=fields[2],
                    month=fields[3],
                    day_of_week=fields[4]
                )

    def training_cycle(self, label: int = 1):
        """
        Collects frames from all sources and performs a batch training step.
        """
        print(f"[{datetime.now()}] Starting batch training cycle...")
        
        weather_vector = self.weather_fetcher.get_weather_vector()
        print(f"  Current Weather Vector (Vis, Ceil): {weather_vector.tolist()}")
        
        image_list = []
        weather_list = []
        label_list = []
        
        for source in self.config_loader.webcam_sources:
            stream = WebcamStream(source, device=self.device)
            try:
                tensor = stream.capture_to_tensor() # Shape [1, 3, 224, 224]
                if tensor is not None:
                    # Collect components for batch
                    image_list.append(tensor.squeeze(0)) # Shape [3, 224, 224]
                    weather_list.append(weather_vector) # Shape [2]
                    label_list.append(torch.tensor(label))
                    print(f"  Source {source}: Captured.")
                else:
                    print(f"  Source {source}: Capture failed.")
            finally:
                stream.release()
        
        if image_list:
            # Create batches
            image_batch = torch.stack(image_list) # [B, 3, 224, 224]
            weather_batch = torch.stack(weather_list) # [B, 2]
            label_batch = torch.stack(label_list) # [B]
            
            # Batch training step
            loss = self.model_wrapper.train_step(image_batch, weather_batch, label_batch, self.optimizer)
            print(f"[{datetime.now()}] Batch Training Step Complete: Loss = {loss:.4f}")
        else:
            print(f"[{datetime.now()}] Training skipped: No frames captured.")

    def start(self):
        self.scheduler.start()
        print("Scheduler started. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()

def run_training():
    """Entry point for uv run training."""
    import sys
    import os
    config_p = "config.toml"
    target_p = "../mountain.toml"
    
    # Check current directory
    if not os.path.exists(config_p):
        print(f"Warning: {config_p} not found in current directory. Searching...")
    
    trainer = TrainingScheduler(config_p, target_p)
    trainer.start()

if __name__ == "__main__":
    run_training()
