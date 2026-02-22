# CAPTURES.md - Data Collection Strategy

## Baseline Collection (Phase 1)
**Goal:** 100 high-variety images with corresponding METAR data.
**Primary Target:** UW ATG Webcam 2 (Mount Rainier SE orientation).

### Strategy: Solar-Aligned Jitter
To ensure the most robust training baseline, captures are scheduled based on solar events rather than fixed intervals.

- **Golden Hour Clusters:** 3 captures at 20-minute intervals centered on sunrise and sunset.
- **Temporal Jitter:** ±5 minutes of random offset applied to every target to prevent synchronization with camera refresh cycles or repetitive conditions.
- **Condition Diversity:** Intentional slow-sampling during mid-day and night to capture a full range of lighting and weather states.

### Configuration
- **Location:** 47.6533, -122.3091 (UW ATG Building)
- **Tool:** `tools/solar_plan.py`
- **Estimated Yield:** ~11 images / 24 hours.
- **Target Duration:** ~9 days for 100 images.

## Plan Logs
| Date | Status | Plan Summary |
| :--- | :--- | :--- |
| 2026-02-22 | **ACTIVE** | 3-Day Solar Plan with Jitter (Sunrise/Sunset focus) |
