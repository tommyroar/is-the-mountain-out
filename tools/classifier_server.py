import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, UTC

app = FastAPI(title="Mountain Classifier API")

# Allow local dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_ROOT = Path(os.environ.get("MOUNTAIN_DATA_ROOT", "data"))
LABELS_PATH = Path(os.environ.get("MOUNTAIN_LABELS_FILE", DATA_ROOT / "labels.yaml"))

class LabelBatch(BaseModel):
    labels: Dict[str, int] # path -> label

def load_labels():
    if LABELS_PATH.exists():
        with open(LABELS_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_labels(labels):
    with open(LABELS_PATH, "w") as f:
        yaml.safe_dump(labels, f)

@app.get("/api/jobs")
def get_jobs():
    """Proxy Nomad jobs for the UI."""
    try:
        nomad_url = os.environ.get("NOMAD_ADDR", "http://127.0.0.1:4646")
        response = requests.get(f"{nomad_url}/v1/jobs", timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Fallback if Nomad is unreachable
        return []

@app.get("/api/images")
def get_images(batch_size: int = 20, offset: int = 0):
    labels = load_labels()
    all_images = sorted([str(p.relative_to(DATA_ROOT)) for p in DATA_ROOT.rglob("*.jpg")])
    
    unlabeled = [img for img in all_images if img not in labels]
    
    return {
        "images": unlabeled[:batch_size],
        "total_unlabeled": len(unlabeled),
        "total_images": len(all_images)
    }

@app.get("/api/stats")
def get_stats():
    labels = load_labels()
    counts = {0: 0, 1: 0, 2: 0}
    for l in labels.values():
        counts[l] = counts.get(l, 0) + 1
        
    return {
        "labeled": len(labels),
        "counts": counts,
        "labels_path": str(LABELS_PATH.absolute())
    }

@app.post("/api/label")
def post_labels(batch: LabelBatch):
    labels = load_labels()
    labels.update(batch.labels)
    save_labels(labels)
    return {"status": "success", "new_count": len(labels)}

# Serve the actual data directory for image access
# Access via /data/YYYYMMDD/...
app.mount("/data", StaticFiles(directory=DATA_ROOT), name="data")

if __name__ == "__main__":
    import uvicorn
    import socket

    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    port = int(os.environ.get("MOUNTAIN_API_PORT", 8000))
    if is_port_in_use(port):
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
    
    # Write the actual port being used to a file so the UI or other tools can find it
    port_file = DATA_ROOT / "classifier_server.port"
    port_file.write_text(str(port))
    
    print(f"📡 API Server starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
