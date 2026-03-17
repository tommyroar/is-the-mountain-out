---
name: mountain-capture
description: Schedule and manage webcam captures of Mount Rainier via Nomad. Supports ad-hoc single captures and persistent collection services. Use when the mountain is confirmed "out" or for scheduled monitoring.
---

# Mountain Capture

This skill manages image collection jobs for Mount Rainier via Nomad.

## Capture Modes

### 1. Ad-Hoc Single Capture (Batch)
Use this to trigger an immediate, one-off capture regardless of whether a persistent collector is running.
- **Nomad Job:** `mountain-capture-single`
- **Execution:** 
  ```bash
  python3 scripts/capture_now.py
  ```
- **Menu Bar Feature:** From any active capture job's tray icon, select **"Capture additional image"** to trigger this Nomad job instantly.
- **Storage:** Images are stored in `data/` with unique session prefixes (e.g., `manual-177...`). Each will spawn its own tray icon briefly during capture.

### 2. Persistent Collection (Service)
The long-running collector service managed by Nomad.
- **Nomad Job:** `mountain-collector`
- **Status:** 
  ```bash
  nomad job status mountain-collector
  ```
- **Control:**
  - Start: `nomad job run nomad/collect.hcl`
  - Stop: `nomad job stop mountain-collector`

### 3. Custom Batch (e.g., "The Mountain is Out")
For capturing multiple images over a window (e.g., 10 captures in 1 hour).
- **Tool:** `tools/capture_out.py`
- **Nomad Job:** `mountain-capture-out`

## Key Files
- `nomad/once.hcl`: Template for single batch captures.
- `nomad/collect.hcl`: Template for the persistent service.
- `data/collector_state.json`: Real-time status of the active collector.
- `data/capture_plan.json`: The current schedule for the active collector.

## Troubleshooting
- **No images captured:** Check Nomad logs: `nomad alloc logs <alloc-id> tray`
- **Port conflicts:** The collector automatically finds an available port and writes to `data/classifier_server.port`.
