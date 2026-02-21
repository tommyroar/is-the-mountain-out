import time
import torch
import torch.optim as optim
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

class Trainer:
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

    def live_training_cycle(self, label: int = 1):
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

@app.command()
def live(config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Collects latest webcam images and METAR and runs the training loop once."""
    trainer = Trainer(config, mountain)
    trainer.live_training_cycle()

@app.command()
def batch(folder: str, label: int = 1, config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Runs the training loop on all valid inputs in a folder with /images and /metar subfolders."""
    trainer = Trainer(config, mountain)
    
    image_dir = Path(folder) / "images"
    metar_dir = Path(folder) / "metar"
    
    if not image_dir.exists() or not metar_dir.exists():
        print(f"Error: Folder {folder} must contain /images and /metar subfolders.")
        raise typer.Exit(code=1)
        
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
        if not metar_p.exists(): continue
            
        frame = cv2.imread(str(img_p))
        if frame is None: continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = transform(frame_rgb).to(trainer.device)
        
        with open(metar_p, 'r') as f:
            metar_text = f.read().strip()
        
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
        
        if len(image_list) >= 8:
            loss = trainer.model_wrapper.train_step(
                torch.stack(image_list), torch.stack(weather_list), 
                torch.stack(label_list), trainer.optimizer
            )
            print(f"Processed batch: Loss = {loss:.4f}")
            image_list, weather_list, label_list = [], [], []

    if image_list:
        loss = trainer.model_wrapper.train_step(
            torch.stack(image_list), torch.stack(weather_list), 
            torch.stack(label_list), trainer.optimizer
        )
        print(f"Final batch: Loss = {loss:.4f}")

@app.command()
def schedule(config: str = "config.toml", mountain: str = "../mountain.toml"):
    """Installs the launchctl service for continuous training."""
    trainer = Trainer(config, mountain)
    config_loader = trainer.config_loader
    
    # Path setup
    current_dir = Path.cwd().absolute()
    executable = subprocess.check_output(["which", "uv"], text=True).strip()
    plist_name = "com.mountain.trainer.plist"
    plist_path = Path.home() / "Library" / "LaunchAgents" / plist_name
    
    # Generate Plist content
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mountain.trainer</string>
    <key>ProgramArguments</key>
    <array>
        <string>{executable}</string>
        <string>run</string>
        <string>python</string>
        <string>{current_dir / "scheduler.py"}</string>
        <string>live</string>
        <string>--config</string>
        <string>{current_dir / config}</string>
        <string>--mountain</string>
        <string>{current_dir / mountain}</string>
    </array>
    <key>StartInterval</key>
    <integer>{config_loader.schedule_seconds}</integer>
    <key>StandardErrorPath</key>
    <string>/tmp/mountain_trainer.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/mountain_trainer.out</string>
    <key>WorkingDirectory</key>
    <string>{current_dir}</string>
</dict>
</plist>
"""
    
    with open(plist_path, "w") as f:
        f.write(plist_content)
        
    # Load the service
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist_path)])
    
    print(f"Service installed and loaded at {plist_path}")
    print(f"Running every {config_loader.schedule_seconds} seconds.")

@app.command()
def unschedule():
    """Unloads and removes the launchctl service."""
    plist_name = "com.mountain.trainer.plist"
    plist_path = Path.home() / "Library" / "LaunchAgents" / plist_name
    
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        plist_path.unlink()
        print(f"Service unloaded and removed from {plist_path}")
    else:
        print("Service plist not found. Nothing to remove.")

if __name__ == "__main__":
    app()
