# ECOTAM — History Analysis Component

**Document ID:** ECOTAM-SW-HISTORY-001  
**Revision:** 1.0  
**Date:** 2026-11-14  
**Status:** Implemented / Local verification  
**Owner:** ECOTAM  
**Sprint:** 12

## 1. Purpose
Provide historical, read-only telemetry exploration, session comparisons, summary statistics and CSV export from InfluxDB 2.x without making an operational radio link a prerequisite.

## 2. Scope
Computer-side data acquisition and historical analysis. Supported fields: altitude, pressure, temperature, voltage, accelerometer axes, gyroscope axes and sequence. Does not process control commands and does not modify firmware.

## 3. Definitions
- **Measurement:** `ecotam_telemetry`.
- **Bucket:** Configured InfluxDB storage container.
- **Session:** Gateway execution tagged with `session_id`; legacy data may be inferred using gaps or sequence resets.
- **Downsampling:** `aggregateWindow` mean over numeric series only.
- **Data point:** Row containing one timestamp plus available numeric fields.

## 4. Design Goals
Preserve Sprint 11 compatibility; minimize new dependencies; keep secrets in volatile memory; constrain local HTTP and query ranges; isolate history logic in a dedicated Python module; make filtered CSV analysis repeatable.

## 5. Model
`ecotam_gateway.py` records each sample using the existing Influx line protocol; it adds a process-scoped `session_id` tag. `ecotam_history.py` constructs fixed-template Flux queries with validated dates and JSON-escaped bucket names. The query reads only whitelisted numeric fields via `POST /api/v2/query` and parses Influx annotated CSV. Results are grouped by timestamp + tags, then by persisted session identifiers or legacy inference. `historico.js` renders the filtered selected field and statistics for two sessions, and exports selected rows as CSV.

Periods of up to 31 days are allowed. To avoid excessive client memory, large ranges use adaptive mean aggregation before transmission. Statistics are based on the returned points, not necessarily on all raw Influx samples. An upper bound on returned bytes and logical rows limits memory use.

## 6. Relationships
```text
Simulator or RX serial
        ↓
   Gateway (CSV + InfluxDB write)
        ↓
 InfluxDB OSS 2.x (telemetry + session tags)
        ↓
 History reader /api/v2/query
        ↓
 Local dashboard /historico (filters, A/B, statistics, CSV)
```

## 7. Design Rules
- Never store or display API tokens in log files, generated CSV or browser storage.
- Never accept arbitrary Flux from the web UI.
- Use only `127.0.0.1` HTTP transport for the local gateway and InfluxDB.
- Only generate aggregate means for numeric whitelisted fields.
- Preserve original telemetry payload format and firmware.
- Label legacy session inference as approximate.
- Treat all presently generated telemetry as simulated.
- A token must have bucket-scoped read permission to query and write permission to ingest.

## 8. References
- https://docs.influxdata.com/influxdb/v2/get-started/query/
- https://docs.influxdata.com/influxdb/v2/api/query/
- Sprint 11 gateway implementation / internal ECOTAM source.

## Revision History
| Revision | Date | Notes |
|---|---|---|
| 1.0 | 2026-11-14 | Initial implementation, legacy compatibility, historical dashboard |
