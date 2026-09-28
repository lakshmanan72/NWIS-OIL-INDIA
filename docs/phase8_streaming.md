# NWIS PHASE 8 — REAL-TIME STREAMING & TELEMETRY LIFECYCLE
## Backpressure, Queueing, Quality Verification & State Recovery

---

## 1. High-Frequency Streaming Pipeline

```
  [Raw Ingest (10-50 Hz)]
           │
           ▼
  [Payload Sanitizer & Well Resolver] ──(Unmapped)──> [Quarantine Queue (UNMATCHED_WELL)]
           │ (Canonical Well Match)
           ▼
  [Physical Validation Engine] ─────────(Invalid)───> [Rejected Metrics & Error Audit]
           │ (Valid / Suspect)
           ▼
  [Deduplication & Order Check] ────────(Duplicate)─> [Discarded Metrics Counter]
           │
           ▼
  [Bounded Queue (Max: 5000)]
           │
    ┌──────┴───────────────────────────────────────┐
    ▼                                              ▼
[Live Well State Buffer (In-Memory)]   [Async Telemetry Persistence Worker]
    │                                              │
    ▼                                              ▼
[Feature Engine (Rolling 30m/60m)]     [PostgreSQL: telemetry_records]
    │                                              │
    ▼                                              ▼
[Anomaly Engine (LIVE-XXX Tokens)]     [PostgreSQL: well_live_state Upsert]
    │
    ▼
[Live Risk Evaluation + Depth Safety]
    │
    ▼
[Alert Lifecycle Engine (AlertRepository)]
    │
    ▼
[WebSocket Broadcast Engine (1 Hz Client Feed)]
```

---

## 2. Bounded Queue & Backpressure Policy

1. **Queue Capacity**: Controlled by `TELEMETRY_QUEUE_MAX_SIZE=5000`.
2. **Backpressure Triggers**:
   - If queue reaches 80% capacity (`4000 items`), system marks stream health as `DEGRADED`.
   - If queue reaches 100% capacity (`5000 items`), system applies non-blocking drop policy: oldest uncalculated transient records are shed, recording `messages_dropped_backpressure` metrics.
   - **Crucial Rule**: Alerts, anomalies, and authoritative live state snapshots are NEVER dropped.

---

## 3. Duplicate & Out-of-Order Handling

- **Deduplication Key**: `hash(canonical_well_id + source + source_timestamp + round(depth_md, 2))`.
- **Duplicate Rule**: If key is present in the rolling 5000-point LRU cache, the packet is flagged as `DUPLICATE` and discarded from database insert.
- **Out-of-Order Arrivals**:
  - Telemetry arriving with source timestamp older than current `live_state.latest_timestamp` is persisted to historical records if within 24h, but does NOT rewind the authoritative `live_state.latest_depth_md` or active bit position.

---

## 4. Depth Safety & Total Depth Protection

Before calculating Phase 3.1 ML risk indicators:
```python
if current_depth_md > canonical_well.total_depth:
    flag = "EXTRAPOLATED_BEYOND_TOTAL_DEPTH"
    # Suppress high-certainty risk extrapolations
    # Display clear warning to operations engineer
```
This guarantees no statistical hallucination occurs past drilling authorization depths.
