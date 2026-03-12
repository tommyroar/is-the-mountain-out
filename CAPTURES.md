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
After an initial high-frequency collection phase and programmatic pruning, the baseline dataset has been manually classified.

- **Total Images Processed:** 1,286
- **Total Labeled:** 1,260
- **Mountain Out (Class 1):** **18 images** (1.4%)
- **Not Out (Class 0):** **1,242 images** (98.6%)
- **Retention Rate (from 6k original):** ~20%

## Classification Analysis
The initial baseline capture reveals an **extreme class imbalance**. Out of over 1,200 unique atmospheric samples, the mountain was only clearly visible in 18 frames.

### Key Findings:
1. **Weather Dominance:** The "Not Out" class is overwhelmingly dominant, confirming that visibility is a rare event during this 19-day window.
2. **False Positives Risk:** The model will likely overfit to "Not Out" unless we use weighted loss functions or oversample the 18 positive frames during the initial fine-tuning.
3. **METAR Correlation:** Initial inspection suggests that most "Out" frames correspond to high visibility (>10SM) and high or clear ceilings, as expected.

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
| 2026-03-11 | **REFINED** | Pruned 6k+ images down to baseline samples |
| 2026-03-11 | **CLASSIFIED**| Manual labeling of 1,260 images completed |
| 2026-03-12 | **ACTIVE**    | Phase 2: 30-Day "Diffuse Spring" Solar Plan (21 images/day) |

## Phase 2: Spring Collection (Phase 2)
**Goal:** Gather high-variance data during March/April when visibility windows are more frequent.

### Strategy: Diffuse Daylight Sampling
Based on Phase 1 learnings, we have optimized the sampling frequency:
- **Golden Hour (Sunrise/Sunset ±45m):** High-density sampling (10-minute intervals).
- **Mid-Day:** Moderate sampling (30-minute intervals with jitter) to catch varying shadow patterns.
- **Night Anchor:** Minimal sampling (one capture every 4 hours) to maintain a baseline of "Not Out" noise without flooding the dataset.
- **Yield:** Approximately 21 high-quality images per 24-hour cycle (~630 images total).
