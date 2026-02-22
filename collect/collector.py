import time
import typer
import os
import subprocess
from pathlib import Path
from datetime import datetime, UTC
import cv2
from typing import Optional, Dict

from train.config_loader import ConfigLoader
from train.utils import WebcamStream, WeatherFetcher

app = typer.Typer()

def perform_capture(config_loader: ConfigLoader, weather_fetcher: WeatherFetcher, data_root: str = "data"):
    """Core logic to capture a single image and METAR data with UTC-based naming."""
    now_utc = datetime.now(UTC)
    date_str = now_utc.strftime("%Y%m%d")
    # Include microseconds to avoid collisions in concurrent runs
    time_str = now_utc.strftime("%H%M%S_%f_UTC")
    
    # Structure: data/YYYYMMDD/HHMMSS_micro_UTC/
    capture_dir = Path(data_root) / date_str / time_str
    image_dir = capture_dir / "images"
    metar_dir = capture_dir / "metar"
    
    image_dir.mkdir(parents=True, exist_ok=True)
    metar_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[{now_utc}] Starting collection into {capture_dir}...")
    
    # Fetch and save METAR
    metar_text = weather_fetcher.fetch_latest_metar()
    if metar_text:
        with open(metar_dir / "metar.txt", "w") as f:
            f.write(metar_text)
        print("  METAR data saved.")
    else:
        print("  Warning: METAR capture failed.")
    
    # Capture and save image
    source = config_loader.webcam_url
    if not source:
        print("Error: No webcam source configured.")
        return False
        
    stream = WebcamStream(source)
    try:
        frame = stream.capture_raw()
        if frame is not None:
            safe_name = str(source).replace("/", "_").replace(":", "_").replace(".", "_")
            filename = f"{time_str}_{safe_name}.jpg"
            cv2.imwrite(str(image_dir / filename), frame)
            print(f"  Source {source}: Saved as {filename}")
            return True
        else:
            print(f"  Source {source}: Capture failed.")
            return False
    finally:
        stream.release()

@app.command()
def collect(config: str = "mountain.toml", data_root: str = "data"):
    """
    Runs a single capture of the configured webcam and METAR data.
    """
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    perform_capture(config_loader, weather_fetcher, data_root)
    print(f"[{datetime.now(UTC)}] Collection complete.")

@app.command()
def live(config: str = "mountain.toml", data_root: str = "data"):
    """
    Runs continuous collection in the foreground using the configured interval.
    """
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    interval = config_loader.collection_seconds
    
    print(f"Starting live collection loop (interval: {interval}s). Press Ctrl+C to stop.")
    try:
        while True:
            perform_capture(config_loader, weather_fetcher, data_root)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping live collection.")

def generate_calendar_plist(schedule: Dict[str, int]) -> str:
    """Generates the StartCalendarInterval portion of a plist."""
    lines = ["    <key>StartCalendarInterval</key>", "    <dict>"]
    for key, val in schedule.items():
        lines.append(f"        <key>{key}</key>")
        lines.append(f"        <integer>{val}</integer>")
    lines.append("    </dict>")
    return "\n".join(lines)

@app.command()
def schedule(config: str = "mountain.toml"):
    """Installs the launchctl service for periodic collection."""
    config_loader = ConfigLoader(config)
    current_dir = Path.cwd().absolute()
    executable = subprocess.check_output(["which", "uv"], text=True).strip()
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.mountain.collector.plist"
    
    # Timing logic: prefer schedule (calendar-based) over interval
    timing_config = ""
    if config_loader.collection_schedule:
        timing_config = generate_calendar_plist(config_loader.collection_schedule)
    else:
        timing_config = f"    <key>StartInterval</key>\n    <integer>{config_loader.collection_seconds}</integer>"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mountain.collector</string>
    <key>ProgramArguments</key>
    <array>
        <string>{executable}</string>
        <string>run</string>
        <string>collect</string>
        <string>collect</string>
        <string>--config</string>
        <string>{current_dir / config}</string>
    </array>
{timing_config}
    <key>StandardErrorPath</key>
    <string>/tmp/mountain_collector.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/mountain_collector.out</string>
    <key>WorkingDirectory</key>
    <string>{current_dir}</string>
</dict>
</plist>
"""
    with open(plist_path, "w") as f: f.write(plist_content)
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist_path)])
    print(f"Service installed at {plist_path}.")
    if config_loader.collection_schedule:
        print(f"Schedule: {config_loader.collection_schedule}")
    else:
        print(f"Interval: {config_loader.collection_seconds}s")

@app.command()
def unschedule():
    """Unloads and removes the launchctl service."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.mountain.collector.plist"
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        plist_path.unlink()
        print(f"Service removed.")
    else: print("Service not found.")

if __name__ == "__main__":
    app()
