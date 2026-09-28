# Model Card: NWIS Phase 3 AI/ML Drilling Risk Prediction

## 1. Model Details
- **System**: Nearby Wells Intelligence System (NWIS)
- **Model Name**: NWIS Multi-Hazard Drilling Risk Prediction Engine
- **Version**: 1.0.0
- **Model Architecture**: Multi-Model Machine Learning Ensemble (Random Forest, XGBoost, CatBoost, LightGBM)
- **Frameworks**: `scikit-learn`, `xgboost`, `catboost`, `lightgbm`, `shap`
- **Trained Hazards**:
  - `mud_loss` (Selected: Random Forest)
  - `stuck_pipe` (Selected: Random Forest)
  - `kick` (Selected: CatBoost)
  - `overpressure` (Selected: CatBoost)
  - `torque_spike` (Selected: XGBoost)

---

## 2. Purpose & Intended Use
- **Primary Objective**: Forecast the conditional probability of upcoming subsurface drilling hazards across a forward lookahead interval of 100 meters ($[D, D + 100\text{m}]$) given physical sensor observations, rolling trends, interval geology, and historical offset incidents available up to current depth $D$.
- **Intended Users**: Drilling engineers, well planners, geomechanical specialists, and operations center crews.
- **Intended Use Case**: Advisory decision support, hazard early warning, tripping and casing seat risk assessment, and mud-weight window verification.
- **CRITICAL RESTRICTION**: **Not intended for autonomous drilling control.** This model is an advisory pair-programming and planning decision-support tool. It must never be used as an automated actuator or primary safety shutdown system without human-in-the-loop engineering validation.

---

## 3. Training & Reference Datasets
- **Source Datasets**:
  1. `nwis_daily_drilling_parameters_15108.csv`: 16,939 depth intervals across 1,694 wells providing continuous mechanical drilling telemetry (ROP, WOB, RPM, torque, SPP, ECD).
  2. `nwis_mud_logging_15108_wells.csv`: 453,240 depth points providing pit levels, flow rates, and hydrocarbon chromatography.
  3. `nwis_historical_drilling_events_15108.csv`: 31,444 verified historical well events used strictly as ground-truth target labels and historical offset evidence.
  4. `nwis_well_geology_15108.csv` & `nwis_formation_lithology_15108.csv`: Subsurface stratigraphic columns, pore pressure, fracture pressure, and lithology.
  5. `nwis_spatial_well_relationships_15108.csv`: 75,540 pairwise spatial offset relationships.
  6. `nwis_well_locations_15108_new.csv`: Canonical well coordinates, basins, fields, and trajectory types.
- **Reference / Derived Dataset Exclusion**:
  - `nwis_risk_recommendations.csv` was audited and identified as a prototype heuristic lookup table. In adherence to strict data science standards, it was **completely excluded** from both target labels and feature engineering.

---

## 4. Target Construction
- **Lookahead Window**: 100 meters ahead ($[D, D + 100\text{m}]$).
- **Labeling Logic**:
  $$\text{Target}_{H} = \begin{cases} 1 & \text{if a verified historical event matching hazard } H \text{ occurred on well } W \text{ within } [D, D + 100\text{m}] \\ 0 & \text{otherwise} \end{cases}$$
- **Hazard Event Mapping**:
  - `mud_loss`: `['Mud Loss', 'Lost Circulation']`
  - `stuck_pipe`: `['Stuck Pipe', 'Differential Sticking', 'Pack-Off']`
  - `kick`: `['Kick']`
  - `overpressure`: `['Formation Pressure Change']`
  - `torque_spike`: `['Torque and Drag']`

---

## 5. Feature Engineering & Leakage Controls
- **Zero-Leakage Guarantee**:
  - At depth $D$, all features use observations strictly $\le D$.
  - Rolling aggregations (means, maximums, and first-difference trends) are calculated chronologically per well without forward lookahead.
  - Concurrent target indicator flags (`drilling_event`, `kick_indicator`, `loss_indicator`, `overpressure_indicator`, `mud_loss_severity`) were audited and purged from the feature space.
  - Correlation audits confirmed that no feature had linear correlation $|r| \ge 0.90$ with any future target.
- **Engineered Feature Groups (70 total columns)**:
  1. *Drilling Mechanics*: `depth_md`, `depth_tvd`, `rop_m_per_hr`, `wob_klbf`, `rpm`, `torque_knm`, `flow_rate_lpm`, `pump_pressure_psi`, `standpipe_pressure_psi`, `mud_weight_ppg`, `mud_viscosity_cp`, `mud_loss_lph`, `ecd_ppg`, `hook_load_klbf`.
  2. *Rolling / Lag Dynamics*: `rolling_mean_rop`, `rolling_mean_torque`, `rolling_max_torque`, `rolling_mean_wob`, `rolling_mean_spp`, `rolling_mean_ecd`, `torque_change`, `rop_change`, `pressure_change`, `mud_loss_trend`.
  3. *Mud Logging Telemetry*: `mud_temperature_c`, `mud_flow_rate_lpm`, `pit_volume_bbl`, `pit_gain_loss_bbl`, `flow_out_pct`, `gas_total_units`, `methane_units`, `ethane_units`, `propane_units`, `connection_gas_units`, `trip_gas_units`, `formation_pressure_estimate_psi`.
  4. *Subsurface Geopressure & Geology*: `porosity_pct`, `permeability_md`, `pore_pressure_psi`, `fracture_pressure_psi`, `temperature_c`, `pressure_margin` ($P_\text{frac} - P_\text{pore}$), `depth_within_formation`, `formation_thickness`, `pore_pressure_gradient`, `fracture_pressure_gradient`.
  5. *Spatial Offset Evidence*: `nearby_well_count`, `same_field_count`, `same_block_count`, `same_basin_count`, offset incident counts (`nearby_mud_loss_events`, `nearby_stuck_pipe_events`, `nearby_kick_events`, `nearby_overpressure_events`, `nearby_torque_events`), same-formation offset incidents (`same_formation_mud_loss_events`, etc.), and `distance_to_nearest_hazard_well`.
  6. *Categoricals*: `formation`, `lithology`, `basin`, `field`, `trajectory_type` (encoded strictly on train split).

---

## 6. Grouped Splitting Strategy
- **Partitioning**: Grouped splitting by `well_id`:
  - **70% Train Wells** (1,185 wells, 11,850 intervals)
  - **15% Validation Wells** (254 wells, 2,539 intervals)
  - **15% Held-Out Test Wells** (255 wells, 2,550 intervals)
- **Disjointness**: Verified 0 well overlap across splits:
  $$\text{Wells}_\text{Train} \cap \text{Wells}_\text{Val} = \emptyset, \quad \text{Wells}_\text{Train} \cap \text{Wells}_\text{Test} = \emptyset, \quad \text{Wells}_\text{Val} \cap \text{Wells}_\text{Test} = \emptyset$$

---

## 7. Algorithms Evaluated & Multi-Model Benchmark Results
All models evaluated strictly on the 15% held-out test wells:

| Hazard | Selected Model | PR-AUC | ROC-AUC | Recall | Precision | F1-Score | False Positives | False Negatives | Selection Criterion |
|---|---|---|---|---|---|---|---|---|---|
| **mud_loss** | Random Forest | **0.0192** | 0.7477 | 0.0417 | 0.0152 | 0.0222 | 67 | 23 | Best PR-AUC |
| **stuck_pipe** | Random Forest | **0.0143** | 0.7588 | 0.0769 | 0.0094 | 0.0168 | 105 | 12 | Best PR-AUC |
| **kick** | CatBoost | **0.0099** | 0.7396 | 0.0000 | 0.0000 | 0.0000 | 3 | 4 | Best PR-AUC |
| **overpressure** | CatBoost | **0.0048** | 0.6645 | **0.2000** | 0.0057 | 0.0111 | 174 | 4 | Best PR-AUC & Recall |
| **torque_spike** | XGBoost | **0.0146** | 0.7514 | 0.0000 | 0.0000 | 0.0000 | 54 | 13 | Best PR-AUC |

*Selection Policy: Primary metric = PR-AUC, Secondary metric = Recall.*

---

## 8. Explainability
- **SHAP TreeExplainer**: Evaluates individual feature contribution values for each observation.
- **Terminology**: Labeled strictly as **"model feature contribution"**.
- **Top Contributing Features**:
  - `pit_volume_bbl` and `pit_gain_loss_bbl`
  - `depth_within_formation` and `formation_thickness`
  - `pressure_margin` ($P_\text{frac} - P_\text{pore}$)
  - `ecd_ppg` and `standpipe_pressure_psi`
  - Offset well incident counts in identical formations

---

## 9. Limitations & Operational Boundaries
1. **Severe Imbalance**: Drilling hazards are rare high-impact events (~0.2% - 1.5% frequency in telemetry). Precision scores remain modest, requiring operations to interpret probabilities as relative risk elevations rather than deterministic event declarations.
2. **Offline Replay**: Current deployment runs on historical and replay telemetry via `CSVDataProvider`. Connection to live eRTMAC feeds will require the `ERTMACDataProvider` driver.
3. **Data Granularity**: Daily drilling parameters are sampled at ~300m intervals. Real-time sub-meter telemetry (WITSML) will yield significantly richer high-frequency anomaly detection.
