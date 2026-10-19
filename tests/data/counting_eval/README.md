# PRAMAAN Person Counting Evaluation Data

This directory contains local development clips and labels for the
PRAMAAN person counting evaluation harness.

**This directory is git-ignored. Files here are local only and must NOT be committed, shared, or transmitted.**

## Consent requirement
Only record clips with the explicit consent of every person in frame.
Delete these files when they are no longer needed for development.

## Contents
- `manifest.json` — Index of all clips with their true-count labels
- `*.avi` — Short webcam clips (local only)
- `eval_results_*.json` — Evaluation run outputs

## Recommended scenarios
Record at least one clip for each of these scenarios before drawing conclusions:

| Scenario | Label flag | Notes |
|----------|-----------|-------|
| Empty room | `--label 0` | Baseline false-positive check |
| 1 person seated | `--label 1` | Single-person detection baseline |
| 2 people side-by-side | `--label 2` | Tests NMS IoU merging |
| 3 people side-by-side | `--label 3` | Main target scenario |
| 1 person at ~1m | `--label 1` | Close-range |
| 1 person at ~2m | `--label 1` | Medium distance |
| 1 person at ~3m | `--label 1` | Far/small in frame |
| Bright lighting | `--label N` | Lighting sensitivity |
| Dim lighting | `--label N` | Lighting sensitivity |
| Person walking in/out | `--label 1` | Dynamic count test |

## Commands
```bash
# Record a clip
python scripts/eval_person_counting.py capture --label 2 --seconds 10 --scenario 2person_seated

# Evaluate all clips
python scripts/eval_person_counting.py eval

# Compare with alternative settings
python scripts/eval_person_counting.py eval --conf 0.35 --iou 0.70  # baseline
python scripts/eval_person_counting.py eval --conf 0.25 --iou 0.45  # improved

# List clips
python scripts/eval_person_counting.py list
```
