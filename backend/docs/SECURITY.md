# PRAMAAN Security & Cryptographic Integrity Specification

## 1. Threat Model & Security Posture
PRAMAAN operates in zero-trust environments where edge devices, local networks, and remote training centre infrastructure are untrusted. The system enforces cryptographic integrity, non-repudiation, strict multi-tenant access control, and defense-in-depth across all ingest and management boundaries.

---

## 2. Authentication & Cryptographic Non-Repudiation

### 2.1 Edge Device Enrollment & Ed25519 Signing
- **Enrollment (`POST /v1/device/enroll`):** Devices are authenticated during factory/commissioning enrollment using short-lived cryptographically signed enrollment tokens. The backend records the device's Ed25519 public key in Base64URL encoding (`AQEBA...`).
- **Observation Ingestion (`POST /v1/ingest/observations`):** Every minute observation is signed at the edge using the device's private Ed25519 key over a canonical JSON serialization:
  - Dates formatted strictly as UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`).
  - Fields sorted alphabetically; explicit `null` fields included to ensure bit-level deterministic equivalence.
  - Record SHA-256 hash: `record_hash = SHA256(canonical_json(minute_ts, persons_p90, feed_health, frames_used, prev_hash))`.
  - Signature verification: `PyNaCl` verifies `signature` against the device's enrolled public key over `record_hash`.

### 2.2 Tamper-Evident Hash Chains
- Each observation contains `prev_hash`, linking it to the immediate prior minute observation from that device.
- The ingestion pipeline validates that `prev_hash` strictly equals the latest committed `record_hash` in the database.
- Any discrepancy (gap, duplicate, or fork) immediately emits an immutable `INTEGRITY_CHAIN_BREAK` event and flags the stream for human investigation.

### 2.3 User Authentication & Role-Based Access Control (RBAC)
PRAMAAN uses RFC 7519 JWT Bearer tokens with strict claim validation:
- Verified against RS256 JWKS or configured HMAC secret with max 30s clock skew tolerance.
- Role taxonomy enforced strictly by the pure `Policy` layer:
  1. `national_admin`: Full read/write access across all centres, states, and global threshold settings.
  2. `state_officer`: Read/write access strictly scoped to centres within their `state_code`.
  3. `inspector`: Read/write access restricted to assigned `centre_ids`.
  4. `training_centre`: Read-only access to their own single centre, with permission to submit explanations (`POST /v1/cases/{id}/respond`).
  5. `auditor`: Global read-only access to all centres, logs, and evidence for forensic oversight.

---

## 3. Network & Infrastructure Defense

### 3.1 SSRF (Server-Side Request Forgery) Prevention
All outbound HTTP REST adapter connectors (`app/adapters/http_rest.py`) enforce DNS resolution and IP address validation:
- Resolves hostname before dispatching HTTP request.
- Blocks connection to Loopback (`127.0.0.0/8`, `::1`), Private RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), Carrier-grade NAT (`100.64.0.0/10`), Link-Local (`169.254.0.0/16`), and Cloud Metadata endpoints (`169.254.169.254`).

### 3.2 Rate Limiting
Configured per-device and per-user token buckets:
- Device Ingestion: 120 RPM per device.
- User API: 600 RPM per user.
- Evidence Presign: 30 RPM.

### 3.3 RFC 9457 Structured Errors
All API error responses follow RFC 9457 `application/problem+json`:
- Standardized fields: `type`, `title`, `status`, `detail`, `instance`, and `error_id`.
- Internal stack traces and database error internals are never leaked to callers.
