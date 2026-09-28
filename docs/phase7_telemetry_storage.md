# NWIS Phase 7: Real-Time Telemetry Storage & Retention Architecture

> **OPERATIONAL ADVISORY**  
> Real-time drilling telemetry storage provides historical operational replay, anomaly forensic analysis, and ML feature backtesting. NWIS telemetry ingestion runs strictly advisory workflows and never performs autonomous rig actions.

---

## 1. Storage & Volume Characteristics

During active drilling operations, surface and downhole instruments stream telemetry at 1 Hz to 10 Hz frequency:
- **Parameters per Record**: Bit Depth (MD), Hole Depth, ROP, WOB, RPM, Surface Torque, SPP, Flow In, Flow Out, Total Gas, Pit Volume, Mud Weight In/Out.
- **Data Volume per Well**:
  - At $1.0\text{ Hz}$: $\approx 86,400\text{ records/day}$ ($\approx 35\text{ MB/day}$).
  - A 30-day drilling campaign produces $\approx 2.6\text{M records}$ ($\approx 1.0\text{ GB}$).
- **Concurrent Rigs**: An asset monitoring 20 active rigs simultaneously ingests $\approx 1.7\text{M records/day}$.

---

## 2. Partitioning Strategy

To maintain sub-second query latency for both latest-value reads and depth-interval queries without requiring proprietary extensions:

### A. Range Partitioning by Timestamp (Standard PostgreSQL)
```sql
CREATE TABLE telemetry_records (
    id BIGSERIAL,
    well_id VARCHAR(32) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    depth_md DOUBLE PRECISION NOT NULL,
    rop DOUBLE PRECISION,
    wob DOUBLE PRECISION,
    rpm DOUBLE PRECISION,
    torque DOUBLE PRECISION,
    spp DOUBLE PRECISION,
    mud_flow_in DOUBLE PRECISION,
    mud_flow_out DOUBLE PRECISION,
    gas DOUBLE PRECISION,
    pump_pressure DOUBLE PRECISION,
    hookload DOUBLE PRECISION,
    source VARCHAR(64) DEFAULT 'eRTMAC',
    quality_status VARCHAR(32) DEFAULT 'GOOD',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Monthly partition examples:
CREATE TABLE telemetry_records_y2026m09 PARTITION OF telemetry_records
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

CREATE TABLE telemetry_records_y2026m10 PARTITION OF telemetry_records
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
```

### B. Indexing Strategy per Partition
Each partition automatically inherits high-efficiency composite indexes:
1. `CREATE INDEX idx_telemetry_well_time ON telemetry_records (well_id, timestamp DESC);`
   - *Query Pattern*: Accelerated fetching of recent $N$ telemetry records for dashboard polling or WebSocket initial sync.
2. `CREATE INDEX idx_telemetry_well_depth ON telemetry_records (well_id, depth_md);`
   - *Query Pattern*: Subsurface interval correlation (e.g. drilling through Limestone formation between $1100\text{ m}$ and $1250\text{ m}$).
3. `CREATE INDEX idx_telemetry_time ON telemetry_records (timestamp DESC);`
   - *Query Pattern*: Global fleet-wide health monitors.

---

## 3. Retention & Tiering Lifecycle

1. **Hot Tier (Memory Ring Buffer + Latest State Table)**:
   - High-speed in-memory ring buffer ($N=200$) in `LiveWellState` for real-time rolling calculations ($\mu$, $\sigma$, ROC, flow imbalance).
   - Authoritative latest state table `well_live_state` stores the single latest record per well for backend restart recovery.
2. **Warm Tier (PostgreSQL Active Partitions, 0 to 90 Days)**:
   - Uncompressed, fully indexed partitions for recent operational history, alert correlation, and Copilot queries.
3. **Cold Tier (Archive Partitions / Compressed Parquet, > 90 Days)**:
   - Partitions older than 90 days are exported to compressed Parquet files in object storage (`s3://nwis-telemetry-archive/`) and detached from PostgreSQL to conserve primary database IOPS.
