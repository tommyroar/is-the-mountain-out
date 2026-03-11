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

app = typer.Typer()

STATE_FILE = "data/.mountain_data_root"

def get_folder_via_picker(title="Select Data Root"):
    """Opens a native folder picker and returns the selected path."""
    root = tk.Tk()
    root.withdraw()
    # Bring window to front
    root.attributes("-topmost", True)
    root.focus_force()
    print("Opening native folder picker...")
    selected_dir = filedialog.askdirectory(
        title=title,
        initialdir=str(Path.cwd() / "data")
    )
    root.destroy()
    return selected_dir

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    folder: Optional[str] = typer.Argument(None, help="Folder to classify"),
    port: int = 8890,
    f: Optional[str] = typer.Option(None, "-f", help="Folder to classify (alias)")
):
    """
    Main entry point for 'uv run classify'.
    Steps:
    1) Resolve data root (CMD param or File Picker).
    2) Launch notebook server.
    3) Verify accessibility.
    4) Open browser.
    5) Wait and cleanup.
    """
    if ctx.invoked_subcommand:
        return

    # 1. Resolve data root
    data_root = folder or f
    
    if data_root:
        data_root = str(Path(data_root).absolute())
        if not Path(data_root).exists():
            print(f"ERROR: Provided path does not exist: {data_root}")
            return
        print(f"1) Using provided data root: {data_root}")
    else:
        print("1) Launching file picker...")
        data_root = get_folder_via_picker("Select Data Root for Classification")
        if not data_root:
            print("No directory selected. Aborting.")
            return
        data_root = str(Path(data_root).absolute())
        print(f"Selected data root: {data_root}")
        
    # Write to state file for the notebook to pick up
    Path("data").mkdir(exist_ok=True)
    Path(STATE_FILE).write_text(data_root)

    # 2. Launch server
    print(f"2) Starting Jupyter Notebook server on port {port}...")
    
    # Clean up any orphaned servers on this port
    subprocess.run(["pkill", "-f", f"port={port}"], capture_output=True)
    
    cmd = [
        "uv", "run", "jupyter", "notebook",
        "--config=jupyter_notebook_config.py",
        f"--ServerApp.port={port}",
        "--ServerApp.ip=127.0.0.1"
    ]
    
    log_file = Path("data/jupyter_classify.log")
    with open(log_file, "w") as f_log:
        process = subprocess.Popen(
            cmd,
            stdout=f_log,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp
        )
    
    try:
        # 3. Confirm accessibility
        print("3) Verifying notebook server is responsive...")
        connected = False
        # Extended polling for slower starts
        for i in range(45): 
            if process.poll() is not None:
                print(f"\nERROR: Notebook server process died with code {process.returncode}")
                break
            
            try:
                # Use 127.0.0.1 directly to avoid localhost resolution delays/issues
                r = requests.get(f"http://127.0.0.1:{port}/tree", timeout=2)
                if r.status_code in [200, 405]:
                    connected = True
                    break
            except requests.exceptions.ConnectionError:
                if i % 5 == 0 and i > 0:
                    print(f"  [Attempt {i+1}/45] Still waiting for connection...")
            except Exception:
                pass
            time.sleep(1)
            
        if not connected:
            print("\nERROR: Notebook server failed to start or is not responding.")
            if log_file.exists():
                print("--- JUPYTER LOG OUTPUT (LAST 30 LINES) ---")
                lines = log_file.read_text().splitlines()
                for line in lines[-30:]:
                    print(line)
                print("--------------------------")
            os.killpg(process.pid, signal.SIGTERM)
            return

        # 4. Open browser
        url = f"http://127.0.0.1:{port}/notebooks/classify.ipynb"
        print(f"4) Opening browser to {url}...")
        subprocess.run(["open", url])

        print("\n--- Classifier is ACTIVE ---")
        print(f"Server PID: {process.pid}")
        print("Press Ctrl+C to stop the server and exit.")
        
        # 5. Wait for exit
        while True:
            time.sleep(1)
            if process.poll() is not None:
                print("Notebook server process ended unexpectedly.")
                break
                
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping classifier server (SIGINT)...")
    finally:
        # Cleanup
        try:
            os.killpg(process.pid, signal.SIGINT)
            for _ in range(5):
                if process.poll() is not None: break
                time.sleep(1)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        except:
            pass
        
        if Path(STATE_FILE).exists():
            Path(STATE_FILE).unlink()
        print("Done.")

@app.command()
def stop():
    """Fallback command to stop any orphaned servers."""
    subprocess.run(["pkill", "-f", "jupyter-notebook"], capture_output=True)
    print("Sent stop signal to any running notebook servers.")

def cli_wrapper():
    """Typer entry point that ensures ctx is provided."""
    app()

if __name__ == "__main__":
    app()
