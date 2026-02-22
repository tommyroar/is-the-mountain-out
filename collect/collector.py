import time
import typer
import os
import subprocess
import json
from pathlib import Path
from datetime import datetime, UTC, timedelta
import cv2
from typing import Optional, Dict, List

from train.config_loader import ConfigLoader
from train.utils import WebcamStream, WeatherFetcher

app = typer.Typer()

PLAN_STATE_FILE = "data/plan_state.json"
COLLECTION_LOG = "data/collection.log"

def log_event(event_type: str, status: str, metadata: Optional[Dict] = None):
    """Writes a structured JSON log entry."""
    log_path = Path(COLLECTION_LOG)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event_type,
        "status": status,
        "metadata": metadata or {}
    }
    
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

def perform_capture(config_loader: ConfigLoader, weather_fetcher: WeatherFetcher, data_root: str = "data", step_info: Optional[Dict] = None):
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
    metar_success = False
    if metar_text:
        with open(metar_dir / "metar.txt", "w") as f:
            f.write(metar_text)
        print("  METAR data saved.")
        metar_success = True
    else:
        print("  Warning: METAR capture failed.")
    
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
            
            metar_path = metar_dir / "metar.txt"
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
    Runs a single capture of the configured webcam and METAR data.
    """
    _collect_internal(config, data_root)
    print(f"[{datetime.now(UTC)}] Collection complete.")

def _collect_internal(config: str = "mountain.toml", data_root: str = "data", step_info: Optional[Dict] = None):
    """Internal helper for collection logic."""
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    perform_capture(config_loader, weather_fetcher, data_root, step_info=step_info)

@app.command()
def plan(
    steps: List[str], 
    config: str = "mountain.toml", 
    data_root: str = "data"
):
    """
    Processes a sequence of intervals. Saves state to remain durable across runs.
    Accepts intervals (e.g., '10m', '1h') and a terminal 'stop' command.
    """
    state_path = Path(PLAN_STATE_FILE)
    state = {"step_index": 0, "next_run": 0, "last_process_start": 0}
    
    if state_path.exists():
        with open(state_path, "r") as f:
            state = json.load(f)
    else:
        log_event("PLAN", "START", {"total_steps": len(steps)})
            
    current_index = state["step_index"]
    if current_index >= len(steps):
        print("Plan already completed.")
        return

    now = time.time()
    
    # If the process just started and the next run is far away (>10m), 
    # run a HEARTBEAT capture to validate the service is alive.
    if state.get("last_process_start", 0) < (now - 60): # Basic check for new process run
        state["last_process_start"] = now
        if now < state["next_run"] and (state["next_run"] - now) > 600:
            print("Performing startup heartbeat capture...")
            _collect_internal(config=config, data_root=data_root, step_info={"type": "HEARTBEAT"})

    if now < state["next_run"]:
        print(f"Waiting... Next run in {int(state['next_run'] - now)}s")
        # Save process start time even if we wait
        with open(state_path, "w") as f: json.dump(state, f)
        return

    step = steps[current_index]
    if step.lower() == "stop":
        print("Plan 'stop' reached. Cleaning up...")
        log_event("PLAN", "STOP", {"completed_steps": current_index})
        
        # Self-unschedule
        unschedule()
        if state_path.exists(): state_path.unlink()
        return

    # Perform capture with logging info
    step_info = {"step_index": current_index + 1, "total_steps": len(steps), "type": "PLAN_STEP"}
    config_loader = ConfigLoader(config)
    weather_fetcher = WeatherFetcher(config_loader.metar_station)
    success = perform_capture(config_loader, weather_fetcher, data_root, step_info=step_info)
    
    # Calculate next step
    interval = parse_interval(step)
    state["step_index"] += 1
    state["next_run"] = now + interval
    
    # Create data dir if not exists
    Path(data_root).mkdir(parents=True, exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f)
    
    print(f"Step {current_index + 1}/{len(steps)} complete. Next run at {datetime.fromtimestamp(state['next_run'], UTC)}")

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
def schedule(config: str = "mountain.toml", plan_steps: Optional[List[str]] = None):
    """Installs the launchctl service. If plan_steps is provided, schedules the 'plan' command."""
    
    # Immediate validation run
    print("Performing immediate validation capture...")
    try:
        _collect_internal(config=config, step_info={"type": "INITIAL_VALIDATION"})
    except Exception as e:
        print(f"Validation failed: {e}. Aborting schedule.")
        raise typer.Exit(code=1)

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

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mountain.collector</string>
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
