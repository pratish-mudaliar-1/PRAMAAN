# Verification & Implementation Report: Camera-Swap Detection and Ghost Batch Detection

This report documents the verification, gap resolution, testing, and benchmark measurements for **Camera-Swap Detection** and **Ghost Batch Detection** across the PRAMAAN backend and frontend.

---

## 1. Before vs After Checklist

| Feature Component | Status Before | Status After | Evidence & Implementation Details |
|---|---|---|---|
| **Camera-Swap: Multi-reference views** | PARTIAL | **DONE** | [`app/db/models/camera_integrity.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/db/models/camera_integrity.py), [`CameraReference`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/db/models/camera_integrity.py) table stores multiple lighting tags (`day`, `night`, `fluorescent`) with ORB/pHash descriptors. Best match chosen via [`compare_scene_against_references`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/vision/scene_compare.py). |
| **Camera-Swap: Server-side comparison** | PARTIAL | **DONE** | [`app/domain/vision/scene_compare.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/vision/scene_compare.py): Pure OpenCV/NumPy pipeline (pHash, ORB + RANSAC homography, masked SSIM, HSV histogram) downscaled to 480x360 px with privacy valid-pixel mask. |
| **Camera-Swap: Classification hierarchy** | PARTIAL | **DONE** | Strict classification order: `STABLE`, `LIGHTING_CHANGE`, `OCCLUDED`, `MOVED`, `SWAPPED`, `UNKNOWN`. |
| **Camera-Swap: Temporal state machine** | PARTIAL | **DONE** | Pure deterministic function [`evaluate_camera_state`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/camera_integrity.py) with K-of-M sustained evidence, 2 independent signals, hysteresis recovery. |
| **Camera-Swap: Change-point & UNTRUSTED isolation** | MISSING | **DONE** | Midpoint change-point estimation [`_estimate_change_point`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/camera_integrity.py). Observations marked `trust = 'UNTRUSTED'`, causing reconciliation to treat them as `NO_DATA` and idempotently resolve previous false flags. |
| **Camera-Swap: Events, Rebaseline & Maintenance** | PARTIAL | **DONE** | Scoped `camera.*` event publishing; auto `Case` + `Flag` creation; two-person rebaseline approval workflow; camera maintenance windows; on-demand challenge endpoints. |
| **Camera-Swap: Frontend UI** | PARTIAL | **DONE** | [`CameraIntegrity.tsx`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/pages/CameraIntegrity.tsx): Reference vs current redacted frame slider ([`CompareSlider`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/components/evidence/CompareSlider.tsx)), "Untrusted Since" banner with change-point, maintenance windows scheduler, on-demand challenge button, bilingual (Hindi/English). |
| **Ghost Batch: Multi-day evaluation** | PARTIAL | **DONE** | Pure deterministic domain [`app/domain/ghost_batch.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/ghost_batch.py) and service [`GhostBatchDetectionService`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/services/ghost_batch.py). |
| **Ghost Batch: Eligibility gating** | MISSING | **DONE** | Sessions require $\ge 5$ claimed and feed health $\ge 0.50$. Ineligible/offline days excluded from denominator but displayed as `NO_DATA`. |
| **Ghost Batch: Pattern rules & transparent score** | MISSING | **DONE** | M-of-N ($2/3$), L-consecutive ($2$), and CUSUM supporting signal. Transparent score components: persistence (0.35), magnitude (0.30), consistency (0.20), evidence quality (0.15). |
| **Ghost Batch: State machine with hysteresis** | PARTIAL | **DONE** | Lifecycle: `NORMAL` $\to$ `WATCH` $\to$ `SUSPECTED_GHOST` $\to$ `ESCALATED` $\to$ `RESOLVED` (3 consecutive healthy days to resolve). |
| **Ghost Batch: Late data & Camera isolation** | MISSING | **DONE** | Untrusted camera days never accuse batch of ghost attendance (`camera_integrity_explains = True`), routing issue to camera integrity rather than false attendance violation. |
| **Ghost Batch: Events, Cases & Centre rollup** | PARTIAL | **DONE** | Scoped `ghost.*` event publishing, automated Case creation with evidence pack, `Flag` with `flag_type="GHOST_BATCH_PATTERN"`, centre risk rollup endpoint `/v1/centres/{id}/ghost-batches`. |
| **Ghost Batch: Frontend UI** | PARTIAL | **DONE** | [`GhostBatches.tsx`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/pages/GhostBatches.tsx): Multi-day table visibly distinguishing `GHOST`, `HEALTHY`, `NO_DATA`, and `UNTRUSTED` days. `NO_DATA` and `UNTRUSTED` are never styled as student violations. Explicit label: "lead for review". Centre rollup card and Hindi/English strings. |

---

## 2. Files Added or Modified

### Backend
- [`backend/app/domain/ghost_batch.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/ghost_batch.py): Pure domain module for multi-day IST aggregation, eligibility gating, pattern rules, transparent scoring, and untrusted camera isolation.
- [`backend/app/domain/camera_integrity.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/camera_integrity.py): Pure domain module for camera state transitions, K-of-M, corroboration, hysteresis, and midpoint change-point estimation.
- [`backend/app/domain/vision/scene_compare.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/vision/scene_compare.py): Pure vision module with multi-reference comparison, masked SSIM, pHash, and ORB geometric homography.
- [`backend/app/services/camera_integrity.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/services/camera_integrity.py): Change-point retro-marking of observations to `UNTRUSTED`, idempotent session re-evaluation, two-person rebaseline approval, maintenance windows, on-demand challenge keyframes.
- [`backend/app/services/ghost_batch.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/services/ghost_batch.py): Multi-day evaluation service, auto-Case generation on `SUSPECTED_GHOST`, Flag generation with `flag_type="GHOST_BATCH_PATTERN"`, and centre rollup.
- [`backend/app/services/reconciliation.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/services/reconciliation.py): Updated reconciliation to filter out `UNTRUSTED` observations, treating them as `NO_DATA`, and auto-resolving attendance violation flags upon re-evaluation.
- [`backend/app/api/v1/cameras.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/api/v1/cameras.py): Endpoints for reference management, rebaseline approval workflow, maintenance windows, challenge keyframes, and re-evaluation.
- [`backend/app/api/v1/ghost.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/api/v1/ghost.py): Endpoints for batch assessment, centre rollup, and re-evaluation.
- [`backend/app/api/v1/schemas.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/app/api/v1/schemas.py): Pydantic request and response schemas for camera and ghost APIs.
- [`backend/alembic/versions/20261011_0001_camera_and_ghost_tables.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/alembic/versions/20261011_0001_camera_and_ghost_tables.py): Migration for `camera_reference`, `scene_observation`, `camera_integrity_state`, `camera_state_event`, `rebaseline_request`, `camera_maintenance_window`, `ghost_assessment`, `ghost_state_event`.
- [`backend/tests/unit/test_camera_swap_and_ghost_unit.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/test_camera_swap_and_ghost_unit.py): Unit test suite for threshold boundaries, K-of-M, IST day boundaries, and state transitions.
- [`backend/tests/unit/test_camera_ghost_property.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/test_camera_ghost_property.py): Hypothesis property tests for determinism, idempotence, monotonicity, and order-invariance.
- [`backend/tests/unit/test_camera_ghost_scenarios.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/test_camera_ghost_scenarios.py): End-to-end scenarios and adversarial tests.
- [`backend/tests/unit/benchmark_measurements.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/benchmark_measurements.py): Performance benchmark harness.

### Frontend
- [`frontend/src/api/cameras.ts`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/api/cameras.ts): API client functions for reference upload, rebaseline approvals, maintenance windows, and challenges.
- [`frontend/src/api/ghost.ts`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/api/ghost.ts): API client functions for live batch assessments, centre rollup, and re-evaluation.
- [`frontend/src/pages/CameraIntegrity.tsx`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/pages/CameraIntegrity.tsx): Redacted baseline comparison slider, "Untrusted Since" banner, maintenance windows modal, challenge trigger.
- [`frontend/src/pages/GhostBatches.tsx`](file:///c:/Users/prati/Documents/sih%2026245/frontend/src/pages/GhostBatches.tsx): Multi-day table with separate non-violation badges for `NO_DATA` and `UNTRUSTED`, centre rollup card, score breakdown.

---

## 3. Test Commands & Real Execution Results

### 1. Domain Unit Tests
Command:
```bash
python -m pytest tests/unit/test_camera_swap_and_ghost_unit.py -v
```
Result:
```text
tests/unit/test_camera_swap_and_ghost_unit.py::test_ghost_ratio_threshold_boundary PASSED [  9%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_ghost_min_claimed_attendance_boundary PASSED [ 18%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_ghost_feed_health_boundary PASSED [ 27%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_ghost_untrusted_camera_isolation PASSED [ 36%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_to_ist_date_boundaries PASSED [ 45%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_camera_state_transition_stable_to_drift_to_swap PASSED [ 54%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_camera_state_recovery_with_hysteresis PASSED [ 63%]
tests/unit/test_camera_rebaseline_transition PASSED [ 72%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_change_point_midpoint_estimation PASSED [ 81%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_corroboration_two_independent_signals PASSED [ 90%]
tests/unit/test_camera_swap_and_ghost_unit.py::test_ghost_batch_state_machine_escalation_and_recovery PASSED [100%]
============================= 11 passed in 2.39s ==============================
```

### 2. Hypothesis Property-Based Tests
Command:
```bash
python -m pytest tests/unit/test_camera_ghost_property.py -v
```
Result:
```text
tests/unit/test_camera_ghost_property.py::test_ghost_batch_deterministic_replay PASSED [ 20%]
tests/unit/test_camera_ghost_property.py::test_order_invariance_of_sessions PASSED [ 40%]
tests/unit/test_camera_ghost_property.py::test_monotonicity_more_observed_occupancy PASSED [ 60%]
tests/unit/test_camera_ghost_property.py::test_untrusted_camera_days_never_create_ghost_accusation PASSED [ 80%]
tests/unit/test_camera_ghost_property.py::test_camera_hysteresis_prevents_single_observation_flapping PASSED [100%]
============================== 5 passed in 2.67s ==============================
```

### 3. Scenario End-to-End & Adversarial Tests
Command:
```bash
python -m pytest tests/unit/test_camera_ghost_scenarios.py -v
```
Result:
```text
tests/unit/test_camera_ghost_scenarios.py::test_scenario_genuine_batch_stays_normal PASSED [  6%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_single_bad_day_does_not_escalate PASSED [ 13%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_three_consecutive_ghost_days PASSED [ 20%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_intermittent_three_of_five PASSED [ 26%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_data_gaps_do_not_trigger PASSED [ 33%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_late_attendance_data PASSED [ 40%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_abrupt_swap_and_gradual_drift PASSED [ 46%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_lights_off_evening_does_not_escalate PASSED [ 53%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_person_in_front_of_lens_occlusion PASSED [ 60%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_small_nudge_is_moved_confirmed PASSED [ 66%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_rebaseline_approval PASSED [ 73%]
tests/unit/test_camera_ghost_scenarios.py::test_scenario_swap_empty_batch_gives_integrity_case_not_ghost PASSED [ 80%]
tests/unit/test_camera_ghost_scenarios.py::test_adversarial_forged_edge_reported_similarity PASSED [ 86%]
tests/unit/test_camera_ghost_scenarios.py::test_adversarial_corrupt_or_empty_image PASSED [ 93%]
tests/unit/test_camera_ghost_scenarios.py::test_adversarial_rbac_cross_centre_isolation PASSED [100%]
============================= 15 passed in 5.90s ==============================
```

### 4. Full Backend Unit Suite
Command:
```bash
python -m pytest tests/unit -v
```
Result:
```text
============================ 206 passed in 13.43s =============================
```

### 5. Frontend Build & Linter
Commands:
```bash
npm run build
npm run lint
```
Results:
```text
✓ 2677 modules transformed.
✓ built in 1.62s (0 errors)
Found 46 warnings and 0 errors in 65 files with 116 rules.
```

---

## 4. Measured Performance Numbers

Run via [`tests/unit/benchmark_measurements.py`](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/benchmark_measurements.py) on local hardware:
- **Processor**: `AMD64 Family 26 Model 96 Stepping 0, AuthenticAMD` (16 vCPUs)
- **OS**: Windows 11 (10.0.26200)

### Keyframe Comparison Latency (480x360 px, 50 iterations)
- **p50**: **29.03 ms**
- **p95**: **40.89 ms**
- **p99**: **60.15 ms**

### Ghost Batch Detection Throughput (14-Day Evaluation Window per Batch)
- **1,000 Batches**: **0.3539 s** total $\to$ **2,825.4 batches/sec** (**0.354 ms/batch**)
- **10,000 Batches**: **3.7372 s** total $\to$ **2,675.8 batches/sec** (**0.374 ms/batch**)

---

## 5. What Is NOT Done or NOT Verified & Photos to Provide

1. **Vision Suite Room Photos**:
   - The subdirectories under `backend/tests/data/rooms/` (`cnc_lab/`, `gear_workshop/`, `machine_workshop/`) are currently empty.
   - Per the prompt instructions: **the vision test suite is under-powered** because real photos are not yet populated. No images were fabricated.
   - **Photos that need to be provided**:
     - At least 3 distinct rooms (e.g., `cnc_lab`, `gear_workshop`, `machine_workshop`).
     - For each room, provide real camera photos under:
       1. Baseline daytime lighting with empty room.
       2. Evening / low-light lighting conditions.
       3. Normal training session with students present.
       4. Physically nudged / rotated angle ($\approx 10^\circ$).
       5. Partial lens occlusion (e.g. object or hand in frame).
2. **Docker Testcontainers**:
   - Docker daemon was not running on the local host, so integration tests ran using the SQLite async in-process engine. Running against a live TimescaleDB container requires starting Docker Desktop on the machine.

---

## 6. Known Limits

1. **Initial Hypotheses**: All default thresholds ($\Delta_{\text{ghost}} = 0.20$, fused similarity $= 0.75 / 0.40$, feed health $= 0.50$) are initial hypotheses that must be calibrated during the pilot deployment.
2. **Synthetic vs Field Accuracy**: The scenario tests demonstrate that the state machines and eligibility gates function correctly as designed. They do not constitute field accuracy figures.
3. **Near-Identical Rooms**: If a camera is swapped to an identical room layout with matching furniture and whiteboards, visual similarity alone may not differentiate the rooms without active physical challenges.
4. **Dependence on Inputs**: Ghost detection depends on trustworthy claimed attendance numbers from the administrative portal and an accurate camera coverage configuration factor ($k$).
