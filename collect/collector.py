import time
import typer
import os
import subprocess
import json
import requests
import signal
from pathlib import Path
from datetime import datetime, UTC, timedelta
import cv2
from typing import Optional, Dict, List

from train.config_loader import ConfigLoader

app = typer.Typer()
notebook_app = typer.Typer()
app.add_typer(notebook_app, name="notebook", help="Manage the interactive capture browser.")

LOG_FILE = "data/collection.log"
NOTEBOOK_PID_FILE = "data/notebook.pid"
NTFY_KEY_FILE = "ntfy.key"

class WebcamStream:
    def __init__(self, url: str):
        self.url = url
        self.cap = cv2.VideoCapture(url)

    def capture_raw(self):
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None

    def capture_to_tensor(self, transform):
        frame = self.capture_raw()
        if frame is not None:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return transform(frame_rgb)
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
            if response.status_code == 200:
                # METAR is typically the second line of the NOAA response
                lines = response.text.strip().split('\n')
                if len(lines) >= 2:
                    return lines[1]
                return lines[0]
        except Exception as e:
            print(f"Error fetching METAR: {e}")
        return None

    def get_weather_vector(self) -> torch.Tensor:
        import torch
        from metar import Metar
        metar_text = self.fetch_latest_metar()
        vis, ceil = 0.0, 1.0 # Defaults (bad weather)
        if metar_text:
            try:
                obs = Metar.Metar(metar_text)
                if obs.vis:
                    # Normalize vis (0 to 10 miles -> 0.0 to 1.0)
                    vis = min(obs.vis.value('SM'), 10.0) / 10.0
                if obs.sky:
                    # Normalize ceiling (0 to 10000ft -> 0.0 to 1.0)
                    # Use the lowest broken or overcast layer
                    layers = [l for l in obs.sky if l[0] in ['BKN', 'OVC']]
                    if layers:
                        ceil = min(layers[0][1].value('FT'), 10000.0) / 10000.0
                    else:
                        ceil = 1.0 # Clear
            except:
                pass
        return torch.tensor([vis, ceil], dtype=torch.float32)

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

def perform_capture(config_loader: ConfigLoader, weather_fetcher: WeatherFetcher, data_root: str = "data", step_info: Optional[Dict] = None):
    """Core logic to capture a single image and METAR data with UTC-based naming."""
    now_utc = datetime.now(UTC)
    date_str = now_utc.strftime("%Y%m%d")
    time_str = now_utc.strftime("%H%M%S_%f_UTC")
    
    capture_dir = Path(data_root) / date_str / time_str
    image_dir = capture_dir / "images"
    metar_dir = capture_dir / "metar"
    
    image_dir.mkdir(parents=True, exist_ok=True)
    metar_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[{now_utc}] Starting collection into {capture_dir}...")
    
    # Fetch and save METAR
    metar_text = weather_fetcher.fetch_latest_metar()
    metar_success = False
    metar_path = metar_dir / "metar.txt"
    if metar_text:
        with open(metar_path, "w") as f:
            f.write(metar_text)
        print("  METAR data saved.")
        metar_success = True
        log_event("METAR", "SUCCESS", {
            "station_id": weather_fetcher.station_id,
            "metar_path": str(metar_path),
            **(step_info or {})
        })
    else:
        print("  Warning: METAR capture failed.")
        log_event("METAR", "FAILURE", {
            "station_id": weather_fetcher.station_id,
            **(step_info or {})
        })
    
    # Capture and save image
    source = config_loader.webcam_url
    if not source:
        print("Error: No webcam source configured.")
        log_event("CAPTURE", "ERROR", {"reason": "No webcam source", **(step_info or {})})
        return False
        
    stream = WebcamStream(source)
    try:
        frame = stream.capture_raw()
        if frame is not None:
            safe_name = str(source).replace("/", "_").replace(":", "_").replace(".", "_")
            filename = f"{time_str}_{safe_name}.jpg"
            image_path = image_dir / filename
            cv2.imwrite(str(image_path), frame)
            print(f"  Source {source}: Saved as {filename}")
            
            log_event("CAPTURE", "SUCCESS", {
                "input_url": source,
                "image_path": str(image_path),
                "metar_path": str(metar_path) if metar_success else None,
                "metar_success": metar_success,
                **(step_info or {})
            })
            return True
        else:
            print(f"  Source {source}: Capture failed.")
            log_event("CAPTURE", "FAILURE", {
                "input_url": source,
                "reason": "Webcam capture failed", 
                **(step_info or {})
            })
            return False
    finally:
        stream.release()

def parse_interval(interval_str: str) -> int:
    """Parses strings like '10m', '1h', '600s' into seconds."""
    if interval_str.endswith('s'):
        return int(interval_str[:-1])
    elif interval_str.endswith('m'):
        return int(interval_str[:-1]) * 60
    elif interval_str.endswith('h'):
        return int(interval_str[:-1]) * 3600
    return int(interval_str)

@app.command()
def collect(config: str = "mountain.toml", data_root: str = "data"):
    """
    Performs a single capture of all configured webcams and METAR data.
    """
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    perform_capture(config_loader, weather_fetcher, data_root)

@app.command()
def plan(
    steps: List[str], 
    config: str = "mountain.toml", 
    data_root: str = "data",
    start_index: int = 0
):
    """
    Executes a sequence of capture steps with defined waits.
    Example: uv run collect plan 600s 600s stop
    """
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    
    total = len(steps)
    print(f"Starting plan execution ({total} steps)...")
    
    for i in range(start_index, total):
        step = steps[i]
        if step.lower() == "stop":
            print("Plan complete.")
            break
            
        # 1. Perform Capture
        step_info = {"step_index": i + 1, "total_steps": total, "type": "PLAN_STEP"}
        perform_capture(config_loader, weather_fetcher, data_root, step_info=step_info)
        
        # 2. Wait
        wait_time = parse_interval(step)
        print(f"  Waiting {wait_time}s until next capture...")
        log_event("PROGRESS", "STATUS", {"progress": i + 1, "total": total, "percentage": round(((i+1)/total)*100, 1)})
        time.sleep(wait_time)

def send_notification(message: str, title: str = "Mountain Collector"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic and Path(NTFY_KEY_FILE).exists():
        with open(NTFY_KEY_FILE, "r") as f:
            topic = f.read().strip()
            
    if topic:
        try:
            requests.post(
                f"https://ntfy.sh/{topic}",
                data=message,
                headers={"Title": title},
                timeout=5
            )
        except: pass

@app.command()
def tail(log_path: str = LOG_FILE, follow: bool = True):
    """
    Pretty-prints the collection log.
    """
    log_path = Path(log_path)
    if not log_path.exists():
        print(f"Log file {log_path} not found.")
        return

    def print_logs(lines):
        for line in lines:
            try:
                j = json.loads(line.strip())
                ts = j.get("timestamp", "").split(".")[0].replace("T", " ")
                event = j.get("event", "UNKNOWN")
                status = j.get("status", "")
                meta = j.get("metadata", {})
                step = f"Step {meta.get('step_index')}/{meta.get('total_steps')}" if "step_index" in meta else ""
                
                path = meta.get('image_path') or meta.get('metar_path') or ""
                extra = f"[{meta.get('station_id')}]" if "station_id" in meta else ""
                
                msg = f"[{ts}] {event:<8} | {status:<8} | {step:<12} | {extra:<8} {path}"
                print(msg)
            except:
                print(line.strip())

    # Initial tail
    with open(log_path, "r") as f:
        lines = f.readlines()
        print_logs(lines[-10:])

    if follow:
        print("\n--- Following log (Ctrl+C to stop) ---")
        try:
            with open(log_path, "r") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(1)
                        continue
                    print_logs([line])
        except KeyboardInterrupt:
            print("\nStopped tailing.")

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

def get_folder_via_picker(title="Select Data Root"):
    """Opens a native folder picker and returns the selected path."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    # Bring window to front
    root.attributes("-topmost", True)
    print("Opening native folder picker...")
    selected_dir = filedialog.askdirectory(
        title=title,
        initialdir=str(Path.cwd() / "data")
    )
    root.destroy()
    return selected_dir

@notebook_app.command("start")
def notebook_start(port: int = 8890, data_root: str = None):
    """Starts the Jupyter Notebook server for the capture browser."""
    pid_path = Path(NOTEBOOK_PID_FILE)
    if pid_path.exists():
        print(f"Notebook server may already be running (PID file exists at {pid_path}).")
        return

    # Use picker if no root provided
    if not data_root:
        data_root = get_folder_via_picker("Select Data Root for Capture Browser")
        if not data_root:
            print("No directory selected. Exiting.")
            return

    print(f"Starting Jupyter Notebook server on port {port} for: {data_root}...")
    
    # Set environment for the notebook to pick up
    env = os.environ.copy()
    env["MOUNTAIN_DATA_ROOT"] = data_root

    # Use 'uv run' to ensure correct environment
    cmd = [
        "uv", "run", "jupyter", "notebook",
        "--no-browser",
        f"--port={port}",
        "--ServerApp.token=",
        "--ServerApp.password=",
        "--ServerApp.ip=127.0.0.1"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp,
        env=env
    )
    
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(process.pid))
    
    print(f"Notebook server started with PID {process.pid}.")
    print(f"Browser URL: http://127.0.0.1:{port}/notebooks/captures.ipynb")

@notebook_app.command("stop")
def notebook_stop():
    """Stops the Jupyter Notebook server."""
    pid_path = Path(NOTEBOOK_PID_FILE)
    if not pid_path.exists():
        print("No notebook PID file found. Is the server running?")
        return
    
    try:
        pid = int(pid_path.read_text().strip())
        print(f"Stopping notebook server (PID {pid})...")
        os.killpg(pid, signal.SIGTERM)
        pid_path.unlink()
        print("Server stopped.")
    except ProcessLookupError:
        print("Process not found. Cleaning up stale PID file.")
        pid_path.unlink()
    except Exception as e:
        print(f"Error stopping server: {e}")

def generate_calendar_plist(schedule: Dict[str, int]) -> str:
    """Generates the StartCalendarInterval portion of a plist."""
    lines = ["    <key>StartCalendarInterval</key>", "    <dict>"]
    for key, val in schedule.items():
        lines.append(f"        <key>{key}</key>")
        lines.append(f"        <integer>{val}</integer>")
    lines.append("    </dict>")
    return "\n".join(lines)

@app.command()
def schedule(config: str = "mountain.toml", plan_steps: Optional[List[str]] = None):
    """Installs the launchctl service. If plan_steps is provided, schedules the 'plan' command."""
    config_loader = ConfigLoader(config)
    current_dir = Path.cwd().absolute()
    executable = subprocess.check_output(["which", "uv"], text=True).strip()
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.mountain.collector.plist"
    
    args = [executable, "run", "collect"]
    if plan_steps:
        args += ["plan"] + list(plan_steps) + ["--config", str(current_dir / config)]
        timing_config = "    <key>StartInterval</key>\n    <integer>60</integer>" # Check plan every minute
    else:
        args += ["collect", "--config", str(current_dir / config)]
        if config_loader.collection_schedule:
            timing_config = generate_calendar_plist(config_loader.collection_schedule)
        else:
            timing_config = f"    <key>StartInterval</key>\n    <integer>{config_loader.collection_seconds}</integer>"

    args_xml = "\n".join([f"        <string>{a}</string>" for a in args])

    # Stash secret in EnvironmentVariables to avoid repeated file reads
    env_vars = ""
    if Path(NTFY_KEY_FILE).exists():
        with open(NTFY_KEY_FILE, "r") as f:
            topic = f.read().strip()
            env_vars = f"""    <key>EnvironmentVariables</key>
    <dict>
        <key>NTFY_TOPIC</key>
        <string>{topic}</string>
    </dict>"""

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mountain.collector</string>
{env_vars}
    <key>ProgramArguments</key>
    <array>
{args_xml}
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
    
    send_notification(
        f"Background collection service has been scheduled and is now active.",
        title="🏔️ Collection Scheduled"
    )
    
    if plan_steps:
        print(f"Plan mode enabled with {len(plan_steps)} steps.")
    elif config_loader.collection_schedule:
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
