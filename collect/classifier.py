import typer
from pathlib import Path
import os
import subprocess
import signal
import time
import requests
import tkinter as tk
from tkinter import filedialog
from typing import Optional
import sys

app = typer.Typer()
notebook_app = typer.Typer()
app.add_typer(notebook_app, name="notebook", help="Manage the interactive classifier notebook.")

CLASSIFY_PID_FILE = "data/classify_notebook.pid"

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
    """Starts the Jupyter Notebook server for the mountain classifier."""
    pid_path = Path(CLASSIFY_PID_FILE)
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            print(f"Classifier notebook server already running at PID {pid}.")
            print(f"URL: http://127.0.0.1:{port}/notebooks/classify.ipynb")
            return
        except:
            pid_path.unlink()

    # Use picker if no root provided
    if not data_root:
        data_root = get_folder_via_picker("Select Data Root for Classifier")
        if not data_root: return

    data_root = str(Path(data_root).absolute())
    print(f"Starting classifier for: {data_root}")
    
    # Set environment for the notebook to pick up
    env = os.environ.copy()
    env["MOUNTAIN_DATA_ROOT"] = data_root

    # The most direct, verified launch command
    # Uses the current venv python directly to avoid uv-wrapper complexity
    python_exe = sys.executable
    cmd = [
        python_exe, "-m", "notebook",
        "--no-browser",
        f"--port={port}",
        "--ServerApp.token=",
        "--ServerApp.password=",
        "--ServerApp.ip=0.0.0.0"
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
    
    # VERIFICATION
    url = f"http://127.0.0.1:{port}/notebooks/classify.ipynb"
    
    # Try to read state for display
    state_msg = ""
    state_file = Path(data_root) / "classifier_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                last_idx = json.load(f).get('last_index', 0)
                state_msg = f" (Resuming from image index {last_idx})"
        except: pass

    print(f"\n🔗 Access URL: {url}{state_msg}")
    print("Verifying connection...")
    
    connected = False
    for i in range(15):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/tree", timeout=1)
            if r.status_code in [200, 405]:
                connected = True
                break
        except: pass
        time.sleep(1)

    if connected:
        print("✅ Server is responding.")
        subprocess.run(["open", url])
    else:
        print("⚠️ Warning: Server is starting slowly. Please refresh the browser manually.")

@notebook_app.command("stop")
def notebook_stop():
    """Stops the classifier notebook server."""
    pid_path = Path(CLASSIFY_PID_FILE)
    
    print("Stopping classifier notebook server...")
    
    # 1. Try stopping via PID file if it exists
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.killpg(pid, signal.SIGTERM)
            print(f"  Sent TERM to process group {pid}")
        except:
            pass
        pid_path.unlink()

    # 2. Nuclear fallback: kill anything on port 8890 or 8891
    # This ensures no zombies are left behind
    subprocess.run(["pkill", "-f", "jupyter-notebook"], capture_output=True)
    subprocess.run(["pkill", "-f", "port=8890"], capture_output=True)
    subprocess.run(["pkill", "-f", "port=8891"], capture_output=True)
    
    print("✅ Cleanup complete.")

def cli_wrapper():
    app()

if __name__ == "__main__":
    app()
