import os
import requests
import argparse
import json
from pathlib import Path
from typing import List

def sync_from_cloud(worker_url: str, data_root: str, limit: int = 50):
    """Sync recent captures from Cloudflare Worker/R2 to local data directory."""
    print(f"📡 Syncing from {worker_url} to {data_root}...")
    
    # 1. Get list of files from worker
    try:
        response = requests.get(f"{worker_url}/list?limit={limit}")
        response.raise_for_status()
        files = response.json()
    except Exception as e:
        print(f"❌ Error fetching file list: {e}")
        return

    # 2. Download each file
    for file_key in files:
        # Expected key: captures/YYYYMMDD/HHMMSS_f_UTC/images/capture.jpg
        # Local path: data/YYYYMMDD/HHMMSS_f_UTC/images/capture.jpg
        local_path = Path(data_root) / file_key.replace("captures/", "")
        
        if local_path.exists():
            print(f"⏩ Skipping {file_key} (already exists)")
            continue
            
        print(f"⬇️ Downloading {file_key}...")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # We assume images are publicly accessible if configured,
            # or we could fetch them via a worker proxy.
            # For this example, let's assume the worker provides a proxy or the bucket is public.
            # Assuming worker proxy for security: {worker_url}/get?key={file_key}
            # BUT we haven't implemented /get in the worker yet.
            # Let's assume the worker_url is the base and the file_key is appended.
            # (In a real setup, R2 would have a public URL or we'd use S3 signed URLs)
            
            # Simple approach for the proposal:
            file_url = f"{worker_url}/get?key={file_key}"
            # Actually, let's just use the fetch logic.
            # (Need to add /get to the worker as well if not public)
            
            r = requests.get(file_url, stream=True)
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"❌ Error downloading {file_key}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Cloudflare Worker URL")
    parser.add_argument("--data-root", default="data", help="Local data root")
    parser.add_argument("--limit", type=int, default=50, help="Max files to sync")
    args = parser.parse_args()
    
    if not args.url:
        print("❌ Please provide --url (Cloudflare Worker URL)")
    else:
        sync_from_cloud(args.url, args.data_root, args.limit)
