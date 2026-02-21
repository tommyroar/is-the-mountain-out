---
library_name: peft
tags:
- lora
- vision
- weather
- dual-input
- convnext
---

# Mount Rainier "Out" Detector

This model implements an iterative image classification system to determine if Mount Rainier is "out" (visible) based on live webcam streams and real-time weather data.

## Model Details

### Model Description

- **Developed by:** tommyroar
- **Model type:** Vision-Backbone with Dual-Input Linear Head
- **Finetuned from model:** `convnext_tiny` (via `timm`)
- **PEFT Method:** LoRA (Low-Rank Adaptation)
- **Primary Input:** 224x224 RGB Image (Webcam capture)
- **Secondary Input:** 2D METAR Weather Vector (Normalized visibility and ceiling)

### Model Architecture
The model uses a pre-trained ConvNeXt-Tiny backbone for feature extraction (768-dim features). These features are concatenated with a 2-dim weather vector (visibility, ceiling) and passed through a custom classification head:
1. `Linear(768 + 2, 256)`
2. `ReLU`
3. `Dropout(0.1)`
4. `Linear(256, 2)` (Binary classification: Not Out / Out)

## Uses

### Direct Use
The model is designed for real-time monitoring of Mount Rainier visibility from various regional webcams (e.g., UW Red Square, Paradise Mountain).

### Out-of-Scope Use
This model should not be used for safety-critical navigation or aviation decisions. It is purely for informational and recreational purposes.

## Training Details

### Training Data
The model is trained iteratively using live captures from regional webcams and normalized METAR data from KSEA.

### Training Procedure
- **Optimizer:** Adam (LR=1e-3)
- **Hardware:** Apple Silicon (MPS - Metal Performance Shaders)
- **Technique:** Iterative Online Learning with Gradient Accumulation (default steps: 4)
- **Zero-Disk Policy:** Live training frames are converted directly to tensors and moved to GPU memory without intermediate storage.

## Evaluation

### Target Benchmarks
- **Accuracy:** > 95%
- **Precision:** > 98% (High priority on minimizing false positives)
- **Loss:** < 0.10
- **F1-Score:** > 0.92

## Technical Specifications

### Compute Infrastructure
- **Hardware:** Apple Silicon (M1/M2/M3)
- **Software:** PyTorch with MPS backend, PEFT, TIMM

## How to Get Started
The model is managed via the `mountain-trainer` project CLI:
```bash
# Load checkpoints and run a single live training cycle
uv run training once
```

### Framework versions
- PEFT 0.18.1
- torch 2.10.0
- timm 1.0.24
