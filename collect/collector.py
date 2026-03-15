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
from collect.state import make_state, write_state, read_label_counts, write_plan, read_plan, PLAN_FILENAME

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

def perform_capture(config_loader: ConfigLoader, weather_fetcher: WeatherFetcher, data_root: str, session_uuid: Optional[str] = None, step_info: Optional[Dict] = None) -> Optional[Path]:
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
            return image_path
        else:
            logging.warning(f"Source {source}: Capture failed.")
            return None
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
    from datetime import datetime, timezone, timedelta

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    session_id = str(uuid.uuid4())[:8]
    config_loader = ConfigLoader(config_path)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    fallback_interval = config_loader.collection_seconds

    # Load plan if one exists
    plan_timestamps = read_plan(data_root)
    if plan_timestamps:
        now_utc = datetime.now(timezone.utc)
        # Skip past timestamps that are already in the past
        plan_timestamps = [t for t in plan_timestamps
                           if datetime.fromisoformat(t) > now_utc]
        logging.info(f"Loaded plan: {len(plan_timestamps)} captures remaining.")
    else:
        logging.info(f"No plan file found. Using fixed interval ({fallback_interval}s).")

    plan_total = len(plan_timestamps) if plan_timestamps else 0
    plan_index = 0
    stop_event = threading.Event()
    capture_count = 0
    session_labels_file = Path(data_root) / f"labels.{session_id}.yaml"

    def _append_session_label(image_path: Path) -> None:
        rel = str(image_path.relative_to(Path(data_root)))
        with open(session_labels_file, "a") as f:
            yaml.dump({rel: None}, f, default_flow_style=False)

    def _next_capture_at() -> Optional[str]:
        if plan_timestamps and plan_index < len(plan_timestamps):
            return plan_timestamps[plan_index]
        return None

    def _sleep_until_next() -> None:
        """Sleep until the next scheduled capture time, or fallback interval."""
        next_iso = _next_capture_at()
        if next_iso:
            target = datetime.fromisoformat(next_iso)
            wait = max(0, (target - datetime.now(timezone.utc)).total_seconds())
        else:
            wait = fallback_interval
        logging.info(f"Next capture in {int(wait)}s.")
        end = time.monotonic() + wait
        while time.monotonic() < end:
            if stop_event.is_set():
                return
            time.sleep(min(1, end - time.monotonic()))

    def capture_loop():
        nonlocal capture_count, plan_index

        while not stop_event.is_set():
            write_state(data_root, make_state(
                session_id=session_id, status="Capturing...",
                capture_count=capture_count,
                plan_total=plan_total,
                interval_seconds=fallback_interval,
                next_capture_at=_next_capture_at(),
                session_labels_file=str(session_labels_file),
            ))

            image_path = perform_capture(config_loader, weather_fetcher, data_root, session_uuid=session_id)

            if image_path:
                capture_count += 1
                _append_session_label(image_path)

            if plan_timestamps:
                plan_index += 1

            now = datetime.now(timezone.utc)
            write_state(data_root, make_state(
                session_id=session_id,
                status="Idle" if image_path else "Error",
                capture_count=capture_count,
                plan_total=plan_total,
                interval_seconds=fallback_interval,
                last_capture_at=now.isoformat(),
                next_capture_at=_next_capture_at(),
                session_labels_file=str(session_labels_file),
            ))

            if is_once:
                logging.info("Single capture complete.")
                stop_event.set()
                rumps.quit_application()
                return

            if plan_timestamps and plan_index >= len(plan_timestamps):
                logging.info("Plan complete.")
                stop_event.set()
                rumps.quit_application()
                return

            _sleep_until_next()

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    tray_manager = MountainTray(data_root=data_root)
    tray_manager.run()

@cli.command()
@click.option('--data-root', default='data', help='Root directory for data storage.')
@click.option('--days', default=30, help='Number of days to plan ahead.')
@click.option('--lat', default=47.6533, help='Latitude of camera location.')
@click.option('--lon', default=-122.3091, help='Longitude of camera location.')
def schedule(data_root: str, days: int, lat: float, lon: float):
    """Generate a solar-aligned capture plan and save it to capture_plan.json."""
    import sys as _sys
    from datetime import datetime, timezone, timedelta as _timedelta
    _sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.plan import CapturePlan

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    planner = CapturePlan(lat, lon)
    intervals = planner.generate(now, days=days)

    # Convert wait-time intervals to absolute UTC timestamps
    timestamps = []
    current = now
    for step in intervals:
        if step == "stop":
            break
        wait = int(step[:-1])
        current = current + _timedelta(seconds=wait)
        timestamps.append(current.isoformat())

    path = write_plan(data_root, timestamps)
    click.echo(f"Plan saved: {path}")
    click.echo(f"  {len(timestamps)} captures over {days} days")
    click.echo(f"  First: {timestamps[0]}")
    click.echo(f"  Last:  {timestamps[-1]}")


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
