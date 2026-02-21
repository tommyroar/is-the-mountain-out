# is-the-mountain-out
Determine if Mount Rainier is "out" (visible) using real-time image classification with iterative LoRA training on live webcam streams, optimized for Apple Silicon (MPS).

## Overview
This system performs online learning using Parameter-Efficient Fine-Tuning (PEFT) with LoRA on a `convnext_tiny` vision backbone. It integrates METAR weather data as a secondary input to the classification head, improving the model's accuracy by incorporating real-world visibility and ceiling data.

## Features
- **Hardware-Accelerated Training:** Fully optimized for Mac M1/M2/M3 using Metal Performance Shaders (MPS).
- **Online Learning:** Iterative LoRA training using live webcam captures converted directly to PyTorch tensors with **zero disk usage** for training data.
- **Dual-Input Architecture:** Classification head accepts both image features (768) and a 2D METAR weather vector (visibility, ceiling).
- **Flexible Data Collection:** `collect` command for capturing datestamped datasets for offline batch training.
- **Periodic Training:** `launchctl` service management for continuous background training.
- **Batch Processing:** Support for training on local datasets with `/images` and `/metar` subfolders.

## Usage
### Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- Mac with Apple Silicon (for MPS acceleration).

### Setup
1. Configure `mountain.toml` in the root directory for target mountain details and webcams.
2. Configure `train/config.toml` for model settings, schedule, and collection intervals.

### Commands
All commands should be run from the `/train` directory:
```bash
# Start a continuous live training loop with gradient accumulation
uv run python scheduler.py live

# Single capture of all webcams and METAR data to /data (git-ignored)
uv run python collector.py collect

# Batch train on a local folder with /images and /metar subfolders
uv run python scheduler.py batch --folder /path/to/data

# Manage background training service via launchctl
uv run python scheduler.py schedule   # Install and load
uv run python scheduler.py unschedule # Unload and remove
```

## Technical Strategy
- **Backbone:** `convnext_tiny` via `timm`.
- **PEFT:** LoRA layers targeting the `fc1` and `fc2` Linear layers in the MLP blocks.
- **Weather Input:** Real-time METAR data from NOAA (e.g., KSEA) normalized and concatenated with image features.
- **Optimizer:** `Adam` with a single-batch or accumulated-batch training cycle.
- **Zero-Disk Training:** Live frames from `OpenCV` are moved directly to MPS tensors, avoiding overhead and privacy concerns related to storing temporary image files during the live loop.

## Project Structure
- `mountain.toml`: Target-specific configuration (coordinates, height, webcam links).
- `train/config.toml`: General training and scheduling configuration.
- `train/scheduler.py`: Main CLI and training loop orchestration.
- `train/collector.py`: Data collection utility.
- `train/utils.py`: Shared hardware-accelerated capture and weather fetching logic.
- `train/model.py`: Dual-input LoRA model implementation.
- `train/config_loader.py`: Unified TOML configuration loader.
- `data/`: Local storage for `collect` outputs (ignored by git).
