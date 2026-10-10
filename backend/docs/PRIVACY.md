# PRAMAAN Privacy & Data Minimisation Architecture

## 1. Core Principles
PRAMAAN is designed from the ground up to verify physical training integrity **without collecting, storing, or processing personal identity information (PII)**.

1. **Zero Biometrics on Server:** Facial embeddings, iris templates, fingerprints, and unredacted facial images are never transmitted or stored on the backend.
2. **Aggregate Occupancy Only:** All trainee attendance is quantified solely as aggregate headcount metrics ($P_{90}$ headcounts per minute and batch-session totals).
3. **No Trainee Identifiers:** Trainee names, Aadhaar numbers, phone numbers, email addresses, and residential addresses are strictly barred from database tables, log messages, and API schemas.
4. **Edge Redaction:** Any evidentiary keyframes required for vision tamper-checking are blurred/redacted at the edge prior to upload.

---

## 2. PII Rejection in Ingestion & Adapters

### 2.1 CSV and External Ingestion
All data adapters (`app/adapters/csv_file.py` and `app/adapters/http_rest.py`) enforce automatic PII rejection:
- Inspects incoming column headers and JSON keys against forbidden PII tokens (`aadhaar`, `uid`, `name`, `candidate_name`, `trainee_name`, `phone`, `mobile`, `email`, `photo`, `face_feature`).
- If any forbidden column is present, the ingestion operation aborts immediately with an explanatory `PIIForbiddenError`.

### 2.2 Structured Log Scrubbing
All log output emitted via `structlog` passes through `scrub_pii_processor`:
- Replaces any detected Aadhaar patterns (`\b\d{4}\s?\d{4}\s?\d{4}\b`), phone numbers (`\b[6-9]\d{9}\b`), and email addresses with `[REDACTED_PII]`.

---

## 3. Data Retention & Lifecycle Management

| Data Category | Table / Location | Retention Policy | Storage Format |
| :--- | :--- | :--- | :--- |
| **Raw Evidence Blobs** | MinIO `pramaan-evidence` | **90 days** auto-expiry | Redacted JPEG / perceptual hash |
| **Per-Minute Observations** | `observation` (TimescaleDB) | **365 days** (compressed after 7d) | Aggregates only ($P_{90}$, health) |
| **Audit Logs & Snapshots** | `audit_log`, `flag_input_snapshot` | **7 years** immutable legal hold | JSONB inputs + model versions |
| **Cases & Events** | `case`, `case_event`, `tc_response` | **7 years** immutable audit log | Metadata + S3 object keys |
