import sys
import random
from datetime import datetime, timedelta, date
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

def generate_collection_plan(events: List[dict], current_time: datetime, jitter_range: int = 300) -> List[str]:
    """
    Generates a multi-day plan targeting golden hours with random jitter.
    jitter_range: max seconds to offset each capture (default 5m).
    """
    intervals = []
    last_event_time = current_time
    
    for event in events:
        # Targets: Sunrise and Sunset
        for target_base in [event["sunrise"], event["sunset"]]:
            # Apply random jitter
            jitter = random.randint(-jitter_range, jitter_range)
            target = target_base + timedelta(seconds=jitter)
            
            if target > last_event_time:
                diff = target - last_event_time
                seconds = int(diff.total_seconds())
                
                # Split long gaps (e.g., night or mid-day) to maintain activity
                if seconds > 14400: # > 4 hours
                    parts = 3
                    for _ in range(parts):
                        intervals.append(f"{seconds // parts}s")
                else:
                    intervals.append(f"{seconds}s")
                
                # Add a few rapid captures around the event
                intervals.append(f"{1200 + random.randint(-60, 60)}s") # ~20m
                intervals.append(f"{1200 + random.randint(-60, 60)}s") # ~20m
                
                last_event_time = target + timedelta(minutes=40)
                
    intervals.append("stop")
    return intervals

if __name__ == "__main__":
    LAT, LON = 47.6533, -122.3091
    DAYS = 3
    start = date.today()
    events = get_solar_events(LAT, LON, start, DAYS)
    
    print(f"Solar Analysis (3-Day Plan) for {LAT}, {LON}:")
    print("-" * 60)
    for e in events:
        print(f"{e['date']}: Sunrise {e['sunrise'].strftime('%H:%M')} | Sunset {e['sunset'].strftime('%H:%M')} UTC")

    # Use a fixed seed for 'Suggested' output consistency in this turn, 
    # but actual usage will be random.
    random.seed(42)
    plan_steps = generate_collection_plan(events, datetime.now(events[0]['sunrise'].tzinfo))
    
    print("\nSuggested 3-Day Plan with Jitter:")
    print(f"uv run collect schedule --plan-steps {' '.join(plan_steps)}")
    
    print("\nNote: Jitter (±5m) has been applied to targets to ensure diverse temporal samples.")
