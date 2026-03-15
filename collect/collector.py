import click
import time
import os
import subprocess
import json
import requests
import signal
import threading
from pathlib import Path
from datetime import datetime, UTC
import cv2
from typing import Optional, Dict, List
import uuid
import yaml
import logging
import rumps

# Assuming 'train' and 'collect' are in the python path.
from train.config_loader import ConfigLoader
from collect.tray import MountainTray
from collect.state import make_state, write_state, read_label_counts

# --- Globals ---
LOG_FILE = "data/collection.log"

# --- Core Business Logic ---

class WebcamStream:
    def __init__(self, url: str):
        self.url = url
        self.cap = cv2.VideoCapture(url)

    def capture_raw(self):
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None

    def release(self):
        self.cap.release()

class WeatherFetcher:
    def __init__(self, station_id: str = "KSEA"):
        self.station_id = station_id
        self.base_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{station_id}.TXT"

    def fetch_latest_metar(self) -> Optional[str]:
        try:
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            lines = response.text.strip().split('\\n')
            return lines[1] if len(lines) >= 2 else lines[0]
        except requests.RequestException as e:
            logging.warning(f"Error fetching METAR: {e}")
        return None

def log_event(event: str, status: str, metadata: Optional[Dict] = None):
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "status": status,
        "metadata": metadata or {}
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

def perform_capture(config_loader: ConfigLoader, weather_fetcher: WeatherFetcher, data_root: str, session_uuid: Optional[str] = None, step_info: Optional[Dict] = None) -> bool:
    now_utc = datetime.now(UTC)
    date_str = now_utc.strftime("%Y%m%d")
    time_str = now_utc.strftime("%H%M%S_%f_UTC")
    
    capture_dir = Path(data_root) / date_str / time_str
    image_dir = capture_dir / "images"
    metar_dir = capture_dir / "metar"
    
    image_dir.mkdir(parents=True, exist_ok=True)
    metar_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Starting collection into {capture_dir}...")
    
    metar_text = weather_fetcher.fetch_latest_metar()
    if metar_text:
        (metar_dir / "metar.txt").write_text(metar_text)
        logging.info("METAR data saved.")
    else:
        logging.warning("METAR capture failed.")

    source = config_loader.webcam_url
    if not source:
        logging.error("No webcam source configured.")
        return False
        
    stream = WebcamStream(source)
    try:
        frame = stream.capture_raw()
        if frame is not None:
            safe_name = str(source).replace("/", "_").replace(":", "_").replace(".", "_")
            filename = f"{time_str}_{safe_name}.jpg"
            image_path = image_dir / filename
            cv2.imwrite(str(image_path), frame)
            logging.info(f"Source {source}: Saved as {filename}")
            return True
        else:
            logging.warning(f"Source {source}: Capture failed.")
            return False
    finally:
        stream.release()

# --- CLI using Click ---

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx, **kwargs):
    """A tool to collect images of Mount Rainier. Defaults to running with a tray icon."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(tray)

def run_tray_loop(config_path: str, data_root: str, is_once: bool = False):
    """Internal implementation for running the tray icon loop."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    session_id = str(uuid.uuid4())[:8]
    config_loader = ConfigLoader(config_path)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    interval = 1 if is_once else config_loader.collection_seconds

    logging.info(f"Starting tray service (Session: {session_id}, Interval: {interval}s)...")

    stop_event = threading.Event()
    capture_count = 0

    def capture_loop():
        nonlocal capture_count
        from datetime import datetime, timezone, timedelta

        while not stop_event.is_set():
            # Mark as capturing
            write_state(data_root, make_state(
                session_id=session_id, status="Capturing...",
                capture_count=capture_count, interval_seconds=interval,
                label_counts=read_label_counts(data_root),
            ))

            success = perform_capture(config_loader, weather_fetcher, data_root, session_uuid=session_id)

            if success:
                capture_count += 1

            now = datetime.now(timezone.utc)
            next_at = (now + timedelta(seconds=interval)).isoformat() if not is_once else None

            write_state(data_root, make_state(
                session_id=session_id, status="Idle" if success else "Error",
                capture_count=capture_count, interval_seconds=interval,
                last_capture_at=now.isoformat(),
                next_capture_at=next_at,
                label_counts=read_label_counts(data_root),
            ))

            if is_once:
                logging.info("Single capture complete.")
                stop_event.set()
                rumps.quit_application()
                return

            for _ in range(interval):
                if stop_event.is_set():
                    break
                time.sleep(1)

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    tray_manager = MountainTray(data_root=data_root)
    tray_manager.run()

@cli.command()
@click.option('--config', default='mountain.toml', help='Path to config file.')
@click.option('--data-root', default='data', help='Root directory for data storage.')
def tray(config: str, data_root: str):
    """Runs continuous collection with a system tray icon."""
    run_tray_loop(config, data_root, is_once=False)

@cli.command()
@click.option('--config', default='mountain.toml', help='Path to config file.')
@click.option('--data-root', default='data', help='Root directory for data storage.')
def once(config: str, data_root: str):
    """Performs a single capture, showing a tray icon briefly."""
    run_tray_loop(config, data_root, is_once=True)

@cli.command()
@click.option('--config', default='mountain.toml', help='Path to config file.')
@click.option('--data-root', default='data', help='Root directory for data storage.')
def live(config: str, data_root: str):
    """Runs continuous collection in the foreground (no tray icon)."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    session_id = str(uuid.uuid4())[:8]
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    interval = config_loader.collection_seconds
    
    logging.info(f"Starting live collection loop (interval: {interval}s). Press Ctrl+C to stop.")
    try:
        while True:
            perform_capture(config_loader, weather_fetcher, data_root, session_uuid=session_id)
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Stopping live collection.")

if __name__ == "__main__":
    cli()
