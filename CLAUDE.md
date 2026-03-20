# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Real-time image classifier that determines if Mount Rainier is visible ("out") using a live UW webcam feed. Uses a ConvNeXt Tiny backbone with LoRA fine-tuning, augmented with METAR weather data (visibility + ceiling) fed into the classifier head.

## Commands

### Python (uv)

```bash
# Tests
uv run pytest                              # all tests
uv run pytest train/tests/test_model.py -v # single test file

# Training
uv run training live        # continuous training loop (gradient accumulation)
uv run training once        # single capture + train cycle
uv run training batch data/20260222  # offline batch training on labeled dataset

# Data collection
uv run collect collect      # single capture (all webcams + METAR)
uv run collect live         # continuous collection loop

# Classification UI (FastAPI + Vite)
uv run classify start [data_folder]
uv run classify stop

# Nomad job management
nomad job run nomad/collect.hcl          # start collector tray
nomad job status mountain-collector      # check status
nomad alloc logs <alloc-id>              # view logs
nomad alloc logs -stderr <alloc-id>      # view error logs
```

### Frontend (ui/)

```bash
cd ui
npm run dev       # Vite dev server
npm run build     # type check + build
npm run lint      # ESLint
```

## Architecture

### Model (`train/model.py`)

`ConvNextLoRAModel` wraps `convnext_tiny` (timm) with PEFT LoRA adapters on the MLP `fc1`/`fc2` layers. The classifier head accepts a **dual input**: 768-dim image features concatenated with a 2-dim weather vector `[visibility, ceiling]` → Linear(770→256) + ReLU + Dropout → Linear(256→3). Three output classes: `0=Not Out`, `1=Full`, `2=Partial`.

Checkpoints saved to `train/checkpoints/`: `adapter_config.json`, `adapter_model.safetensors`, `classifier.pt`.

### Training Loop (`train/scheduler.py` + `train/utils.py`)

`WebcamStream` fetches JPEG from the webcam URL and converts directly to a `(1, 3, 224, 224)` tensor (no intermediate disk writes). `WeatherFetcher` queries METAR for KSEA and returns `[visibility_sm, ceiling_ft]`. The scheduler accumulates gradients over `N` captures before stepping (configurable in `mountain.toml`).

### Data Collection (`collect/collector.py`)

Writes timestamped directories: `data/YYYYMMDD/HHMMSS_us_UTC/{images/,metar/}`. Labels stored in `data/labels.yaml` as `{relative_path: label}`.

### Classification UI (`tools/classifier_server.py` + `ui/`)

FastAPI server writes its port to `data/classifier_server.port` at startup (dynamic port allocation). The React app (`ui/src/App.tsx`) polls `/api/images` for unlabeled batches (60 images), supports drag-to-select, hotkeys `1/2/0` for Full/Partial/None, and submits via `/api/label`. The Vite base path is `/classify/`; the API server reverse-proxies at that path.

### Configuration (`mountain.toml`)

Single source of truth for webcam URL, METAR station (`KSEA`), LoRA hyperparameters, checkpoint directory, collection intervals, and training schedule. Loaded via `train/config_loader.py`.

## Key Design Constraints

- **Zero-disk training:** Live frames go directly to tensors — never written to disk during live loops.
- **Dynamic port:** The classifier server picks a free port and writes it to `data/classifier_server.port`; the React UI fetches `config.json` at a relative path to discover it.
- **MPS device:** Apple Silicon (MPS) is the primary target; falls back to CPU.
- **Precision over recall:** The system is tuned to minimize false positives (announcing the mountain is out when it isn't).
