#!/usr/bin/env python3
import subprocess
import sys
import time
from pathlib import Path

def trigger_capture():
    """Triggers a single capture by running the 'mountain-capture-single' Nomad job."""
    hcl_path = Path("nomad/once.hcl")
    if not hcl_path.exists():
        print(f"Error: {hcl_path} not found.")
        sys.exit(1)

    print(f"Submitting Nomad job: {hcl_path}...")
    try:
        # Run nomad job run and capture output
        result = subprocess.run(
            ["nomad", "job", "run", str(hcl_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print("Nomad job submitted successfully.")
        
        # Extract the Eval ID from output
        # e.g. "==> 2026-03-17T01:30:00-07:00: Monitoring evaluation \"abcdef12\""
        for line in result.stdout.splitlines():
            if "Monitoring evaluation" in line:
                eval_id = line.split()[-1].strip('"')
                print(f"Evaluation ID: {eval_id}")
                break
        
        print("Capture in progress via Nomad (batch job)...")
    except subprocess.CalledProcessError as e:
        print(f"Error submitting Nomad job:\n{e.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    trigger_capture()
