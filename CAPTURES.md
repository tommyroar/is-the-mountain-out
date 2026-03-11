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

## Dataset Statistics (As of 2026-03-11)
After an initial high-frequency collection phase, the dataset was programmatically pruned to ensure high variance and manageable manual labeling.

- **Total Historical Captures:** 6,266
- **Pruned Set (Baseline):** **804 high-variety images**
- **Temporal Span:** 19 Days (2026-02-21 to 2026-03-11)
- **Retention Rate:** ~12.8%

## Data Pruning Methodology
To reduce redundancy while maintaining atmospheric diversity, the `tools/prune_data.py` script was applied with the following logic:

1. **Temporal Downsampling:** Minimum 300s (5-minute) interval between retained captures during daylight.
2. **Darkness Filtering:** General threshold of 10.0 (out of 255) mean pixel brightness to remove pitch-black frames.
3. **Hourly Anchor:** Guaranteed retention of one image per hour regardless of darkness to provide the model with "true night" samples across the entire 19-day span.
4. **Static Scene Removal:** Discarded images with < 2.0 mean pixel difference from the previously retained frame.

## Plan Logs
| Date | Status | Plan Summary |
| :--- | :--- | :--- |
| 2026-02-22 | **COMPLETE** | 3-Day Solar Plan with Jitter (Sunrise/Sunset focus) |
| 2026-03-07 | **COMPLETE** | High-frequency continuous capture loop (~1 min intervals) |
| 2026-03-11 | **REFINED** | Pruned 6k+ images down to 804 high-variance baseline samples |
