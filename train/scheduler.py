import time
import torch
import torch.optim as optim
from datetime import datetime
from typing import Optional, List
import typer
import os
from pathlib import Path
import subprocess

from train.config_loader import ConfigLoader
from train.utils import WebcamStream, WeatherFetcher
from train.model import ConvNextLoRAModel

app = typer.Typer()

class Trainer:
    def __init__(self, config_path: str = "mountain.toml"):
        self.config_loader = ConfigLoader(config_path)
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        
        # Initialize components
        self.model_wrapper = ConvNextLoRAModel(
            num_classes=3,
            rank=self.config_loader.lora_settings['rank'],
            alpha=self.config_loader.lora_settings['alpha'],
            target_modules=self.config_loader.lora_settings['target_modules'],
            device=self.device
        )
        
        # Attempt to load checkpoint
        self.model_wrapper.load_checkpoint(self.config_loader.checkpoint_dir)
        
        # Lower learning rate for fine-tuning stability
        self.optimizer = optim.Adam(self.model_wrapper.model_dict.parameters(), lr=0.0001)
        self.weather_fetcher = WeatherFetcher(self.config_loader.metar_station)

    def run_single_cycle(self, label: int = 1):
        print(f"[{datetime.now()}] Starting single training cycle...")
        weather_vector = self.weather_fetcher.get_weather_vector()
        
        source = self.config_loader.webcam_url
        stream = WebcamStream(source, device=self.device)
        try:
            tensor = stream.capture_to_tensor()
            if tensor is not None:
                # Still use batch format even for single image
                image_batch = tensor
                weather_batch = weather_vector.unsqueeze(0)
                label_batch = torch.tensor([label]).to(self.device)
                
                loss = self.model_wrapper.train_step(image_batch, weather_batch, label_batch, self.optimizer)
                print(f"[{datetime.now()}] Cycle Complete: Loss = {loss:.4f}")
                self.model_wrapper.save_checkpoint(self.config_loader.checkpoint_dir)
            else:
                print(f"  Source {source}: Capture failed.")
        finally:
            stream.release()

    def live_training_loop(self, label: int = 1):
        print(f"[{datetime.now()}] Starting continuous live training loop...")
        image_list = []
        weather_list = []
        label_list = []
        
        source = self.config_loader.webcam_url
        try:
            while True:
                weather_vector = self.weather_fetcher.get_weather_vector()
                stream = WebcamStream(source, device=self.device)
                try:
                    tensor = stream.capture_to_tensor()
                    if tensor is not None:
                        image_list.append(tensor.squeeze(0))
                        weather_list.append(weather_vector)
                        label_list.append(torch.tensor(label))
                        print(f"  Captured from {source}")
                    else:
                        print(f"  Source {source}: Capture failed.")
                finally:
                    stream.release()
                
                if image_list:
                    current_accum = len(image_list)
                    print(f"  Accumulation step {current_accum}/{self.config_loader.gradient_accumulation_steps}")
                    
                    if current_accum >= self.config_loader.gradient_accumulation_steps:
                        image_batch = torch.stack(image_list)
                        weather_batch = torch.stack(weather_list)
                        label_batch = torch.stack(label_list)
                        loss = self.model_wrapper.train_step(image_batch, weather_batch, label_batch, self.optimizer)
                        print(f"[{datetime.now()}] Batch Training Complete: Loss = {loss:.4f}")
                        self.model_wrapper.save_checkpoint(self.config_loader.checkpoint_dir)
                        image_list, weather_list, label_list = [], [], []
                
                time.sleep(self.config_loader.capture_interval_seconds)
        except (KeyboardInterrupt, SystemExit):
            print("\nExiting live training loop.")

@app.command()
def once(config: str = "mountain.toml"):
    """Performs a single capture and training cycle and then exits."""
    trainer = Trainer(config)
    trainer.run_single_cycle()

@app.command()
def live(config: str = "mountain.toml"):
    """Runs a continuous loop capturing images and weather data to train the model."""
    trainer = Trainer(config)
    trainer.live_training_loop()

@app.command()
def batch(folder: str, label: Optional[int] = None, config: str = "mountain.toml"):
    """Runs training on a folder. If labels.yaml is present in the folder, it uses those labels."""
    trainer = Trainer(config)
    data_root = Path(folder)
    labels_file = data_root / "labels.yaml"
    
    import yaml
    import cv2
    from torchvision import transforms
    from metar import Metar

    # Strategy: Use labels.yaml if exists, otherwise fallback to folder-wide label
    labels_map = {}
    if labels_file.exists():
        with open(labels_file, 'r') as f:
            labels_map = yaml.safe_load(f) or {}
        print(f"Loaded {len(labels_map)} labels from {labels_file}")
    
    # Calculate class weights based on labels_map
    all_label_values = list(labels_map.values())
    count_0 = all_label_values.count(0)
    count_1 = all_label_values.count(1)
    
    # Avoid division by zero
    w0 = 1.0 / (count_0 if count_0 > 0 else 1)
    w1 = 1.0 / (count_1 if count_1 > 0 else 1)
    
    # Strategy: Oversample minority classes (Full = 1, Partial = 2)
    labels_full = {path: label for path, label in labels_map.items() if label == 1}
    labels_partial = {path: label for path, label in labels_map.items() if label == 2}
    labels_not_out = {path: label for path, label in labels_map.items() if label == 0}

    print(f"Dataset stats: {len(labels_not_out)} Not Out, {len(labels_full)} Full, {len(labels_partial)} Partial")

    # We want a reasonable representation of all visible mountain frames
    # Target: 1:2:2 ratio (NotOut : Full : Partial) or similar
    max_not_out = len(labels_not_out)

    final_training_list = []
    # Add all 'Not Out' once
    for p, l in labels_not_out.items():
        final_training_list.append((p, l))

    # Oversample 'Full'
    if labels_full:
        full_factor = max(1, max_not_out // (len(labels_full) * 2))
        for p, l in labels_full.items():
            for _ in range(full_factor):
                final_training_list.append((p, l))
        print(f"  Oversampling 'Full' by {full_factor}x")

    # Oversample 'Partial'
    if labels_partial:
        partial_factor = max(1, max_not_out // (len(labels_partial) * 2))
        for p, l in labels_partial.items():
            for _ in range(partial_factor):
                final_training_list.append((p, l))
        print(f"  Oversampling 'Partial' by {partial_factor}x")

    import random
    random.shuffle(final_training_list)

    print(f"Final training set size: {len(final_training_list)} samples.")

    batch_size = 16
    
    from torchvision import transforms
    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    for epoch in range(epochs):
        random.shuffle(final_training_list)
        print(f"Epoch {epoch+1}/{epochs}...")
        
        image_list, weather_list, label_list = [], [], []
        
        for rel_path, img_label in final_training_list:
            img_p = data_root / rel_path
            # ... (Existing logic to load image and metar)
            metar_p = img_p.parent.parent / "metar" / f"{img_p.stem}.txt"
            if not metar_p.exists(): metar_p = img_p.parent.parent / "metar" / "metar.txt"
            if not metar_p.exists(): metar_p = img_p.parent / f"{img_p.stem}.txt"
            if not metar_p.exists(): continue

            frame = cv2.imread(str(img_p))
            if frame is None: continue
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor = transform(frame_rgb).to(trainer.device)
            
            with open(metar_p, 'r') as f: metar_text = f.read().strip()
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
            label_list.append(torch.tensor(img_label))
            
            if len(image_list) >= batch_size:
                loss = trainer.model_wrapper.train_step(torch.stack(image_list), torch.stack(weather_list), torch.stack(label_list), trainer.optimizer)
                image_list, weather_list, label_list = [], [], []

        if image_list:
            trainer.model_wrapper.train_step(torch.stack(image_list), torch.stack(weather_list), torch.stack(label_list), trainer.optimizer)
        
        print(f"Epoch {epoch+1} complete.")
    
    trainer.model_wrapper.save_checkpoint(trainer.config_loader.checkpoint_dir)

@app.command()
def schedule(config: str = "mountain.toml"):
    """Installs the launchctl service for periodic training."""
    trainer = Trainer(config)
    config_loader = trainer.config_loader
    current_dir = Path.cwd().absolute()
    executable = subprocess.check_output(["which", "uv"], text=True).strip()
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.mountain.trainer.plist"
    
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
        <string>training</string>
        <string>once</string>
        <string>--config</string>
        <string>{current_dir / config}</string>
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
    with open(plist_path, "w") as f: f.write(plist_content)
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist_path)])
    print(f"Service installed at {plist_path}. Interval: {config_loader.schedule_seconds}s")

@app.command()
def unschedule():
    """Unloads and removes the launchctl service."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.mountain.trainer.plist"
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        plist_path.unlink()
        print(f"Service removed.")
    else: print("Service not found.")

if __name__ == "__main__":
    app()
