# GEMINI.md - Project Mandates & Technical Context

## Overview
This project implements an iterative, real-time image classification system to determine if Mount Rainier is "out" (visible). It uses Parameter-Efficient Fine-Tuning (PEFT) with LoRA on a `convnext_tiny` vision backbone, optimized for Apple Silicon (MPS).

## Architectural Mandates
- **Hardware Acceleration:** All training and inference MUST target Metal Performance Shaders (`mps`) where available.
- **Zero-Disk Training:** Live captures from webcams MUST be converted directly to PyTorch tensors and moved to the MPS device. Intermediate image files MUST NOT be saved to disk during the live training loop.
- **Dual-Input Model:** The classification head MUST accept both vision features (768-dim) and a METAR weather vector (2-dim: visibility, ceiling).
- **Configuration:** Project configuration is split between `mountain.toml` (target mountain/webcams) and `train/config.toml` (training/scheduling parameters).

## Build & Environment
The project uses `uv` for dependency management.
1. **Initialize Environment:**
   ```bash
   cd train && uv venv
   ```
2. **Install in Editable Mode:**
   To enable the `uv run training` and `uv run collect` commands, the package must be installed as editable:
   ```bash
   cd train && uv pip install -e .
   ```

## CLI Commands
All commands should be executed from the `/train` directory:
- `uv run training live`: Continuous training loop with gradient accumulation.
- `uv run training once`: Single capture and training cycle (used by `launchctl`).
- `uv run training batch --folder <path>`: Offline training on existing datasets.
- `uv run collect`: Single capture of all sources to the `/data` directory.
- `uv run training schedule`: Installs the `launchctl` periodic service.

## Testing & Validation
Rigorous validation is required for all changes.
- **Test Runner:** `pytest`
- **Execution:**
  ```bash
  cd train && uv run pytest
  ```
- **Coverage Requirements:**
  - `test_config_loader`: Configuration merging and validation.
  - `test_model`: LoRA weight updates and dual-input integrity.
  - `test_webcam`: Hardware acceleration and zero-disk capture.
  - `test_scheduler`: Training cycle orchestration.

## Data Structure
- `/data`: Local directory for collected images and METAR files (ignored by git).
- `/train/tests`: Comprehensive unit test suite.
