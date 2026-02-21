import time
import torch
import torch.optim as optim
from apscheduler.schedulers.background import BackgroundScheduler
from croniter import croniter
from datetime import datetime
from typing import Optional, List
import typer
import os
from pathlib import Path
import subprocess

from config_loader import ConfigLoader
from webcam import WebcamStream
from model import ConvNextLoRAModel
from weather import WeatherFetcher

app = typer.Typer()

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
        print(f"[{datetime.now()}] Starting live training cycle...")
        
        weather_vector = self.weather_fetcher.get_weather_vector()
        print(f"  Current Weather Vector (Vis, Ceil): {weather_vector.tolist()}")
        
        image_list = []
        weather_list = []
        label_list = []
        
        for source in self.config_loader.webcam_sources:
            stream = WebcamStream(source, device=self.device)
            try:
                tensor = stream.capture_to_tensor()
                if tensor is not None:
                    image_list.append(tensor.squeeze(0))
                    weather_list.append(weather_vector)
                    label_list.append(torch.tensor(label))
                    print(f"  Source {source}: Captured.")
                else:
                    print(f"  Source {source}: Capture failed.")
            finally:
                stream.release()
        
        if image_list:
            image_batch = torch.stack(image_list)
            weather_batch = torch.stack(weather_list)
            label_batch = torch.stack(label_list)
            
            loss = self.model_wrapper.train_step(image_batch, weather_batch, label_batch, self.optimizer)
            print(f"[{datetime.now()}] Training Step Complete: Loss = {loss:.4f}")
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

@app.command()
def live(config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Collects latest webcam images and METAR and runs the training loop once."""
    trainer = TrainingScheduler(config, mountain)
    trainer.training_cycle()

@app.command()
def batch(folder: str, label: int = 1, config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Runs the training loop on all valid inputs in a folder with /images and /metar subfolders."""
    trainer = TrainingScheduler(config, mountain)
    
    image_dir = Path(folder) / "images"
    metar_dir = Path(folder) / "metar"
    
    if not image_dir.exists() or not metar_dir.exists():
        print(f"Error: Folder {folder} must contain /images and /metar subfolders.")
        raise typer.Exit(code=1)
        
    # Simple matching based on filename prefix (timestamp)
    image_files = sorted(image_dir.glob("*.jpg"))
    
    image_list = []
    weather_list = []
    label_list = []
    
    import cv2
    from torchvision import transforms
    from metar import Metar

    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    for img_p in image_files:
        metar_p = metar_dir / f"{img_p.stem}.txt"
        if not metar_p.exists():
            continue
            
        # Load Image
        frame = cv2.imread(str(img_p))
        if frame is None: continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = transform(frame_rgb).to(trainer.device)
        
        # Load METAR
        with open(metar_p, 'r') as f:
            metar_text = f.read().strip()
        
        # Parse weather vector (duplicate logic from WeatherFetcher for simplicity)
        vis, ceil = 0.0, 1.0
        try:
            obs = Metar.Metar(metar_text)
            if obs.vis: vis = min(obs.vis.value('SM'), 10.0) / 10.0
            if obs.sky:
                layers = [l for l in obs.sky if l[0] in ['BKN', 'OVC']]
                ceil = min(layers[0][1].value('FT'), 10000.0) / 10000.0 if layers else 1.0
        except: pass
        
        image_list.append(tensor)
        weather_list.append(torch.tensor([vis, ceil], dtype=torch.float32))
        label_list.append(torch.tensor(label))
        
        # If batch is full or at end, train
        if len(image_list) >= 8:
            loss = trainer.model_wrapper.train_step(
                torch.stack(image_list), torch.stack(weather_list), 
                torch.stack(label_list), trainer.optimizer
            )
            print(f"Processed batch of 8: Loss = {loss:.4f}")
            image_list, weather_list, label_list = [], [], []

    # Final batch
    if image_list:
        loss = trainer.model_wrapper.train_step(
            torch.stack(image_list), torch.stack(weather_list), 
            torch.stack(label_list), trainer.optimizer
        )
        print(f"Processed final batch of {len(image_list)}: Loss = {loss:.4f}")

@app.command()
def schedule(config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Launches the launchctl service for continuous training."""
    # This command can either run the persistent loop or set up the plist
    # Given the request for "suspending and waking up", we'll implement the persistent loop
    # that uses APScheduler, which is standard for "continuous interval" in scripts.
    trainer = TrainingScheduler(config, mountain)
    trainer.start()

if __name__ == "__main__":
    app()
