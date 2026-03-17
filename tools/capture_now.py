#!/usr/bin/env python3
import subprocess
import sys
import argparse
from pathlib import Path

def trigger_capture(session_id=None):
    """Triggers a single capture by running the 'mountain-capture-single' Nomad job."""
    hcl_path = Path("nomad/once.hcl")
    if not hcl_path.exists():
        # Check relative to script location
        hcl_path = Path(__file__).parent.parent / "nomad" / "once.hcl"
        
    if not hcl_path.exists():
        print(f"Error: {hcl_path} not found.")
        sys.exit(1)

    cmd = ["nomad", "job", "run"]
    if session_id:
        cmd.extend(["-var", f"session_id={session_id}"])
    cmd.append(str(hcl_path))

    print(f"Submitting Nomad job: {' '.join(cmd)}...")
    try:
        # Run nomad job run and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print("Nomad job submitted successfully.")
        
        # Extract the Eval ID from output
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", help="Session ID to use for this capture")
    args = parser.parse_args()
    trigger_capture(args.session_id)
