import React, { useState, useEffect } from 'react';
import {
  Compass,
  MapPin,
  Layers,
  Activity,
  Flame,
  AlertTriangle,
  FileText,
  ShieldAlert,
  ArrowLeft,
  Search,
  ExternalLink,
  Sliders,
  CheckCircle2,
  Clock,
  Sparkles,
  Info,
  Radio,
  Zap,
} from 'lucide-react';
import AiRiskPredictionPanel from '../components/AiRiskPredictionPanel';

export default function WellIntelligencePage({ wellId, onNavigate }) {
  const [activeTab, setActiveTab] = useState('ai-risk');
  const [well, setWell] = useState(null);
  const [isLoadingWell, setIsLoadingWell] = useState(true);
  const [wellError, setWellError] = useState(null);

  // Correlation Interactive Inputs
  const [currentDepth, setCurrentDepth] = useState(2500);
  const [currentFormation, setCurrentFormation] = useState('');
  const [radiusKm, setRadiusKm] = useState(25);
  const [depthWindowM, setDepthWindowM] = useState(200);

  // Data states
  const [offsetIntel, setOffsetIntel] = useState(null);
  const [isLoadingIntel, setIsLoadingIntel] = useState(false);
  const [geology, setGeology] = useState([]);
  const [formations, setFormations] = useState([]);
  const [drilling, setDrilling] = useState([]);
  const [mudLogs, setMudLogs] = useState([]);
  const [events, setEvents] = useState([]);
  const [risks, setRisks] = useState([]);
  const [completion, setCompletion] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [liveData, setLiveData] = useState(null);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [isLoadingLive, setIsLoadingLive] = useState(false);

  // Fetch Core Well Overview
  useEffect(() => {
    async function fetchWellData() {
      setIsLoadingWell(true);
      setWellError(null);
      try {
        const wid = wellId || 'WELL-000001';
        const res = await fetch(`/api/wells/${encodeURIComponent(wid)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Well not found`);
        const data = await res.json();
        setWell(data);
        if (data.total_depth) {
          setCurrentDepth(Math.round(data.total_depth * 0.7));
        }
      } catch (err) {
        console.error('Error fetching canonical well:', err);
        setWellError(err.message);
      } finally {
        setIsLoadingWell(false);
      }
    }

    fetchWellData();
  }, [wellId]);

  // Fetch Offset Intelligence
  useEffect(() => {
    if (!well) return;
    const wid = well.well_id;

    async function fetchOffsetIntelligence() {
      setIsLoadingIntel(true);
      try {
        let url = `/api/wells/${encodeURIComponent(wid)}/offset-intelligence?radius_km=${radiusKm}&depth_window_m=${depthWindowM}&current_depth=${currentDepth}`;
        if (currentFormation) {
          url += `&current_formation=${encodeURIComponent(currentFormation)}`;
        }
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setOffsetIntel(data);
        }
      } catch (err) {
        console.error('Error fetching offset intelligence:', err);
      } finally {
        setIsLoadingIntel(false);
      }
    }

    fetchOffsetIntelligence();
  }, [well, currentDepth, currentFormation, radiusKm, depthWindowM]);

  // Lazy load tab data
  useEffect(() => {
    if (!well) return;
    const wid = well.well_id;

    if (activeTab === 'geology' && geology.length === 0) {
      fetch(`/api/wells/${encodeURIComponent(wid)}/geology`)
        .then((r) => r.ok && r.json())
        .then((d) => setGeology(d.intervals || []));
      fetch(`/api/wells/${encodeURIComponent(wid)}/formations`)
        .then((r) => r.ok && r.json())
        .then((d) => setFormations(d.formations || []));
    } else if (activeTab === 'drilling' && drilling.length === 0) {
      fetch(`/api/wells/${encodeURIComponent(wid)}/drilling`)
        .then((r) => r.ok && r.json())
        .then((d) => setDrilling(d.records || []));
      fetch(`/api/wells/${encodeURIComponent(wid)}/mud-logging?limit=50`)
        .then((r) => r.ok && r.json())
        .then((d) => setMudLogs(d.records || []));
    } else if (activeTab === 'events' && events.length === 0) {
      fetch(`/api/wells/${encodeURIComponent(wid)}/events`)
        .then((r) => r.ok && r.json())
        .then((d) => setEvents(d.events || []));
    } else if (activeTab === 'risk' && risks.length === 0) {
      fetch(`/api/wells/${encodeURIComponent(wid)}/risks`)
        .then((r) => r.ok && r.json())
        .then((d) => setRisks(d.recommendations || []));
    } else if (activeTab === 'completion' && !completion) {
      fetch(`/api/wells/${encodeURIComponent(wid)}/completion`)
        .then((r) => r.ok && r.json())
        .then((d) => setCompletion(d.completion));
      fetch(`/api/wells/${encodeURIComponent(wid)}/documents`)
        .then((r) => r.ok && r.json())
        .then((d) => setDocuments(d.documents || []));
    }
  }, [activeTab, well]);

  // Live polling effect when live tab active
  useEffect(() => {
    if (!well || activeTab !== 'live') return;
    const wid = well.well_id;
    let isSubscribed = true;

    async function fetchLive() {
      setIsLoadingLive(true);
      try {
        const [resLatest, resAlerts] = await Promise.all([
          fetch(`/api/realtime/latest/${encodeURIComponent(wid)}`),
          fetch(`/api/realtime/alerts?well_id=${encodeURIComponent(wid)}&active_only=true`)
        ]);
        if (resLatest.ok && isSubscribed) {
          const dLatest = await resLatest.json();
          setLiveData(dLatest);
        }
        if (resAlerts.ok && isSubscribed) {
          const dAlerts = await resAlerts.json();
          setLiveAlerts(dAlerts.alerts || []);
        }
      } catch (err) {
        console.error('Error fetching live data in well intelligence:', err);
      } finally {
        if (isSubscribed) setIsLoadingLive(false);
      }
    }

    fetchLive();
    const interval = setInterval(fetchLive, 3000);
    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, [activeTab, well]);

  if (isLoadingWell) {
    return (
      <div className="intel-loading-screen">
        <div className="loading-spinner"></div>
        <span>Retrieving Canonical Well Intelligence Profile...</span>
      </div>
    );
  }

  if (wellError || !well) {
    return (
      <div className="intel-error-screen">
        <AlertTriangle size={36} />
        <h2>Well Not Found</h2>
        <p>{wellError || 'The requested well ID does not exist in canonical registry.'}</p>
        <button onClick={() => onNavigate('map')} className="back-map-btn">
          <ArrowLeft size={16} /> Return to Map
        </button>
      </div>
    );
  }

  return (
    <div className="intelligence-page">
      {/* Top Banner Navigation */}
      <div className="intel-top-bar">
        <button className="back-btn" onClick={() => onNavigate('map')}>
          <ArrowLeft size={16} />
          <span>Back to Map</span>
        </button>
        <div className="intel-title-box">
          <span className="intel-tag">CANONICAL INTELLIGENCE COCKPIT</span>
          <span className="intel-well-title">
            {well.well_name} ({well.well_id})
          </span>
        </div>
        <div className="intel-actions">
          <span className="status-pill active">{well.well_status || 'Active'}</span>
        </div>
      </div>

      <div className="intel-content-container">
        {/* ==================================================
            1. WELL OVERVIEW (Canonical Profile Card)
            ================================================== */}
        <div className="well-overview-card">
          <div className="overview-header">
            <div className="overview-title-group">
              <span className="star-icon-lg">★</span>
              <div>
                <h2>{well.well_name}</h2>
                <div className="overview-submeta">
                  <span className="font-mono text-primary">{well.well_id}</span>
                  <span>•</span>
                  <span>{well.operator}</span>
                  <span>•</span>
                  <span>{well.basin} Basin</span>
                  <span>•</span>
                  <span>{well.field} Field</span>
                </div>
              </div>
            </div>
            <div className="overview-coords-pill">
              <Compass size={16} />
              <span>
                {well.latitude.toFixed(6)}° N, {well.longitude.toFixed(6)}° E
              </span>
            </div>
          </div>

          <div className="overview-grid">
            <div className="ov-item">
              <span className="ov-lbl">Well Type</span>
              <span className="ov-val">{well.well_type || 'Exploratory'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Well Status</span>
              <span className="ov-val">{well.well_status || 'Producing'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Trajectory</span>
              <span className="ov-val">{well.trajectory_type || 'Vertical'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Total Depth (TD)</span>
              <span className="ov-val font-mono">{well.total_depth ? `${well.total_depth.toFixed(0)} m` : 'N/A'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Block Identifier</span>
              <span className="ov-val">{well.block || 'N/A'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Spud Date</span>
              <span className="ov-val">{well.spud_date || 'N/A'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Completion Date</span>
              <span className="ov-val">{well.completion_date || 'N/A'}</span>
            </div>
            <div className="ov-item">
              <span className="ov-lbl">Data Provenance</span>
              <span className="ov-val text-primary font-bold">nwis_well_locations_15108_new.csv</span>
            </div>
          </div>
        </div>

        {/* Intelligence Tab Navigation Bar */}
        <div className="intel-tabs-bar">
          <button
            className={`intel-tab-btn ${activeTab === 'live' ? 'active' : ''}`}
            onClick={() => setActiveTab('live')}
          >
            <Radio size={16} className="text-emerald-400" />
            <span>Live Telemetry & Alerts</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'ai-risk' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai-risk')}
          >
            <Sparkles size={16} className="text-cyan-400" />
            <span>AI Drilling Risk Prediction</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'offset' ? 'active' : ''}`}
            onClick={() => setActiveTab('offset')}
          >
            <ShieldAlert size={16} />
            <span>Offset Intelligence & Correlation</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'nearby' ? 'active' : ''}`}
            onClick={() => setActiveTab('nearby')}
          >
            <Compass size={16} />
            <span>Nearby Offset Wells</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'geology' ? 'active' : ''}`}
            onClick={() => setActiveTab('geology')}
          >
            <Layers size={16} />
            <span>Subsurface Geology</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'drilling' ? 'active' : ''}`}
            onClick={() => setActiveTab('drilling')}
          >
            <Activity size={16} />
            <span>Drilling & Mud Telemetry</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'events' ? 'active' : ''}`}
            onClick={() => setActiveTab('events')}
          >
            <Clock size={16} />
            <span>Institutional Memory Logs</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'risk' ? 'active' : ''}`}
            onClick={() => setActiveTab('risk')}
          >
            <Flame size={16} />
            <span>Prototype Risk Advisory</span>
          </button>
          <button
            className={`intel-tab-btn ${activeTab === 'completion' ? 'active' : ''}`}
            onClick={() => setActiveTab('completion')}
          >
            <FileText size={16} />
            <span>WCR & Documents</span>
          </button>
        </div>

        {/* ==================================================
            TAB 0: AI/ML DRILLING RISK PREDICTION (Phase 3)
            ================================================== */}
        {activeTab === 'ai-risk' && (
          <div className="intel-section">
            <AiRiskPredictionPanel
              wellId={well.well_id}
              initialDepth={currentDepth}
              maxDepth={well.total_depth || 6000}
            />
          </div>
        )}

        {/* ==================================================
            TAB 1: OFFSET WELL EVENT CORRELATION (Core Feature)
            ================================================== */}
        {activeTab === 'offset' && (
          <div className="intel-section">
            <div className="correlation-controls-panel">
              <div className="controls-header">
                <Sliders size={18} />
                <h3>Real-Time Depth & Formation Hazard Correlation</h3>
              </div>
              <p className="controls-desc">
                Simulate or set current drilling bit depth and target formation to compare historical drilling incidents across all nearby offset wells.
              </p>

              <div className="controls-row">
                <div className="ctrl-input-group">
                  <label>Current Drilling Depth (m):</label>
                  <div className="input-with-unit">
                    <input
                      type="number"
                      value={currentDepth}
                      onChange={(e) => setCurrentDepth(Number(e.target.value))}
                      step={25}
                      min={100}
                      max={7000}
                    />
                    <span className="unit-label">meters</span>
                  </div>
                </div>

                <div className="ctrl-input-group">
                  <label>Current Formation Filter:</label>
                  <input
                    type="text"
                    placeholder="e.g. Formation-A (or leave empty for all)"
                    value={currentFormation}
                    onChange={(e) => setCurrentFormation(e.target.value)}
                  />
                </div>

                <div className="ctrl-input-group">
                  <label>Offset Radius (km):</label>
                  <select value={radiusKm} onChange={(e) => setRadiusKm(Number(e.target.value))}>
                    <option value={10}>10 km</option>
                    <option value={25}>25 km (Standard)</option>
                    <option value={50}>50 km</option>
                    <option value={100}>100 km (Regional)</option>
                  </select>
                </div>

                <div className="ctrl-input-group">
                  <label>Depth Window Tolerance (± m):</label>
                  <select value={depthWindowM} onChange={(e) => setDepthWindowM(Number(e.target.value))}>
                    <option value={50}>± 50 m (Tight)</option>
                    <option value={100}>± 100 m</option>
                    <option value={200}>± 200 m (Standard)</option>
                    <option value={500}>± 500 m (Broad)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Historical Offset Intelligence Alert Box */}
            {isLoadingIntel ? (
              <div className="intel-loading-card">
                <div className="loading-spinner-sm"></div>
                <span>Scanning offset well historical events...</span>
              </div>
            ) : offsetIntel && (
              <>
                <div className="historical-alert-box">
                  <div className="alert-header-row">
                    <div className="alert-title-group">
                      <AlertTriangle className="alert-icon-warning" size={24} />
                      <div>
                        <h4>HISTORICAL OFFSET INTELLIGENCE</h4>
                        <div className="alert-summary-text">{offsetIntel.alert_summary}</div>
                      </div>
                    </div>
                    <div className="alert-badge-interval">
                      <span>Historical Event Interval:</span>
                      <strong>{offsetIntel.historical_event_interval}</strong>
                    </div>
                  </div>

                  {/* Supporting Wells Chips */}
                  {offsetIntel.supporting_wells?.length > 0 && (
                    <div className="supporting-wells-row">
                      <span className="sup-label">Supporting Offset Wells:</span>
                      <div className="sup-chips-list">
                        {offsetIntel.supporting_wells.map((swId) => (
                          <span
                            key={swId}
                            className="sup-well-chip"
                            onClick={() => onNavigate('intelligence', swId)}
                            title="Inspect offset well"
                          >
                            {swId} <ExternalLink size={12} />
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Hazard Summary Badges */}
                  {Object.keys(offsetIntel.event_matches || {}).length > 0 && (
                    <div className="hazard-badges-summary">
                      <span className="sup-label">Identified Hazards:</span>
                      {Object.entries(offsetIntel.event_matches).map(([evt, cnt]) => (
                        <span key={evt} className="hazard-badge">
                          {evt} <strong>({cnt})</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Evidence Table with Full Provenance */}
                <div className="evidence-section">
                  <div className="section-title-row">
                    <h3>Supporting Historical Event Evidence ({offsetIntel.historical_events?.length || 0})</h3>
                    <span className="provenance-pill">
                      Data Provenance: nwis_historical_drilling_events_15108.csv
                    </span>
                  </div>

                  {offsetIntel.historical_events?.length === 0 ? (
                    <div className="evidence-empty-card">
                      <CheckCircle2 size={32} color="#10b981" />
                      <h4>No Historical Hazards in Current Interval</h4>
                      <p>
                        No lost circulation, stuck pipe, or wellbore instability events were recorded in nearby wells within ±{depthWindowM}m of depth {currentDepth}m.
                      </p>
                    </div>
                  ) : (
                    <div className="events-table-wrapper">
                      <table className="nwis-data-table">
                        <thead>
                          <tr>
                            <th>Hazard Event</th>
                            <th>Offset Well</th>
                            <th>Distance</th>
                            <th>Event Depth</th>
                            <th>Depth Diff</th>
                            <th>Formation</th>
                            <th>Severity</th>
                            <th>NPT</th>
                            <th>Action Taken & Outcome</th>
                            <th>Event ID & Provenance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {offsetIntel.historical_events.map((ev) => (
                            <tr key={ev.event_id} className={ev.formation_match ? 'formation-match-row' : ''}>
                              <td>
                                <span className="hazard-type-pill">{ev.event_type}</span>
                              </td>
                              <td className="font-mono">
                                <button
                                  className="link-btn"
                                  onClick={() => onNavigate('intelligence', ev.well_id)}
                                >
                                  {ev.well_name || ev.well_id}
                                </button>
                              </td>
                              <td className="font-mono">{ev.distance_km} km</td>
                              <td className="font-mono font-bold">{ev.depth_md} m</td>
                              <td className="font-mono text-muted">±{ev.depth_difference_m} m</td>
                              <td>
                                <span className={ev.formation_match ? 'badge-match' : ''}>
                                  {ev.formation}
                                  {ev.formation_match && ' ★'}
                                </span>
                              </td>
                              <td>
                                <span className={`severity-badge ${ev.severity.toLowerCase()}`}>
                                  {ev.severity}
                                </span>
                              </td>
                              <td className="font-mono text-amber font-bold">{ev.npt_hours} hrs</td>
                              <td className="action-text-cell">
                                <div className="action-main">{ev.action_taken}</div>
                                <div className="outcome-text text-muted">{ev.outcome}</div>
                              </td>
                              <td>
                                <div className="provenance-cell">
                                  <span className="font-mono text-primary">{ev.event_id}</span>
                                  <span className="text-muted text-xs">{ev.source_document} (p.{ev.page_number})</span>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* ==================================================
            TAB 2: NEARBY OFFSET WELLS
            ================================================== */}
        {activeTab === 'nearby' && (
          <div className="intel-section">
            <div className="section-title-row">
              <h3>Nearby Offset Wells ({offsetIntel?.nearby_wells?.length || 0})</h3>
              <span className="provenance-pill">
                Source: nwis_spatial_well_relationships_15108.csv
              </span>
            </div>

            <div className="nearby-table-wrapper">
              <table className="nwis-data-table">
                <thead>
                  <tr>
                    <th>Offset Well ID</th>
                    <th>Well Name</th>
                    <th>Distance</th>
                    <th>Operator</th>
                    <th>Field</th>
                    <th>Basin</th>
                    <th>Block</th>
                    <th>Status</th>
                    <th>TD (m)</th>
                    <th>Proximity Class</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(offsetIntel?.nearby_wells || []).map((nw) => (
                    <tr key={nw.well_id}>
                      <td className="font-mono text-primary font-bold">{nw.well_id}</td>
                      <td>{nw.well_name}</td>
                      <td className="font-mono font-bold text-amber">{nw.distance_km} km</td>
                      <td>{nw.operator}</td>
                      <td>
                        {nw.field} {nw.same_field && <span className="badge-tag">Same Field</span>}
                      </td>
                      <td>
                        {nw.basin} {nw.same_basin && <span className="badge-tag">Same Basin</span>}
                      </td>
                      <td>
                        {nw.block} {nw.same_block && <span className="badge-tag">Same Block</span>}
                      </td>
                      <td>{nw.well_status || 'N/A'}</td>
                      <td className="font-mono">{nw.total_depth ? nw.total_depth.toFixed(0) : 'N/A'}</td>
                      <td>
                        <span className="badge-prox">{nw.proximity_class}</span>
                      </td>
                      <td>
                        <button
                          className="table-action-btn"
                          onClick={() => onNavigate('intelligence', nw.well_id)}
                        >
                          Inspect <ArrowLeft style={{ transform: 'rotate(180deg)' }} size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ==================================================
            TAB 3: SUBSURFACE GEOLOGY & STRATIGRAPHY
            ================================================== */}
        {activeTab === 'geology' && (
          <div className="intel-section">
            <div className="section-title-row">
              <h3>Subsurface Stratigraphy & Reservoir Intervals</h3>
              <span className="provenance-pill">
                Source: nwis_well_geology_15108.csv & nwis_formation_lithology_15108.csv
              </span>
            </div>

            {/* Depth-Oriented Stratigraphy Timeline Column */}
            <div className="stratigraphy-timeline-container">
              <h4>Depth-Oriented Geological Column</h4>
              <div className="geological-column">
                {formations.map((f, i) => (
                  <div
                    key={f.formation_id || i}
                    className="formation-stratum-box"
                    style={{ flex: Math.max(1, (f.depth_to_md - f.depth_from_md) / 100) }}
                  >
                    <div className="stratum-depth">
                      <span>{f.depth_from_md.toFixed(0)}m</span>
                      <span>{f.depth_to_md.toFixed(0)}m</span>
                    </div>
                    <div className="stratum-info">
                      <div className="stratum-name">{f.formation_name}</div>
                      <div className="stratum-meta">
                        {f.lithology} • {f.rock_type} • {f.geological_age}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Geology Intervals Table */}
            <div className="events-table-wrapper" style={{ marginTop: '24px' }}>
              <h4>Interval Reservoir & Geomechanics Log</h4>
              <table className="nwis-data-table">
                <thead>
                  <tr>
                    <th>Interval</th>
                    <th>Formation</th>
                    <th>Lithology</th>
                    <th>Top (m)</th>
                    <th>Base (m)</th>
                    <th>Porosity %</th>
                    <th>Perm (mD)</th>
                    <th>Pore Press (psi)</th>
                    <th>Frac Press (psi)</th>
                    <th>Temp (°C)</th>
                    <th>Show</th>
                    <th>Reservoir Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {geology.map((g) => (
                    <tr key={g.geology_id}>
                      <td className="font-mono">#{g.interval_no}</td>
                      <td className="font-bold">{g.formation}</td>
                      <td>{g.lithology}</td>
                      <td className="font-mono">{g.top_depth_m}</td>
                      <td className="font-mono">{g.bottom_depth_m}</td>
                      <td className="font-mono">{g.porosity_pct ? `${g.porosity_pct}%` : 'N/A'}</td>
                      <td className="font-mono">{g.permeability_md || 'N/A'}</td>
                      <td className="font-mono">{g.pore_pressure_psi || 'N/A'}</td>
                      <td className="font-mono">{g.fracture_pressure_psi || 'N/A'}</td>
                      <td className="font-mono">{g.temperature_c ? `${g.temperature_c}°C` : 'N/A'}</td>
                      <td>{g.hydrocarbon_show || 'None'}</td>
                      <td>
                        <span className={`quality-badge ${String(g.reservoir_quality).toLowerCase()}`}>
                          {g.reservoir_quality || 'Moderate'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ==================================================
            TAB 4: DRILLING & MUD TELEMETRY
            ================================================== */}
        {activeTab === 'drilling' && (
          <div className="intel-section">
            <div className="section-title-row">
              <h3>Daily Operational Drilling Parameters ({drilling.length} logs)</h3>
              <span className="provenance-pill">
                Source: nwis_daily_drilling_parameters_15108.csv
              </span>
            </div>

            {drilling.length === 0 ? (
              <div className="empty-section-card">
                <Info size={24} />
                <p>No daily operational drilling telemetry recorded for this well.</p>
              </div>
            ) : (
              <div className="events-table-wrapper">
                <table className="nwis-data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>MD (m)</th>
                      <th>TVD (m)</th>
                      <th>ROP (m/h)</th>
                      <th>WOB (klbf)</th>
                      <th>RPM</th>
                      <th>Torque (kNm)</th>
                      <th>Flow (lpm)</th>
                      <th>Pump (psi)</th>
                      <th>Mud Wt (ppg)</th>
                      <th>Loss (lph)</th>
                      <th>ECD (ppg)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drilling.map((d) => (
                      <tr key={d.drilling_record_id}>
                        <td className="font-mono text-muted">{d.record_date}</td>
                        <td className="font-mono font-bold">{d.depth_md}</td>
                        <td className="font-mono">{d.depth_tvd}</td>
                        <td className="font-mono text-primary font-bold">{d.rop_m_per_hr}</td>
                        <td className="font-mono">{d.wob_klbf}</td>
                        <td className="font-mono">{d.rpm}</td>
                        <td className="font-mono">{d.torque_knm}</td>
                        <td className="font-mono">{d.flow_rate_lpm}</td>
                        <td className="font-mono">{d.pump_pressure_psi}</td>
                        <td className="font-mono text-amber font-bold">{d.mud_weight_ppg}</td>
                        <td className="font-mono text-danger">{d.mud_loss_lph > 0 ? `${d.mud_loss_lph} L/h` : '0'}</td>
                        <td className="font-mono">{d.ecd_ppg}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Mud Logging Sensor Telemetry & Hazards */}
            <div className="section-title-row" style={{ marginTop: '36px' }}>
              <h3>Mud Logging Sensor Telemetry & Hazard Indicators ({mudLogs.length} samples)</h3>
              <span className="provenance-pill">
                Source: nwis_mud_logging_15108_wells.csv (Server-Filtered)
              </span>
            </div>

            {mudLogs.length === 0 ? (
              <div className="empty-section-card">
                <Info size={24} />
                <p>No mud logging sensor records available for this well.</p>
              </div>
            ) : (
              <div className="events-table-wrapper">
                <table className="nwis-data-table">
                  <thead>
                    <tr>
                      <th>Depth (m)</th>
                      <th>Timestamp</th>
                      <th>Mud Wt</th>
                      <th>Visc</th>
                      <th>Pit Gain/Loss</th>
                      <th>Flow %</th>
                      <th>Gas Total</th>
                      <th>Cuttings Lithology</th>
                      <th>Kick</th>
                      <th>Loss</th>
                      <th>Overpressure</th>
                      <th>Drilling Event</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mudLogs.map((m) => (
                      <tr key={m.mud_log_id}>
                        <td className="font-mono font-bold">{m.depth_m}</td>
                        <td className="font-mono text-muted text-xs">{m.timestamp}</td>
                        <td className="font-mono">{m.mud_weight_ppg} ppg</td>
                        <td className="font-mono">{m.mud_viscosity_cp} cP</td>
                        <td className="font-mono font-bold">
                          {m.pit_gain_loss_bbl > 0 ? `+${m.pit_gain_loss_bbl}` : m.pit_gain_loss_bbl} bbl
                        </td>
                        <td className="font-mono">{m.flow_out_pct}%</td>
                        <td className="font-mono font-bold text-amber">{m.gas_total_units} units</td>
                        <td>{m.lithology_observed || 'N/A'}</td>
                        <td>
                          {m.kick_indicator ? (
                            <span className="hazard-flag danger">KICK</span>
                          ) : (
                            <span className="text-muted text-xs">Normal</span>
                          )}
                        </td>
                        <td>
                          {m.loss_indicator ? (
                            <span className="hazard-flag warning">LOSS</span>
                          ) : (
                            <span className="text-muted text-xs">Normal</span>
                          )}
                        </td>
                        <td>
                          {m.overpressure_indicator ? (
                            <span className="hazard-flag purple">OVERPRESS</span>
                          ) : (
                            <span className="text-muted text-xs">Normal</span>
                          )}
                        </td>
                        <td className="text-xs">{m.drilling_event || 'Routine'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ==================================================
            TAB 5: INSTITUTIONAL MEMORY DRILLING EVENTS
            ================================================== */}
        {activeTab === 'events' && (
          <div className="intel-section">
            <div className="section-title-row">
              <h3>Institutional Memory Historical Drilling Incident Logs</h3>
              <span className="provenance-pill">
                Source: nwis_historical_drilling_events_15108.csv
              </span>
            </div>

            {events.length === 0 ? (
              <div className="empty-section-card">
                <CheckCircle2 size={32} color="#10b981" />
                <h4>No Historical Incidents Recorded for This Well</h4>
                <p>This well was drilled and completed with zero non-productive time incidents.</p>
              </div>
            ) : (
              <div className="events-table-wrapper">
                <table className="nwis-data-table">
                  <thead>
                    <tr>
                      <th>Event ID</th>
                      <th>Incident Type</th>
                      <th>Severity</th>
                      <th>Depth</th>
                      <th>Formation</th>
                      <th>NPT Hours</th>
                      <th>Description</th>
                      <th>Action Taken & Outcome</th>
                      <th>Source Document</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e) => (
                      <tr key={e.event_id}>
                        <td className="font-mono text-primary font-bold">{e.event_id}</td>
                        <td>
                          <span className="hazard-type-pill">{e.event_type}</span>
                        </td>
                        <td>
                          <span className={`severity-badge ${e.severity.toLowerCase()}`}>
                            {e.severity}
                          </span>
                        </td>
                        <td className="font-mono font-bold">{e.depth_md} m</td>
                        <td>{e.formation}</td>
                        <td className="font-mono text-amber font-bold">{e.npt_hours} hrs</td>
                        <td className="action-text-cell">{e.description}</td>
                        <td className="action-text-cell">
                          <div className="action-main">{e.action_taken}</div>
                          <div className="outcome-text text-muted">{e.outcome}</div>
                        </td>
                        <td>
                          <div className="provenance-cell">
                            <span>{e.source_document}</span>
                            <span className="text-muted text-xs">Page {e.page_number}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ==================================================
            TAB 6: PROTOTYPE RISK ADVISORY
            ================================================== */}
        {activeTab === 'risk' && (
          <div className="intel-section">
            <div className="prototype-risk-disclaimer-banner">
              <ShieldAlert size={20} />
              <div>
                <strong>PROTOTYPE RISK ANALYSIS</strong>
                <p>
                  These predictions represent preliminary research prototype modeling from the baseline NWIS dataset. They are not certified for production autonomous drilling decisions.
                </p>
              </div>
            </div>

            <div className="section-title-row" style={{ marginTop: '20px' }}>
              <h3>Hazard Event Predictions & Offset Recommendations ({risks.length})</h3>
              <span className="provenance-pill">
                Source: nwis_risk_recommendations.csv
              </span>
            </div>

            {risks.length === 0 ? (
              <div className="empty-section-card">
                <CheckCircle2 size={32} color="#10b981" />
                <h4>No Elevated Risk Forecasts</h4>
                <p>No high-probability drilling hazard events flagged for this well profile.</p>
              </div>
            ) : (
              <div className="risks-cards-grid">
                {risks.map((r) => (
                  <div key={r.prediction_id} className="risk-card">
                    <div className="risk-card-top">
                      <span className="risk-rank">Rank #{r.prediction_rank}</span>
                      <span className={`risk-level-badge ${r.risk_level.toLowerCase()}`}>
                        {r.risk_level} RISK
                      </span>
                    </div>

                    <h4 className="risk-event-title">{r.predicted_event}</h4>

                    <div className="risk-meta-grid">
                      <div>
                        <span className="lbl">Depth:</span>
                        <span className="val font-mono">{r.depth_md} m</span>
                      </div>
                      <div>
                        <span className="lbl">Formation:</span>
                        <span className="val">{r.formation}</span>
                      </div>
                      <div>
                        <span className="lbl">Risk Score:</span>
                        <span className="val font-bold text-danger">{(r.risk_score * 100).toFixed(1)}%</span>
                      </div>
                      <div>
                        <span className="lbl">Confidence:</span>
                        <span className="val font-bold text-primary">{(r.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    <div className="risk-action-box">
                      <span className="action-lbl">Recommended Action:</span>
                      <p>{r.recommended_action}</p>
                    </div>

                    <div className="risk-footer">
                      <span className="font-mono text-xs">Prediction ID: {r.prediction_id}</span>
                      {r.supporting_event_id && (
                        <span className="font-mono text-xs text-primary">
                          Event: {r.supporting_event_id}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ==================================================
            TAB 7: WCR & DOCUMENTS
            ================================================== */}
        {activeTab === 'completion' && (
          <div className="intel-section">
            <div className="section-title-row">
              <h3>Well Completion Report (WCR) Technical Handover</h3>
              <span className="provenance-pill">
                Source: nwis_well_completion_wcr_15108.csv
              </span>
            </div>

            {completion ? (
              <div className="wcr-summary-card">
                <div className="wcr-header">
                  <h4>{completion.wcr_summary || 'Well Completion Report Summary'}</h4>
                  <span className="wcr-status-tag">{completion.final_well_status || 'Completed'}</span>
                </div>

                <div className="wcr-grid">
                  <div className="wcr-col">
                    <h5>Reservoir Properties</h5>
                    <div className="wcr-field">
                      <span>Formation:</span>
                      <strong>{completion.reservoir_formation || 'N/A'}</strong>
                    </div>
                    <div className="wcr-field">
                      <span>Top / Base:</span>
                      <strong>
                        {completion.reservoir_top_depth_m}m / {completion.reservoir_bottom_depth_m}m
                      </strong>
                    </div>
                    <div className="wcr-field">
                      <span>Porosity / Perm:</span>
                      <strong>
                        {completion.porosity_pct}% / {completion.permeability_md} mD
                      </strong>
                    </div>
                    <div className="wcr-field">
                      <span>Net Pay / Gross Pay:</span>
                      <strong>
                        {completion.net_pay_m}m / {completion.gross_pay_m}m
                      </strong>
                    </div>
                  </div>

                  <div className="wcr-col">
                    <h5>Initial Production Test Rates</h5>
                    <div className="wcr-field">
                      <span>Initial Oil Rate:</span>
                      <strong>{completion.initial_oil_rate_bopd || 0} BOPD</strong>
                    </div>
                    <div className="wcr-field">
                      <span>Initial Gas Rate:</span>
                      <strong>{completion.initial_gas_rate_mscfd || 0} MSCFD</strong>
                    </div>
                    <div className="wcr-field">
                      <span>Initial Water Rate:</span>
                      <strong>{completion.initial_water_rate_bwpd || 0} BWPD</strong>
                    </div>
                    <div className="wcr-field">
                      <span>Test Duration:</span>
                      <strong>{completion.production_test_duration_hr || 0} hrs</strong>
                    </div>
                  </div>

                  <div className="wcr-col">
                    <h5>Mechanical & Completion</h5>
                    <div className="wcr-field">
                      <span>Completion Type:</span>
                      <strong>{completion.completion_type || 'Perforated'}</strong>
                    </div>
                    <div className="wcr-field">
                      <span>Casing / Tubing Size:</span>
                      <strong>
                        {completion.casing_size_in}" / {completion.production_tubing_size_in}"
                      </strong>
                    </div>
                    <div className="wcr-field">
                      <span>Perforation Interval:</span>
                      <strong>
                        {completion.perforation_top_depth_m}m – {completion.perforation_bottom_depth_m}m ({completion.perforation_interval_m}m)
                      </strong>
                    </div>
                    <div className="wcr-field">
                      <span>Artificial Lift:</span>
                      <strong>{completion.artificial_lift || 'None (Flowing)'}</strong>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-section-card">
                <Info size={24} />
                <p>No WCR technical handover record available for this well.</p>
              </div>
            )}

            {/* Document Archival Catalog */}
            <div className="section-title-row" style={{ marginTop: '36px' }}>
              <h3>Archival Document Catalog ({documents.length} files)</h3>
              <span className="provenance-pill">
                Source: nwis_document_metadata_15108.csv
              </span>
            </div>

            <div className="events-table-wrapper">
              <table className="nwis-data-table">
                <thead>
                  <tr>
                    <th>Doc ID</th>
                    <th>Document Type</th>
                    <th>Document Title</th>
                    <th>Report Date</th>
                    <th>Pages</th>
                    <th>File Path</th>
                    <th>OCR Status</th>
                    <th>Extraction</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.document_id}>
                      <td className="font-mono text-primary">{doc.document_id}</td>
                      <td>
                        <span className="badge-prox">{doc.document_type}</span>
                      </td>
                      <td className="font-bold">{doc.document_title}</td>
                      <td className="text-muted font-mono">{doc.document_date}</td>
                      <td className="font-mono">{doc.page_count}</td>
                      <td className="font-mono text-xs">{doc.source_file}</td>
                      <td>
                        <span className="status-pill active">{doc.ocr_status}</span>
                      </td>
                      <td>
                        <span className="status-pill active">{doc.extraction_status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ==================================================
            TAB 8: LIVE DRILLING TELEMETRY & ALERTS (Phase 6)
            ================================================== */}
        {activeTab === 'live' && (
          <div className="intel-section">
            <div className="section-header-box" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                  <Radio size={20} className="text-emerald-400" />
                  Real-Time Drilling Telemetry & Live Alert Engine
                </h3>
                <p className="section-desc" style={{ marginTop: '4px' }}>
                  Streaming surface & downhole sensors correlated with Phase 3.1 ML risk indicators and Phase 5.1 approved institutional memory.
                </p>
              </div>
              <button
                className="btn-primary"
                onClick={() => onNavigate('live', well.well_id)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: '#0284c7', color: '#fff', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600 }}
              >
                <span>Launch Live Operations Console</span>
                <ExternalLink size={16} />
              </button>
            </div>

            {liveData && liveData.status !== 'DISCONNECTED' && liveData.data ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '16px' }}>
                {/* Status Bar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: liveData.status === 'LIVE' || liveData.status === 'REPLAY' ? '#10b981' : '#f59e0b', display: 'inline-block' }} />
                      <strong style={{ color: '#f8fafc' }}>
                        {liveData.is_replay ? 'DEMO REPLAY' : liveData.status}
                      </strong>
                    </div>
                    <span style={{ color: '#94a3b8', fontSize: '13px' }}>
                      Provider: <strong>{liveData.provider || 'eRTMAC Engine'}</strong>
                    </span>
                    <span style={{ color: '#94a3b8', fontSize: '13px' }}>
                      Data Age: <strong>{liveData.data_age_seconds !== null && liveData.data_age_seconds !== undefined ? `${liveData.data_age_seconds.toFixed(1)}s` : 'Active'}</strong>
                    </span>
                    <span style={{ color: '#94a3b8', fontSize: '13px' }}>
                      Quality: <strong style={{ color: liveData.data_quality === 'GOOD' ? '#10b981' : '#f59e0b' }}>{liveData.data_quality || 'GOOD'}</strong>
                    </span>
                  </div>
                  {liveData.detected_anomalies && liveData.detected_anomalies.length > 0 && (
                    <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', border: '1px solid #ef4444', padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }}>
                      ⚠️ {liveData.detected_anomalies.length} Active Anomaly Signals
                    </span>
                  )}
                </div>

                {/* 8-Card Telemetry Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bit Depth</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>
                      {liveData.data.bit_depth_m !== null && liveData.data.bit_depth_m !== undefined ? liveData.data.bit_depth_m.toFixed(1) : '-'} <span style={{ fontSize: '13px', color: '#64748b' }}>m</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Hole: {liveData.data.hole_depth_m?.toFixed(1) || '-'} m</div>
                  </div>

                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Rate of Penetration</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#10b981', marginTop: '4px' }}>
                      {liveData.data.rop_m_per_hr !== null && liveData.data.rop_m_per_hr !== undefined ? liveData.data.rop_m_per_hr.toFixed(1) : '-'} <span style={{ fontSize: '13px', color: '#64748b' }}>m/hr</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Real-time drilling rate</div>
                  </div>

                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Weight on Bit (WOB)</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#f59e0b', marginTop: '4px' }}>
                      {liveData.data.wob_kn !== null && liveData.data.wob_kn !== undefined ? liveData.data.wob_kn.toFixed(1) : '-'} <span style={{ fontSize: '13px', color: '#64748b' }}>kN</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Rotary speed: {liveData.data.surface_rpm?.toFixed(0) || '-'} RPM</div>
                  </div>

                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Surface Torque</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#ec4899', marginTop: '4px' }}>
                      {liveData.data.surface_torque_kn_m !== null && liveData.data.surface_torque_kn_m !== undefined ? liveData.data.surface_torque_kn_m.toFixed(1) : '-'} <span style={{ fontSize: '13px', color: '#64748b' }}>kN·m</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Drillstring torque load</div>
                  </div>

                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Standpipe Pressure</div>
                    <div style={{ fontSize: '22px', fontWeight: 700, color: '#8b5cf6', marginTop: '4px' }}>
                      {liveData.data.standpipe_pressure_kpa !== null && liveData.data.standpipe_pressure_kpa !== undefined ? liveData.data.standpipe_pressure_kpa.toFixed(0) : '-'} <span style={{ fontSize: '13px', color: '#64748b' }}>kPa</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Circulating pressure</div>
                  </div>

                  <div style={{ background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '14px' }}>
                    <div style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Flow In / Out</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#06b6d4', marginTop: '4px' }}>
                      {liveData.data.flow_rate_in_lpm?.toFixed(0) || '-'} / {liveData.data.flow_rate_out_lpm?.toFixed(0) || '-'} <span style={{ fontSize: '12px', color: '#64748b' }}>LPM</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Mud Weight: {liveData.data.mud_weight_sg?.toFixed(2) || '-'} SG</div>
                  </div>
                </div>

                {/* Active Alerts for this Well */}
                <div style={{ background: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '16px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldAlert size={18} className="text-amber-400" />
                    Active Drilling Alerts ({liveAlerts.length})
                  </h4>
                  {liveAlerts.length === 0 ? (
                    <div style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 0' }}>
                      <CheckCircle2 size={16} />
                      <span>No active critical alerts. Operating parameters are within normal variance thresholds.</span>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {liveAlerts.map((alt) => (
                        <div key={alt.alert_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: 'rgba(30, 41, 59, 0.8)', border: alt.severity === 'CRITICAL' ? '1px solid #ef4444' : '1px solid #f59e0b', borderRadius: '6px', padding: '12px 14px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ background: alt.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b', color: '#fff', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                                {alt.severity}
                              </span>
                              <strong style={{ color: '#f8fafc', fontSize: '14px' }}>{alt.title}</strong>
                              <span style={{ color: '#94a3b8', fontSize: '12px' }}>Depth: {alt.depth_m?.toFixed(1)}m</span>
                            </div>
                            <p style={{ margin: '6px 0 0 0', color: '#cbd5e1', fontSize: '13px' }}>{alt.description}</p>
                            {alt.recommendation && (
                              <p style={{ margin: '4px 0 0 0', color: '#38bdf8', fontSize: '12px' }}>
                                💡 <strong>Advisory:</strong> {alt.recommendation}
                              </p>
                            )}
                          </div>
                          <button
                            onClick={() => onNavigate('live', well.well_id)}
                            style={{ background: 'transparent', border: '1px solid #38bdf8', color: '#38bdf8', borderRadius: '4px', padding: '4px 10px', fontSize: '12px', cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            Manage Alert →
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ padding: '48px 24px', textAlign: 'center', background: 'rgba(15, 23, 42, 0.4)', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: '8px', marginTop: '16px' }}>
                <Radio size={40} style={{ color: '#64748b', margin: '0 auto 16px auto', display: 'block' }} />
                <h4 style={{ color: '#e2e8f0', fontSize: '18px', margin: '0 0 8px 0' }}>No Active Live Telemetry Connection</h4>
                <p style={{ color: '#94a3b8', maxWidth: '480px', margin: '0 auto 20px auto', fontSize: '14px', lineHeight: 1.5 }}>
                  Telemetry stream for <strong>{well.well_id}</strong> is currently disconnected or idle. Launch Demo Replay or configure an upstream eRTMAC WITSML/OPC-UA connection.
                </p>
                <button
                  className="btn-primary"
                  onClick={() => onNavigate('live', well.well_id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 20px', background: '#0284c7', color: '#fff', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: 600 }}
                >
                  <Zap size={16} />
                  <span>Start Live Operations / Demo Replay</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
