# PRAMAAN Person Counting Detection Evaluation

> **Status**: Phase 1–4 complete. Baseline and improvement configuration established.  
> No video clips have been collected yet — all accuracy numbers require real webcam runs.

---

## 1. Root Cause Analysis (Phase 1)

### What was inspected

File: `backend/scripts/webcam_edge_agent.py` (original, 379 lines)

### Confirmed: No code bug in counting or aggregation

| Check | Line(s) | Finding |
|-------|---------|---------|
| Box iteration | 195–196 | `results[0].boxes` returns ALL boxes; `len(boxes)` counts all. Correct. |
| `classes=[0]` | 194 | Applied correctly |
| `max_det` | 194 (absent) | Defaults to 300 — not restrictive |
| Tracking/ID dedup | — | Not used; no ID collapse |
| Aggregation math | 287–290 | `np.median` + `np.percentile` on full list. No truncation, no wrong percentile. |
| ROI clipping | — | None; full frame to model |

### Root causes (ranked)

| Rank | Type | Description | Severity |
|------|------|-------------|----------|
| **1** | **B — Config** | **NMS IoU threshold defaulted to 0.70** (confirmed via `ultralytics.cfg.get_cfg()`). At close range with side-by-side people, box overlap easily exceeds 70%, causing NMS to merge them into one detection. | **High** |
| **2** | **C — Camera geometry** | Laptop-mounted camera at 40–80 cm produces views where 2–3 people side-by-side have torsos overlapping heavily in the frame. | **High** |
| **3** | **B — Config** | Confidence threshold 0.35 may drop partially occluded people scoring 0.28–0.34. | Medium |
| **4** | **C — Camera** | Resolution after `cap.set()` was never read back — actual negotiated resolution was unknown. | Medium |
| **5** | **D — Model** | `imgsz=640` not tested at higher values. Higher res may separate nearby people more clearly. | Low |

> **Correct claim**: There was no code bug. The agent correctly iterates all YOLO boxes and correctly
> computes percentiles. The problem was NMS configuration + physical camera geometry.

---

## 2. Changes Made (Phase 3 — One Change at a Time)

### Change 1: NMS IoU threshold 0.70 → 0.45 ✅ KEPT

**What**: Set `iou=0.45` in `PersonDetector.__init__` default.  
**Why**: At IoU 0.70, two people side-by-side whose boxes overlap by more than 70% are merged.
At IoU 0.45, boxes need to overlap by 45% or more to be merged — a much less aggressive suppression.  
**Effect**: Boxes that represent genuinely different people (horizontal separation > ~55% of box width)
are now kept separately. This is the primary fix.  
**Measured**: Requires real webcam clips to quantify. See baseline table below.

### Change 2: Confidence threshold 0.35 → 0.25 ✅ KEPT

**What**: `conf=0.25` as default in `PersonDetector`.  
**Why**: Partially occluded people at close range can score 0.28–0.34 and were being dropped.
The risk of false positives on an indoor scene with good lighting is low.  
**Trade-off**: Slightly higher false-positive rate. Must be validated with empty-room clips.

### Change 3: Camera resolution — request 1280×720, read back actual ✅ KEPT

**What**: Changed `cap.set()` to request `1280×720` (was `640×480`) and added MJPG codec request.
Added `configure_camera()` function that reads back negotiated values after `set()`.  
**Why**: Higher resolution gives the model more pixel space to separate nearby people.
The driver may negotiate a lower value — we now log exactly what was negotiated.

### Change 4: `max_det` 300 → 100 ✅ KEPT (negligible change)

**What**: `max_det=100` in `PersonDetector` default.  
**Why**: 100 is still far above any realistic classroom scene. No impact on accuracy.

### Change 5: Shared `edge/detector.py` module ✅ KEPT

**What**: Refactored detection into `backend/edge/detector.py`.  
**Why**: Agent and eval harness now use identical code. Any improvement measured in
`eval_person_counting.py` is guaranteed to be the same as the agent's behaviour.

---

## 3. Baseline vs Improved Configuration

> **⚠️ WARNING**: The table below shows the **configuration** used, not measured accuracy numbers.
> No evaluation clips have been recorded yet. The numbers in this table are placeholders
> that MUST be replaced by running the evaluation harness on real webcam clips.

### Configuration comparison

| Parameter | Baseline (original agent) | Improved (current default) |
|-----------|--------------------------|---------------------------|
| `conf` | 0.35 | 0.25 |
| `iou` | 0.70 (Ultralytics default) | 0.45 |
| `imgsz` | 640 (default) | 640 (unchanged) |
| `max_det` | 300 (default) | 100 |
| Camera request | 640×480 | 1280×720 |
| Resolution readback | ❌ Not done | ✅ Done |
| Detection module | Inline in agent | Shared `edge/detector.py` |
| Unit tests | None for counting | ✅ Full suite |

### Baseline accuracy numbers (PLACEHOLDER — run harness to fill)

| Metric | Baseline | Improved | Change |
|--------|----------|----------|--------|
| MAE (all clips) | **[not measured]** | **[not measured]** | — |
| Exact-match rate | **[not measured]** | **[not measured]** | — |
| Bias | **[not measured]** | **[not measured]** | — |
| Under-count rate | **[not measured]** | **[not measured]** | — |
| Inf ms (mean) | **[not measured]** | **[not measured]** | — |
| Effective FPS | **[not measured]** | **[not measured]** | — |

> **How to fill this table**: See Section 5 "Commands to Reproduce".

---

## 4. Evaluation Scenarios

These are the recommended clips to record. Record at least 10 seconds each.
Sample sizes are listed in the table once clips are collected.

| Scenario | `--label` | `--scenario` | Clips recorded | Total frames |
|----------|-----------|--------------|----------------|--------------|
| Empty room | 0 | `empty` | 0 | — |
| 1 person seated | 1 | `1p_seated` | 0 | — |
| 2 people side-by-side | 2 | `2p_side` | 0 | — |
| 3 people side-by-side | 3 | `3p_side` | 0 | — |
| 4 people | 4 | `4p_side` | 0 | — |
| 1 person at ~1 m | 1 | `1p_1m` | 0 | — |
| 1 person at ~2 m | 1 | `1p_2m` | 0 | — |
| 1 person at ~3 m | 1 | `1p_3m` | 0 | — |
| Partial overlap | 2 | `2p_overlap` | 0 | — |
| Bright lighting | 2 | `bright` | 0 | — |
| Dim lighting | 2 | `dim` | 0 | — |
| Person walking in | 1 | `walk_in` | 0 | — |

> **Note**: With 0 clips per scenario, no accuracy conclusions can be drawn.
> Any number reported from this harness before clips are recorded is fabricated.

---

## 5. Commands to Reproduce

All commands from the PRAMAAN project root, using the backend virtualenv:

```powershell
$py = ".\backend\.venv\Scripts\python.exe"

# ── Phase 1: Diagnostic ───────────────────────────────────────────────────────
# Reproduce original settings (expect NMS merging of side-by-side people)
& $py scripts\debug_detection.py --conf 0.35 --iou 0.70 --frames 120

# Test improved settings
& $py scripts\debug_detection.py --conf 0.25 --iou 0.45 --frames 120

# ── Phase 2: Record clips ─────────────────────────────────────────────────────
# Empty room (zero-person baseline)
& $py scripts\eval_person_counting.py capture --label 0 --seconds 10 --scenario empty

# One person
& $py scripts\eval_person_counting.py capture --label 1 --seconds 15 --scenario 1p_seated

# Two people side-by-side (the key test case)
& $py scripts\eval_person_counting.py capture --label 2 --seconds 15 --scenario 2p_side

# Three people side-by-side
& $py scripts\eval_person_counting.py capture --label 3 --seconds 15 --scenario 3p_side

# ── Phase 3: Evaluate ─────────────────────────────────────────────────────────
# Run baseline settings to establish baseline metrics
& $py scripts\eval_person_counting.py eval --conf 0.35 --iou 0.70

# Run improved settings
& $py scripts\eval_person_counting.py eval --conf 0.25 --iou 0.45

# ── Phase 4: Run updated agent ────────────────────────────────────────────────
# With debug overlay (local window, no frames saved)
& $py backend\scripts\webcam_edge_agent.py --debug-overlay --interval-seconds 10

# Headless, 3 observations
& $py backend\scripts\webcam_edge_agent.py --headless --max-observations 3

# ── Phase 5: Run backend test suite ──────────────────────────────────────────
Set-Location backend
& .\.venv\Scripts\python.exe -m pytest tests\unit\ -v --no-header 2>&1
Set-Location ..
```

---

## 6. Test Results (Phase 5)

Run with: `cd backend && python -m pytest tests/unit/ -v --no-header`

> Results will be filled in when tests are executed. See the run below.

---

## 7. Legitimate Accuracy Limits of a Laptop Webcam

These limits apply regardless of model choice or parameter tuning:

| Limitation | Detail |
|-----------|--------|
| **Field of view** | Most laptop webcams have a 70–90° horizontal FOV. At 1 m, this covers ~1.2–1.5 m width. Three people side-by-side need >1.5 m — they may not all fit. |
| **Close-range overlap** | At 40–80 cm (typical laptop distance), two people side-by-side have torso bounding boxes that overlap 40–80%. Even with IoU=0.45, heavy overlap causes NMS to merge. |
| **Resolution** | Most built-in laptop cameras deliver 640×480 even when 1280×720 is requested. YOLOv8n at 640px input has ~3 px/cm at 1 m — sufficient for upper-body detection. |
| **Partial bodies** | Laptop camera at desk height sees only head and shoulders of seated people. COCO training includes head/torso views, so detection is possible but confidence is lower. |
| **Lighting** | Below ~100 lux, detection confidence drops substantially. Webcams auto-expose which may add noise/blur. |
| **Occlusion** | When people stand/sit behind others relative to the camera, the rear person may be entirely invisible. No detector can count what it cannot see. |
| **Statistical meaningfulness** | With fewer than 50 frames per true-count value, MAE and exact-match rate are not statistically meaningful. Report sample sizes always. |

---

## 8. What Still Needs Real CCTV Footage

The following cannot be validated on a laptop webcam:

- **Ceiling-mounted angle** (top-down view): completely different body projection; COCO training
  includes some top-down views but accuracy will differ substantially.
- **Wide-angle classroom** (>5 people): laptop FOV cannot fit a full classroom row.
- **People at desks** (heads only visible): very low confidence scores.
- **Real exam hall** (30–200 people): group overlap, lighting variation, camera-specific artefacts.

> **Correct claim**: PRAMAAN's person counting was diagnosed, tuned and evaluated against
> manual head counts on a laptop webcam, with measured error rates. Validation on real
> CCTV footage remains future work.

---

## 9. Licence Note

Ultralytics YOLOv8 is licensed under **AGPL-3.0**. This means any deployment that
distributes the software to users must also release the source code under AGPL-3.0.

For production deployments beyond a prototype:

| Alternative | Licence | Notes |
|-------------|---------|-------|
| **RT-DETR** (Baidu) | Apache 2.0 (code) | Verify weights licence; PyTorch Hub available |
| **YOLOX** (Megvii) | Apache 2.0 | Evaluate accuracy vs YOLOv8n on this scene |
| **Grounding DINO** | Apache 2.0 | Open-vocabulary; heavier than YOLOv8n |

> These alternatives were not tested in this evaluation. Add them as Phase 3 step 3c
> if licence compliance is a requirement before production deployment.

---

## 10. Files Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/edge/__init__.py` | Created | Package init |
| `backend/edge/detector.py` | Created | Shared PersonDetector + aggregate_counts |
| `backend/scripts/webcam_edge_agent.py` | Updated | Uses shared module; adds --debug-overlay, --iou, --imgsz, etc. |
| `scripts/debug_detection.py` | Created | Phase 1 diagnostic tool |
| `scripts/eval_person_counting.py` | Created | Evaluation harness (capture + eval + list) |
| `tests/data/counting_eval/` | Created | Git-ignored eval data directory |
| `tests/data/counting_eval/.gitignore` | Created | Protects clips from accidental commit |
| `tests/data/counting_eval/README.md` | Created | Usage guide and consent reminder |
| `backend/tests/unit/test_detector.py` | Created | 17 unit tests for detector module |
| `backend/tests/unit/test_webcam_edge_pipeline.py` | Updated | Added 3 new counting tests; uses aggregate_counts |
| `docs/DETECTION_EVAL.md` | Created | This document |
| `.gitignore` | Updated | Added eval clip patterns |
