# Model Checkpoints & History

This document catalogs the major model checkpoints saved during the project's development and outlines expectations for future models.

## Current Checkpoints

### 1. `checkpoints_v1_binary`
- **Date:** March 11, 2026
- **Architecture:** 2-Class Binary (Not Out / Out)
- **Dataset:** Phase 1 (1,260 images)
- **Strategy:** Heavy oversampling of the "Out" class (1.4% representation).
- **Status:** Retired. This model was highly accurate on unambiguous days but suffered from false positives during "Partial" visibility, leading to the 3-class redesign.

### 2. `checkpoints_v2_pre_reclassify`
- **Date:** March 14, 2026
- **Architecture:** 2-Class Binary
- **Status:** Archived. This was the final state of the binary model weights immediately prior to the dataset reclassification into 3 classes.

### 3. `train/checkpoints` (Current Phase 2 Baseline)
- **Date:** March 14, 2026
- **Architecture:** 3-Class (Not Out, Full, Partial)
- **Dataset:** 1,319 images (Phase 1 re-labeled)
  - Not Out: 1,254 (95.1%)
  - Full: 8 (0.6%)
  - Partial: 57 (4.3%)
- **Strategy:** Fresh ConvNeXt weights fine-tuned with 78x oversampling on "Full" and 11x on "Partial".
- **Status:** Active Baseline.

## Future Expectations

### The April 14 Fine-Tuned Model (`v3_spring`)
The current Phase 2 data collection run is scheduled to conclude on **April 14**. This 30-day "Diffuse Spring" solar plan captures 21 images a day with a focus on capturing rapid clearing events and diverse cloud layers.

Once the new dataset is labeled and the model is fine-tuned, we will run the new `tools/evaluate.py` script. 

**Expectations:**
1. **Partial Class Separation:** A massive improvement in F1 and Precision for the "Partial" class. The model should better understand the boundary between a fully obscured mountain and one peeking through a marine layer.
2. **False Positives:** A continued suppression of false positives (predicting Full/Partial when it is Not Out).
3. **METAR Reliance:** The model should demonstrate an even stronger fusion of visual and high-frequency METAR data to handle late-spring volatile weather.

## Evaluation
To compare a checkpoint against a labeled dataset, use the evaluation script:
```bash
uv run python tools/evaluate.py --checkpoint path/to/checkpoint --labels path/to/labels.yaml
```