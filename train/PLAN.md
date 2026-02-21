# LoRA Training Implementation Plan

This plan details the steps to build a real-time image classification system that fine-tunes `convnext_tiny` on live webcam streams using LoRA, optimized for MPS.

## Milestone 1: Environment & Configuration
- [x] Initialize project with `uv` in `/train`.
- [x] Define dependencies in `pyproject.toml` (torch, torchvision, timm, peft, etc.).
- [x] Create initial `train/config.yaml` with camera indices and cron schedules.
- [x] Implement `ConfigLoader` in `train/config_loader.py` to parse `train/config.yaml`.

## Milestone 2: Hardware-Accelerated Data Pipeline
- [x] Implement `WebcamStream` class in `train/webcam.py` using `OpenCV`.
- [x] Add `capture_to_tensor()` to move frames directly to the `mps` device.
- [x] Use `torchvision.transforms` for on-device image preprocessing.

## Milestone 3: LoRA Model & Training Loop
- [x] Initialize `timm.create_model('convnext_tiny', pretrained=True, num_classes=0)`.
- [x] Wrap the backbone with `LoraConfig` targeting ConvNeXt's Linear (fc) layers.
- [x] Implement a custom dual-input head (image features + METAR vector).
- [x] Implement the training step with `APScheduler` triggers in `train/scheduler.py`.
- [x] Ensure memory efficiency using `del` and `torch.mps.empty_cache()`.

## Milestone 4: Verification & Testing
- [x] Implement `pytest` for MPS detection and zero-disk-usage checks.
- [x] Add a "Mock Webcam" mode for testing via unit test mocks.
- [x] Verify LoRA parameter updates.

## Milestone 5: Weather & Filtering
- [x] Implement `WeatherFetcher` in `train/weather.py` using `metar` library.
- [x] Fetch and normalize METAR data (visibility, ceiling) into a 2D vector.
- [x] Integrate weather vector as a secondary input to the model's classification head.
- [ ] Add time-of-day logic to skip training/prediction at night.
