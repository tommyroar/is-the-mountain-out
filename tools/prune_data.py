import os
import shutil
import argparse
import yaml
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from metar import Metar
from datetime import datetime, UTC

def load_labels(data_root):
    labels_path = Path(data_root) / "labels.yaml"
    if labels_path.exists():
        with open(labels_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_labels(data_root, labels):
    labels_path = Path(data_root) / "labels.yaml"
    with open(labels_path, 'w') as f:
        yaml.safe_dump(labels, f)

def get_metar_data(img_path):
    # Try multiple paths for metar.txt
    search_paths = [
        img_path.parent.parent / "metar" / "metar.txt",
        img_path.parent / "metar.txt",
        img_path.parent / f"{img_path.stem}.txt"
    ]
    for p in search_paths:
        if p.exists():
            with open(p, 'r') as f:
                return f.read().strip()
    return None

def prune_dataset(data_root="data", min_seconds=300, dark_thresh=10.0, diff_thresh=2.0, dry_run=True, force_keep_hourly=True, auto_label_metar=True):
    root = Path(data_root)
    labels = load_labels(root)
    
    images = []
    for img_path in root.rglob("*.jpg"):
        # Skip if already labeled
        rel_path = str(img_path.relative_to(root))
        if rel_path in labels:
            continue
        images.append((img_path.stat().st_mtime, img_path))
    
    images.sort(key=lambda x: x[0])
    print(f"🔍 Found {len(images)} unlabeled images in '{data_root}'")
    
    to_delete_dirs = []
    reasons = {"time": 0, "dark": 0, "duplicate": 0, "metar_auto": 0}
    
    last_kept_time = 0
    last_kept_img = None
    last_forced_hour = -1

    for mtime, img_path in images:
        capture_dir = img_path.parent.parent
        rel_path = str(img_path.relative_to(root))
        
        # 1. METAR Auto-Labeling (Obvious "Not Out")
        if auto_label_metar:
            metar_text = get_metar_data(img_path)
            if metar_text:
                try:
                    obs = Metar.Metar(metar_text)
                    vis = obs.vis.value('SM') if obs.vis else 10.0
                    # Check for low ceiling (BKN or OVC layers)
                    ceil = 10000.0
                    if obs.sky:
                        layers = [l for l in obs.sky if l[0] in ['BKN', 'OVC']]
                        if layers: ceil = layers[0][1].value('FT')
                    
                    # Logic: If vis is crap OR ceiling is below Rainier's peak area (~8000ft)
                    if vis < 3.0 or ceil < 6000:
                        if not dry_run:
                            labels[rel_path] = 0
                        reasons["metar_auto"] += 1
                        # We don't delete these! We just auto-label them so the human skips them.
                        continue
                except: pass

        # 2. Force Keep Logic (1 per hour for darkness baseline)
        dt = datetime.fromtimestamp(mtime, UTC)
        hour_key = (dt.day, dt.hour)
        if force_keep_hourly and hour_key != last_forced_hour:
            last_forced_hour = hour_key
            last_kept_time = mtime
            try:
                with Image.open(img_path) as img:
                    last_kept_img = img.convert("L").copy()
                continue 
            except: pass

        # 3. Temporal Pruning
        if mtime - last_kept_time < min_seconds:
            to_delete_dirs.append(capture_dir)
            reasons["time"] += 1
            continue
            
        try:
            with Image.open(img_path) as img:
                img_gray = img.convert("L")
                stat = ImageStat.Stat(img_gray)
                avg_brightness = stat.mean[0]
                
                # 4. Darkness Pruning
                if avg_brightness < dark_thresh:
                    to_delete_dirs.append(capture_dir)
                    reasons["dark"] += 1
                    continue
                    
                # 5. Redundancy / Diff Pruning
                if last_kept_img is not None:
                    diff = ImageChops.difference(img_gray, last_kept_img)
                    diff_stat = ImageStat.Stat(diff)
                    avg_diff = diff_stat.mean[0]
                    
                    if avg_diff < diff_thresh:
                        to_delete_dirs.append(capture_dir)
                        reasons["duplicate"] += 1
                        continue
                
                # Keep this image, update baselines
                last_kept_time = mtime
                last_kept_img = img_gray.copy()
                
        except Exception as e:
            print(f"Error processing {img_path}: {e}")

    if not dry_run:
        save_labels(root, labels)

    total_deleted = len(to_delete_dirs)
    
    print("\n📊 --- Pruning & Auto-Labeling Results ---")
    print(f"Auto-Labeled (METAR Low Vis/Ceiling): {reasons['metar_auto']}")
    print(f"Pruned (Time Constraints):           {reasons['time']}")
    print(f"Pruned (Too Dark):                   {reasons['dark']}")
    print(f"Pruned (No Scene Change):            {reasons['duplicate']}")
    print(f"Total Folders to Delete:             {total_deleted}")

    if dry_run:
        print("\n🛑 DRY RUN: No files deleted, no labels saved.")
    else:
        print("\n🗑️ Executing deletions and saving auto-labels...")
        deleted_count = 0
        for d in set(to_delete_dirs):
            if d.exists() and d.name != "data":
                try:
                    shutil.rmtree(d)
                    deleted_count += 1
                except: pass
        print(f"Done. Deleted {deleted_count} directories.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--min-sec", type=int, default=300)
    parser.add_argument("--dark", type=float, default=10.0)
    parser.add_argument("--diff", type=float, default=2.0)
    args = parser.parse_args()
    
    prune_dataset(dry_run=not args.execute, min_seconds=args.min_sec, dark_thresh=args.dark, diff_thresh=args.diff)
