import typer
import os
from pathlib import Path
from datetime import datetime
import cv2
from typing import Optional

from train.config_loader import ConfigLoader
from train.utils import WebcamStream, WeatherFetcher

app = typer.Typer()

@app.command()
def collect(config: str = "train/config.toml", mountain: str = "mountain.toml", data_root: str = "data"):
    """
    Runs a single capture of each webcam and METAR data, saving them into a datestamped directory.
    """
    config_loader = ConfigLoader(config, mountain)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    
    # Create datestamped directory
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    collection_dir = Path(data_root) / timestamp
    image_dir = collection_dir / "images"
    metar_dir = collection_dir / "metar"
    
    image_dir.mkdir(parents=True, exist_ok=True)
    metar_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[{now}] Starting collection into {collection_dir}...")
    
    # Fetch METAR once for this cycle
    metar_text = weather_fetcher.fetch_latest_metar()
    if metar_text:
        with open(metar_dir / "metar.txt", "w") as f:
            f.write(metar_text)
        print("  METAR data saved.")
    else:
        print("  Warning: METAR capture failed.")
    
    # Capture from each source
    for idx, source in enumerate(config_loader.webcam_sources):
        stream = WebcamStream(source)
        try:
            frame = stream.capture_raw()
            if frame is not None:
                # Sanitize filename if source is a URL
                safe_name = str(source).replace("/", "_").replace(":", "_").replace(".", "_")
                filename = f"cam_{idx}_{safe_name}.jpg"
                cv2.imwrite(str(image_dir / filename), frame)
                print(f"  Source {source}: Saved as {filename}")
            else:
                print(f"  Source {source}: Capture failed.")
        finally:
            stream.release()
            
    print(f"[{datetime.now()}] Collection complete.")

if __name__ == "__main__":
    app()
