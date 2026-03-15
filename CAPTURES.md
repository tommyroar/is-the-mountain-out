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

### Historical Weather Context (Phase 1):
The 1.4% "Out" rate, while lower than the annual average of 23%, is consistent with the **Late-Winter Seattle Climatology** for 2026:
1. **PNW Variability:** February 21 – March 11 was marked by typical "late-winter gloom." METAR data for successful "Out" frames (e.g., Feb 22-23) showed a consistent **10SM visibility** and relatively high ceilings (>4,500ft), but these windows were short-lived.
2. **Spring Snowstorm:** A significant late-season system brought **moderate snow** on March 10, followed by rain on March 11, which explains the total lack of visibility in the final days of the run.
3. **La Niña Influence:** The 2026 spring occurred during a **La Niña to ENSO-neutral transition**, which historically correlates with cooler, wetter, and cloudier conditions in the Puget Sound area.

### Climate Projection (Phase 2):
Conditions are expected to improve significantly during the March/April window:
- **Increasing High Pressure:** As spring progresses, the frequency of persistent high-pressure ridges increases, which leads to the "clearing" of low-level marine layers.
- **ENSO Normalization:** The transition toward neutral ENSO conditions will likely reduce the frequency of the "unending cloud" pattern observed in Phase 1.
- **Daylight Expansion:** Longer days provide more opportunities for the "mid-day clearing" effect, where solar heating breaks up low clouds.

### Key Findings:
1. **Weather Dominance:** The "Not Out" class is overwhelmingly dominant, confirming that visibility is a rare event during this 19-day window.
2. **False Positives Risk:** The model will likely overfit to "Not Out" unless we use weighted loss functions or oversample the 18 positive frames during the initial fine-tuning.
3. **METAR Correlation:** Initial inspection confirms that "Out" frames strictly correlate with high visibility (>10SM) and ceilings above the mountain's critical visibility thresholds.

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

## Phase 1 Training Results (Established 2026-03-11)
After establishment of the ground truth labels, the baseline model was fine-tuned using the following configuration:
- **Optimizer:** Adam (LR: 0.0001)
- **Epochs:** 5
- **Balance Strategy:** 17x Oversampling of "Out" class.
- **Hardware:** MPS (Metal Performance Shaders).

### Current Model Performance (Regression Suite):
- ✅ **Darkness Test:** 100% accurate in predicting "Not Out" for 0.0 brightness frames.
- ✅ **Visibility Test:** 100% accurate in identifying confirmed "Mountain Out" frames from Phase 1.

## A/B Testing: METAR Ablation Study (2026-03-11)
A systematic A/B comparison was performed to determine if METAR weather data provides unique signal or if it is redundant with the vision backbone.

| Variant | F1-Score | Precision | Recall |
| :--- | :---: | :---: | :---: |
| **Vision Only** | **0.525** | 0.556 | 0.500 |
| **Full METAR (Real-time)** | 0.499 | **0.700** | **0.556** |
| **Sparse METAR (Daily)** | 0.507 | 0.544 | 0.500 |

### Final Architecture Decision:
1. **Retention of METAR:** While Vision Only achieved higher F1, **Full METAR** provided a critical **26% boost in Precision**. For a public notification system, minimizing false positives (announcing the mountain is out when it isn't) is the highest priority.
2. **High-Frequency Synchronization:** A/B tests showed that "Sparse" weather data significantly degraded precision. **The collector will maintain 1:1 image-to-METAR synchronization** to ensure the model has the most accurate atmospheric state at the micro-level.

## Phase 2 Training: 3-Class Reclassification (2026-03-14)

The Phase 1 binary model (Out/Not Out) was retired in favor of a 3-class architecture to better reflect real-world visibility states.

### Reclassification
The original 1,260 binary labels were discarded. The full dataset of 1,319 images was re-labeled via the interactive classifier UI with three classes:
- **Class 0 — Not Out:** 1,254 images (95.1%)
- **Class 1 — Full:** 8 images (0.6%)
- **Class 2 — Partial:** 57 images (4.3%)

The split of "Out" frames into Full/Partial captures the important distinction between unobstructed peak views and partially-obscured sightings. The 18 binary "Out" frames became 8 Full + 57 Partial as more nuanced labeling revealed previously ambiguous frames.

### Baseline Training Run
- **Checkpoint:** `train/checkpoints/` (archived v1 binary → `checkpoints_v1_binary/`, v2 pre-reclassify → `checkpoints_v2_pre_reclassify/`)
- **Mode:** Fresh (pretrained ConvNeXt weights only, no checkpoint loaded)
- **Optimizer:** Adam (LR: 0.0001)
- **Epochs:** 10
- **Balance Strategy:** 78x oversampling of "Full", 11x oversampling of "Partial" → **2,505 samples/epoch**
- **Hardware:** MPS (Metal Performance Shaders)

### Notes
Per-epoch loss is not yet logged by the batch training loop — qualitative validation via `uv run training once` is the current smoke test. Loss logging is a candidate for Phase 2 iteration.

## Tray Collector Improvements (2026-03-15)

The macOS menu bar collector was substantially overhauled to decouple the tray UI from the capture service and fix several reliability issues.

### Architecture
- **State file pattern:** Capture service writes `data/collector_state.json` atomically (tmp + rename); tray polls it every 5 minutes via `rumps.Timer`. Any process can update state independently.
- **Per-session index:** Each run writes `data/labels.{uuid}.yaml` with null-labeled image paths for future classification. "Open Index File" in the tray reveals this file in Finder.
- **Plan-aware resume:** On restart, `capture_count` and `plan_index` are seeded from the previous state file so progress is never reset to zero.

### Bug Fixes
- **`last_capture_at` always "—" on startup:** Two root causes fixed:
  1. `_derive_initial_last_capture_at()` extracted as a testable function — derives last capture from most recent past plan timestamp, falling back to previous state file (only if the value is actually in the past, guarding against stale future values from prior bugs).
  2. Capture loop's "Capturing..." status write omitted `last_capture_at`, resetting it to `None` before the tray could read the initial state. Fixed by tracking `last_capture_at` as a loop variable passed through every `write_state` call.
- **`last_capture_at` set to future scheduled time:** `just_captured_at` was incorrectly assigned from `plan_timestamps[plan_index]` (the next scheduled slot) instead of `datetime.now()`. Fixed.

### Tray Menu
Menu now displays: Status · Progress (N/total %) · Last Capture · Next Capture · **Final Capture** · Session · Open {index file path} · Quit

- Timestamps formatted as `Today HH:MM` or `Mon DD HH:MM` to show date context across the 30-day plan.
- **Final Capture** shows the last scheduled timestamp in the plan (end of 30-day spring window).

### Tests
26 → 27 tests covering: state file roundtrip, atomic write, render fields, refresh skip-on-unchanged, `pct_complete`, `_fmt_time`, `_derive_initial_last_capture_at` (plan past, state fallback, future-state guard, empty), and the "Capturing..." write must not reset `last_capture_at`.

### Scheduler Changes
- `Trainer.__init__` now accepts `fresh: bool` to skip checkpoint loading for baseline training
- `batch` command now accepts `--labels path/to/labels.yaml` directly, decoupling training input from folder structure
- Removed dead class-weight code that computed `w0`/`w1` but never passed them to `train_step`

## Phase 2: Spring Collection (Phase 2)
**Goal:** Gather high-variance data during March/April when visibility windows are more frequent.

### Strategy: Diffuse Daylight Sampling
Based on Phase 1 learnings, we have optimized the sampling frequency:
- **Golden Hour (Sunrise/Sunset ±45m):** High-density sampling (10-minute intervals).
- **Mid-Day:** Moderate sampling (30-minute intervals with jitter) to catch varying shadow patterns.
- **Night Anchor:** Minimal sampling (one capture every 4 hours) to maintain a baseline of "Not Out" noise without flooding the dataset.
- **Yield:** Approximately 21 high-quality images per 24-hour cycle (~630 images total).
