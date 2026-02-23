import sys
import random
from datetime import datetime, timedelta, date, UTC
from typing import List, Tuple
try:
    from astral import LocationInfo
    from astral.sun import sun
except ImportError:
    print("Error: 'astral' library not found. Run with 'uv run --with astral tools/solar_plan.py'")
    sys.exit(1)

def get_solar_events(lat: float, lon: float, start_date: date, days: int) -> List[dict]:
    location = LocationInfo("Custom", "USA", "UTC", lat, lon)
    events = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        s = sun(location.observer, date=day)
        events.append({
            "date": day,
            "sunrise": s["sunrise"],
            "sunset": s["sunset"]
        })
    return events

def generate_collection_plan(lat: float, lon: float, current_time: datetime, start_time: Optional[datetime] = None, target_count: int = 100, jitter_range: int = 300) -> List[str]:
    """
    Generates a plan targeting exactly target_count captures, focused on solar events.
    """
    intervals = []
    
    # If a future start time is specified, add an initial interval to reach it
    effective_now = current_time
    if start_time and start_time > current_time:
        initial_delay = int((start_time - current_time).total_seconds())
        intervals.append(f"{initial_delay}s")
        effective_now = start_time
        # We don't count the initial delay as a capture
    
    last_event_time = effective_now
    captured_so_far = 0
    day_offset = 0
    
    location = LocationInfo("Custom", "USA", "UTC", lat, lon)

    while captured_so_far < target_count:
        day = effective_now.date() + timedelta(days=day_offset)
        s = sun(location.observer, date=day)
        
        # Events for the day: Sunrise and Sunset
        # We want to cluster around these
        for event_base in [s["sunrise"], s["sunset"]]:
            if captured_so_far >= target_count:
                break
                
            # Move to the start of the cluster (20m before the event)
            cluster_start = event_base - timedelta(minutes=20)
            
            if cluster_start > last_event_time:
                # Gap from last activity to this cluster
                gap_seconds = int((cluster_start - last_event_time).total_seconds())
                
                # If gap is huge (night), add a spacer capture
                if gap_seconds > 14400: # 4 hours
                    intervals.append(f"{gap_seconds // 2}s")
                    captured_so_far += 1
                    if captured_so_far >= target_count: break
                    intervals.append(f"{gap_seconds // 2}s")
                else:
                    intervals.append(f"{gap_seconds}s")
                
                captured_so_far += 1
                if captured_so_far >= target_count: break
                
                # Cluster: 5 captures every 10 mins (including the one that just triggered)
                for _ in range(4):
                    step_interval = 600 + random.randint(-jitter_range, jitter_range)
                    intervals.append(f"{step_interval}s")
                    captured_so_far += 1
                    if captured_so_far >= target_count: break
                
                last_event_time = cluster_start + timedelta(seconds=sum([int(i[:-1]) for i in intervals[-5:] if i.endswith('s')]))
            
        day_offset += 1
        if day_offset > 365: # Safety break
            break
                
    intervals.append("stop")
    return intervals

if __name__ == "__main__":
    LAT, LON = 47.6533, -122.3091
    TARGET = 100
    
    # Analyze the next few days for the printout
    events = get_solar_events(LAT, LON, date.today(), 3)
    print(f"Solar Analysis for {LAT}, {LON}:")
    print("-" * 60)
    for e in events:
        print(f"{e['date']}: Sunrise {e['sunrise'].strftime('%H:%M')} | Sunset {e['sunset'].strftime('%H:%M')} UTC")

    # Generate the full 100-step plan
    # Use UTC now for calculation
    now_utc = datetime.now(UTC)
    
    # Target: 8am PT tomorrow (Monday, Feb 23) -> 16:00 UTC
    target_start = datetime(2026, 2, 23, 16, 0, 0, tzinfo=UTC)
    
    plan_steps = generate_collection_plan(LAT, LON, now_utc, start_time=target_start, target_count=TARGET)
    
    # Calculate days based on total day_offset from the plan generation
    # (re-running generation or just moving the variable outside)
    total_days = 0
    test_count = 0
    while test_count < TARGET:
        total_days += 1
        # Simple estimate: ~12 captures per day in this logic
        test_count += 12

    print(f"\nGenerated {len(plan_steps) - 1} capture intervals to reach target.")
    print("\nSuggested Command:")
    # Group plan steps for cleaner output if needed, but we need them individual for Typer
    cmd = "uv run collect schedule"
    for step in plan_steps:
        cmd += f" --plan-steps {step}"
    
    print(cmd)
    
    print(f"\nPlan Summary:")
    print(f"  Target Captures: {TARGET}")
    print(f"  Duration: Approximately {total_days} days")
    print(f"  Jitter: ±5m per step")
