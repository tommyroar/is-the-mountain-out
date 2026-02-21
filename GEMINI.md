# GEMINI.md - Project Mandates & Technical Context

## Overview
This project implements an iterative, real-time image classification system to determine if Mount Rainier is "out" (visible). It uses Parameter-Efficient Fine-Tuning (PEFT) with LoRA on a `convnext_tiny` vision backbone, optimized for Apple Silicon (MPS).

## Architectural Mandates
- **Hardware Acceleration:** All training and inference MUST target Metal Performance Shaders (`mps`) where available.
- **Zero-Disk Training:** Live captures from webcams MUST be converted directly to PyTorch tensors and moved to the MPS device. Intermediate image files MUST NOT be saved to disk during the live training loop.
- **Dual-Input Model:** The classification head MUST accept both vision features (768-dim) and a METAR weather vector (2-dim: visibility, ceiling).
- **Persistence:** The model MUST save/load LoRA adapters and classifier weights to/from the `train/checkpoints` directory to support continuous online learning.
- **Configuration:** Project configuration is split between `mountain.toml` (root) and `train/config.toml`.

## Build & Environment
The project uses `uv` for dependency management from the root directory.
1. **Initialize Environment:**
   ```bash
   uv venv
   ```
2. **Install in Editable Mode:**
   To enable the `uv run training` and `uv run collect` commands:
   ```bash
   uv pip install -e .
   ```

## CLI Commands
All commands should be executed from the **root project directory**:
- `uv run training live`: Continuous training loop with gradient accumulation and persistence.
- `uv run training once`: Single capture and training cycle (used by `launchctl`).
- `uv run training batch <folder>`: Offline training on existing datasets.
- `uv run collect`: Single capture of all sources to the `/data` directory.
- `uv run training schedule`: Installs the `launchctl` periodic service.
- `uv run training unschedule`: Removes the `launchctl` periodic service.

## Testing & Validation
- **Test Runner:** `pytest`
- **Execution:** `uv run pytest`
- **Coverage Requirements:**
  - `test_config_loader`: Configuration merging and validation.
  - `test_model`: LoRA weight updates, dual-input integrity, and checkpoint save/load.
  - `test_webcam`: Hardware acceleration and zero-disk capture.
  - `test_scheduler`: Training cycle orchestration.

## Data Structure
- `/data`: Local directory for collected images and METAR files (ignored by git).
- `/train/checkpoints`: Local storage for model weights (ignored by git).
- `/train/tests`: Comprehensive unit test suite.
