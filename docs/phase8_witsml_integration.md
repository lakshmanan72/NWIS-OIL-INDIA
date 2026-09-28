# NWIS PHASE 8 — WITSML INTEGRATION SPECIFICATION
## WITSML 1.3.1.1 / 1.4.1.1 Log Query & Telemetry Adapter

---

## 1. Overview & Standard Architecture

The **WITSML (Wellsite Information Transfer Standard Markup Language)** integration module equips NWIS with the capability to interface with industry-standard WITSML servers (Energistics WITSML 1.3.1.1 and 1.4.1.1 XML Store Web Services).

---

## 2. Supported Log Queries

NWIS queries WITSML servers through `WMLS_GetFromStore` with standard XML queries:
- **`well` / `wellbore` Discovery**: Locates active rig wells and associated wellbores.
- **`log` Metadata & Curve Definitions**: Identifies index type (`measured depth` or `date time`), mnemonic lists, and measurement units.
- **`logData` Range Retrieval**:
  - Time-indexed queries: `startIndex` / `endIndex` in ISO-8601 UTC.
  - Depth-indexed queries: `startIndex` / `endIndex` in meters or feet.

---

## 3. Mnemonic Mapping Matrix

WITSML log data streams use varying vendor curve mnemonics. The parser normalizes these into the canonical NWIS schema:

| Canonical NWIS Field | WITSML Mnemonics Recognized | Primary Unit | Canonical Range |
| :--- | :--- | :--- | :--- |
| `depth_md` | `DEPT`, `MD`, `DEPTH`, `HOLE_DEPTH` | m / ft | `>= 0.0` |
| `rop_m_hr` | `ROP`, `ROPA`, `ROP_AVG`, `DIF_RATE` | m/h / ft/h | `[0.0, 300.0]` |
| `wob_klbf` | `WOB`, `WOBA`, `SWOB`, `WTBR` | klbf / kN | `[0.0, 150.0]` |
| `rpm` | `RPM`, `CRPM`, `TORQ_RPM`, `SR_RPM` | rpm | `[0.0, 350.0]` |
| `torque_kftlb` | `TORQ`, `STOR`, `TRQ`, `TORQ_SURF` | kft-lb / kNm | `[0.0, 100.0]` |
| `standpipe_pressure_psi` | `SPP`, `STPP`, `SPPA`, `PUMP_PRESS` | psi / kPa | `[0.0, 10000.0]` |
| `mud_flow_in_lpm` | `FLOWIN`, `FLOW_IN`, `MFI`, `PUMP_FLOW`| L/min / gpm | `[0.0, 6000.0]` |
| `mud_flow_out_lpm` | `FLOWOUT`, `FLOW_OUT`, `MFO`, `FLWO` | L/min / % | `[0.0, 6000.0]` |
| `gas_units` | `GAS`, `TGAS`, `GAS_TOT`, `TOT_GAS` | units / ppm | `[0.0, 10000.0]` |
| `mud_weight_ppg` | `MW`, `MWIN`, `MUD_WT`, `DENS` | ppg / sg | `[6.0, 22.0]` |
| `hookload` | `HKLD`, `HKLA`, `HOOKLOAD` | klbf / kN | `[0.0, 1500.0]` |

Units are dynamically converted to SI/Oilfield standard (e.g. feet to meters, kPa to psi, kNm to kft-lb) during parse phase.

---

## 4. Configuration & Credentials

All settings are environment driven:
```env
WITSML_ENABLED=false
WITSML_URL=https://witsml.upstream-rig.example.com/witsml/services/store
WITSML_USERNAME=nwis_ingest
WITSML_PASSWORD=
WITSML_WELL_ID=WELL-000050
WITSML_WELLBORE_ID=WB-01
```

If `WITSML_ENABLED=false` or credentials are unset, the integration status remains `DISABLED`, preventing unauthorized network activity.
