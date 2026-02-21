# is-the-mountain-out
Determine if "the mountain" (Mount Rainier) is "out" using iterative LoRA training on live webcam streams, optimized for Apple Silicon.

## Design
This project implements a real-time image classification system that fine-tunes a `convnext_tiny` model using Parameter-Efficient Fine-Tuning (PEFT) with LoRA. The training occurs iteratively as frames are captured from webcams, with a strict constraint of zero disk usage for image data.

### Technical Strategy
- **Hardware Acceleration:** Fully optimized for Mac M1/M2/M3 using Metal Performance Shaders (MPS).
- **Online Learning:** Iterative LoRA training using live webcam captures converted directly to PyTorch tensors.
- **Data Pipeline:** `OpenCV` for stream capture, `torchvision` for on-device transformations.
- **Model:** `timm` provided `convnext_tiny` wrapped with `peft` LoRA.
- **Scheduling:** `APScheduler` with crontab-style triggers defined in `config.yaml`.
- **Optimizations:** Incorporation of time-of-day and METAR weather data to refine predictions (e.g., visibility thresholds).

## Usage
To start the iterative training loop on Apple Silicon:
1. Ensure `uv` is installed.
2. Configure `mountain.toml` in the root directory.
3. Configure `train/config.yaml` with your schedule and model settings.
4. Run the training command:
   ```bash
   cd train && uv run training
   ```

## Design
This project implements a real-time image classification system that fine-tunes a `convnext_tiny` model using Parameter-Efficient Fine-Tuning (PEFT) with LoRA. The training occurs iteratively as frames are captured from multiple webcams and processed in small batches.

### Technical Strategy
- **Hardware Acceleration:** Fully optimized for Mac M1/M2/M3 using Metal Performance Shaders (MPS).
- **Online Learning:** Iterative LoRA training using live webcam captures converted directly to PyTorch tensors.
- **Batch Processing:** Captures are collected from all sources and trained in small batches for improved efficiency.
- **Dual-Input Head:** The classification head accepts both image features and a 2D METAR weather vector (visibility and ceiling) to refine predictions.
- **Data Pipeline:** `OpenCV` for stream capture, `torchvision` for on-device transformations.
- **Scheduling:** `APScheduler` with crontab-style triggers defined in `config.yaml`.
