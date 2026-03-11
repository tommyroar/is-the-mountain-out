import os
import shutil
import argparse
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

def prune_dataset(data_root="data", min_seconds=300, dark_thresh=10.0, diff_thresh=2.0, dry_run=True, force_keep_hourly=True):
    root = Path(data_root)
    # Collect all images and sort by modification time to process chronologically
    images = []
    for img_path in root.rglob("*.jpg"):
        images.append((img_path.stat().st_mtime, img_path))
    
    images.sort(key=lambda x: x[0])
    
    print(f"🔍 Found {len(images)} total images in '{data_root}'")
    
    to_delete_dirs = []
    reasons = {"time": 0, "dark": 0, "duplicate": 0}
    
    last_kept_time = 0
    last_kept_img = None
    last_forced_hour = -1

    for mtime, img_path in images:
        capture_dir = img_path.parent.parent
        
        # Determine the current hour for force-keep logic
        from datetime import datetime, UTC
        dt = datetime.fromtimestamp(mtime, UTC)
        current_hour = dt.hour
        current_day = dt.day
        
        # 1. Force Keep Logic (1 per hour)
        # We use (day, hour) to ensure we get 1 per hour every day
        hour_key = (current_day, current_hour)
        if force_keep_hourly and hour_key != last_forced_hour:
            last_forced_hour = hour_key
            last_kept_time = mtime
            try:
                with Image.open(img_path) as img:
                    last_kept_img = img.convert("L").copy()
                continue # Skip all other pruning for this forced-keep image
            except:
                pass # If file is corrupt, let normal logic handle it

        # 2. Temporal Pruning
        if mtime - last_kept_time < min_seconds:
            to_delete_dirs.append(capture_dir)
            reasons["time"] += 1
            continue
            
        try:
            with Image.open(img_path) as img:
                img_gray = img.convert("L")
                stat = ImageStat.Stat(img_gray)
                avg_brightness = stat.mean[0]
                
                # 3. Darkness Pruning
                if avg_brightness < dark_thresh:
                    to_delete_dirs.append(capture_dir)
                    reasons["dark"] += 1
                    continue
                    
                # 4. Redundancy / Diff Pruning
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

    total_kept = len(images) - len(to_delete_dirs)
    
    print("\n📊 --- Pruning Results ---")
    print(f"Thresholds: Interval={min_seconds}s, Dark={dark_thresh}, Diff={diff_thresh}")
    if force_keep_hourly:
        print("Special: Guaranteed 1 image kept per hour (ignoring darkness).")
    
    print(f"Removed (Time Constraints):     {reasons['time']}")
    print(f"Removed (Too Dark):             {reasons['dark']}")
    print(f"Removed (No Scene Change):      {reasons['duplicate']}")
    print(f"Total to delete:           {len(to_delete_dirs)}")
    print(f"✅ Images Remaining:        {total_kept} ({(total_kept/len(images))*100:.1f}%)")

    if dry_run:
        print("\n🛑 This was a DRY RUN. No directories were deleted.")
        print("To execute the deletion, run: uv run python tools/prune_data.py --execute")
    else:
        print("\n🗑️ Executing deletions...")
        deleted_count = 0
        for d in set(to_delete_dirs):
            if d.exists() and d.name != "data":
                try:
                    shutil.rmtree(d)
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {d}: {e}")
        print(f"Done. Deleted {deleted_count} capture directories.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune redundant or unusable webcam captures.")
    parser.add_argument("--execute", action="store_true", help="Actually delete files (default is dry-run)")
    parser.add_argument("--min-sec", type=int, default=300, help="Minimum seconds between frames (default: 300)")
    parser.add_argument("--dark", type=float, default=10.0, help="Brightness threshold (0-255, default: 10.0)")
    parser.add_argument("--diff", type=float, default=2.0, help="Pixel difference threshold (0-255, default: 2.0)")
    parser.add_argument("--no-force-hour", action="store_false", dest="force_hour", help="Don't guarantee hourly samples")
    parser.set_defaults(force_hour=True)
    args = parser.parse_args()
    
    prune_dataset(
        dry_run=not args.execute, 
        min_seconds=args.min_sec, 
        dark_thresh=args.dark, 
        diff_thresh=args.diff,
        force_keep_hourly=args.force_hour
    )
