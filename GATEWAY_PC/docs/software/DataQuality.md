# ECOTAM — Data Quality Analysis (Sprint 13)

## Document metadata

- **Document ID:** ECOTAM-SW-DATA-QUALITY-001
- **Status:** Implemented; pending validation against the user's actual InfluxDB instance
- **Version:** 1.0
- **Sprint:** 13
- **Scope:** PC Gateway / InfluxDB OSS 2.x
- **Dependencies:** Sprint 12 `ecotam_history.py`, Sprint 11 persistence architecture

## 1. Purpose

Provide transparent, read-only diagnostics for ECOTAM telemetry data, including missing measurements, irregular time intervals, duplicate/regressing sequence identifiers, and basic numeric sanity checks. Results are heuristics, not proofs of RF delivery, sensor faults, or physical-system behavior.

## 2. Scope

Includes historical data quality, per-session summaries, a gateway health status panel, and CSV event report export. The analysis works on simulated PC telemetry and legacy data. It does not change ESP32 firmware, attempt remote radio control, or automatically correct data.

## 3. Definitions

- **Sample:** Numeric fields collapsed by timestamp and tag set, as returned by InfluxDB.
- **Gap:** A timestamp interval greater than 2.5 seconds between consecutive samples in a session; configured simulator cadence is approximately 1 second.
- **Missing estimate:** The larger of the timestamp-derived and sequence-derived missing counts per interval, to avoid double counting correlated evidence.
- **Duplicate sequence:** Two consecutive sampled points in a session with the same integer sequence identifier.
- **Integrity flag:** A missing, illegible, or out-of-broad-range numeric field.
- **Approximate session:** A legacy Sprint 11 session inferred from gaps or sequence resets, because no `session_id` was written.
- **Estimated index:** An informal indicator: `(samples without flagged conditions) / (observed samples + estimated missing samples) * 100`.

## 4. Design Goals

1. Read-only, reproducible queries against the InfluxDB v2 Flux API.
2. Preserve the Sprint 11–12 gateway and dashboards.
3. Avoid misleading detection caused by averaging, aggregation, or imputation.
4. Never expose or persist the InfluxDB API token in API responses, browser storage, logs, or CSV exports.
5. Bound query volume and display payload sizes.
6. Clearly distinguish simulator assumptions from real measurements.

## 5. Model

### API endpoints

- `GET /qualidade`: quality dashboard.
- `GET /qualidade.js`: dashboard behavior.
- `POST /api/quality`: request `{ "period": "15m" | "1h" | "6h" | "24h" | "custom", "start"?: ISO8601, "stop"?: ISO8601 }`.
- `GET /api/status`: operational gateway counters (already available since Sprint 11).

### Query model

Uses `from(bucket) |> range() |> filter()` and `keep()` over numeric fields, **without** `aggregateWindow`. Historical graphs retain their previous aggregated query endpoint, while quality analysis uses raw values. Responses are parsed from InfluxDB's annotated CSV.

### Checks

- `campo_ausente`: required numeric field not present or not parsable as finite number.
- `faixa_basica`: field outside broad ranges (format/sanity only, not real-world calibration).
- `sequencia_ausente`: sequence is missing or not a non-negative integer.
- `sequencia_duplicada`: repeated sequential identifier.
- `sequencia_retrocesso`: identifier decreased within a session.
- `salto_sequencia`: non-consecutive increasing sequence identifier.
- `lacuna_temporal`: delta > 2.5 seconds between observations in one session.

Data is organized by the `session_id` tag when present, otherwise by inferred legacy sessions. Issues are attributed to the *later* sample in a transition. Full anomaly totals are counted, but API previews and CSV event exports are limited to 150 events. The UI explicitly labels that limitation.

## 6. Relationships

`ecotam_gateway.py` exposes the HTTP endpoint and the existing status API. `ecotam_quality.py` builds the Flux query, parses raw data using `ecotam_history`, and computes findings. `qualidade.html/js` present status, session summaries, anomaly events and a CSV export. `dashboard.css` provides shared style rules. No firmware project or InfluxDB schema migration is required.

## 7. Design Rules

- The data is synthetic by default. No physically meaningful threshold is inferred from it.
- Gaps before the first sampled point and after the last point cannot be inferred from the observed series.
- InfluxDB can merge writes with identical measurement, tags and timestamps. Some duplicate writes therefore cannot be reconstructed from the stored data.
- The 1-second cadence and 2.5-second gap threshold are settings for the current simulator; tune them after sensor integration. A stopped historical session is not necessarily a failure.
- Long unaggregated queries are deliberately rejected if they exceed ~12MB of response or 18,000 sample records; rerun for a shorter interval rather than silently sampling and overstating accuracy.
- Keep tokens in process memory only, accept InfluxDB localhost URLs only, and bind the gateway to 127.0.0.1.
- Previous operational `influx_failed` and `queue_drops` counters reset each time the gateway process restarts.

## 8. References

- [InfluxDB OSS 2 — Query data](https://docs.influxdata.com/influxdb/v2/get-started/query/)
- [InfluxDB OSS 2 — Query HTTP API](https://docs.influxdata.com/influxdb/v2/api/query/)
- `docs/software/HistoryAnalysis.md` (Sprint 12)

## Revision History

| Version | Date | Description |
|---|---|---|
| 1.0 | 2026-11-14 | Initial quality audit and gateway status integration |
