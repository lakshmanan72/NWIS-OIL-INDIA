import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Activity,
  ShieldCheck,
  TrendingUp,
  HelpCircle,
  Cpu,
  ChevronDown,
  ChevronUp,
  Layers,
  Database,
  Info,
} from 'lucide-react';

export default function AiRiskPredictionPanel({ wellId, initialDepth = 2500, maxDepth = 6000 }) {
  const [depth, setDepth] = useState(initialDepth);
  const [prediction, setPrediction] = useState(null);
  const [benchmark, setBenchmark] = useState([]);
  const [selectionReport, setSelectionReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showBenchmark, setShowBenchmark] = useState(false);

  // Sync with initial depth when provided
  useEffect(() => {
    if (initialDepth) {
      setDepth(initialDepth);
    }
  }, [initialDepth]);

  // Fetch ML Prediction
  const fetchPrediction = async (targetDepth) => {
    if (!wellId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/prediction/risk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          well_id: wellId,
          depth_md: parseFloat(targetDepth) || 2500,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      console.error('Error fetching AI risk prediction:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch benchmark & selection report
  useEffect(() => {
    async function loadReports() {
      try {
        const [benchRes, selRes] = await Promise.all([
          fetch('/api/prediction/benchmark'),
          fetch('/api/prediction/selection-report'),
        ]);
        if (benchRes.ok) {
          const benchData = await benchRes.json();
          setBenchmark(benchData);
        }
        if (selRes.ok) {
          const selData = await selRes.json();
          setSelectionReport(selData);
        }
      } catch (e) {
        console.warn('Could not load benchmark report:', e);
      }
    }
    loadReports();
  }, []);

  // Sync with initial depth when provided and fetch prediction
  useEffect(() => {
    if (initialDepth) {
      setDepth(initialDepth);
      fetchPrediction(initialDepth);
    } else if (wellId) {
      fetchPrediction(depth);
    }
  }, [wellId, initialDepth]);

  const handlePredictSubmit = (e) => {
    e.preventDefault();
    fetchPrediction(depth);
  };

  const getRiskClass = (prob) => {
    if (prob >= 0.50) return 'high-risk';
    if (prob >= 0.15) return 'medium-risk';
    return 'low-risk';
  };

  return (
    <div className="ai-risk-panel">
      {/* Hero Header */}
      <div className="ai-hero-header">
        <div className="ai-title-wrap">
          <h3>
            <Sparkles size={24} className="text-cyan-400" />
            AI DRILLING RISK PREDICTION
          </h3>
          <p>
            Statistical machine learning forecast of potential drilling hazards over a 100m lookahead window.
          </p>
        </div>
        <div className="ai-badges-group">
          <div className="ai-badge-pill primary">
            <Cpu size={14} />
            <span>Version: {prediction?.model_version || 'nwis-v1.0'}</span>
          </div>
          <div className="ai-badge-pill">
            <Database size={14} />
            <span>Lookahead: {prediction?.lookahead_m || 100} m</span>
          </div>
          <div className="ai-badge-pill">
            <ShieldCheck size={14} />
            <span>Zero-Leakage Verified</span>
          </div>
        </div>
      </div>

      {/* Operational Disclaimer Banner */}
      <div className="ai-disclaimer-banner">
        <AlertTriangle size={18} className="flex-shrink-0" />
        <span>
          <strong>Decision-support only:</strong> This model risk indicator is generated from verified historical drilling incidents and physical telemetry. Requires engineer review. Strictly not certified for autonomous drilling control.
        </span>
      </div>

      {/* Depth Warning Banner if Extrapolated */}
      {prediction && prediction.depth_warning && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex items-center gap-2">
          <AlertTriangle size={16} className="flex-shrink-0 text-amber-600" />
          <span>{prediction.depth_warning}</span>
        </div>
      )}

      {/* Depth Selector Bar */}
      <form onSubmit={handlePredictSubmit} className="ai-depth-selector-bar">
        <div className="ai-depth-controls">
          <label className="text-sm font-bold text-slate-700">Bit Depth (MD):</label>
          <input
            type="number"
            min="100"
            max={7000}
            step="10"
            value={depth}
            onChange={(e) => setDepth(e.target.value)}
            className="ai-depth-input"
          />
          <input
            type="range"
            min="100"
            max={7000}
            step="50"
            value={depth}
            onChange={(e) => setDepth(e.target.value)}
            className="ai-slider-input"
          />
          <span className="text-xs text-slate-500 font-mono">meters MD</span>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="ai-predict-btn"
        >
          {isLoading ? (
            <>
              <Activity size={16} className="animate-spin" />
              <span>Analyzing Depth Signals...</span>
            </>
          ) : (
            <>
              <Sparkles size={16} />
              <span>Predict Hazard Risk</span>
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          <strong>Inference Notice:</strong> {error}
        </div>
      )}

      {/* Hazard Prediction Cards Grid */}
      {prediction && prediction.predictions && (
        <div className="ai-hazard-cards-grid">
          {prediction.predictions.map((p) => {
            const riskClass = getRiskClass(p.probability);
            const formattedName = p.hazard.replace('_', ' ').toUpperCase();
            const pct = p.probability_pct !== undefined ? p.probability_pct : (p.probability * 100);
            const displayPct = typeof pct === 'number' ? (pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)) : pct;

            return (
              <div key={p.hazard} className={`ai-hazard-card ${riskClass}`}>
                <div className="ai-hazard-head">
                  <span className="ai-hazard-name">{formattedName}</span>
                  <span className="ai-alg-badge">{p.algorithm}</span>
                </div>
                <div className="ai-probability-display">
                  <span className="ai-prob-number">{displayPct}</span>
                  <span className="ai-prob-pct">%</span>
                </div>
                <div className="ai-progress-track">
                  <div
                    className="ai-progress-fill"
                    style={{ width: `${Math.max(5, Math.min(100, Number(displayPct)))}%` }}
                  />
                </div>
                <div className="flex justify-between items-center text-xs text-slate-500 pt-1">
                  <span>Relative Risk Probability: {(p.probability).toFixed(4)}</span>
                  <span className="font-semibold">
                    {p.probability >= 0.50 ? 'ELEVATED' : p.probability >= 0.15 ? 'MONITOR' : 'BASELINE'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Split View: Top Contributing Features vs Separate Historical Offset Evidence */}
      {prediction && (
        <div className="ai-split-view-grid">
          {/* Box 1: Explainability / TreeSHAP Feature Contributions */}
          <div className="ai-features-box">
            <div>
              <div className="ai-box-title">
                <TrendingUp size={18} className="text-cyan-600" />
                <span>Model Feature Contributions</span>
              </div>
              <p className="ai-box-subtitle">
                Mathematical influence of active drilling and mud parameters on the hazard probability.
              </p>
            </div>

            <div className="ai-contrib-list">
              {prediction.top_features && prediction.top_features.length > 0 ? (
                prediction.top_features.slice(0, 6).map((feat, idx) => {
                  const absVal = Math.abs(feat.contribution);
                  const barWidth = Math.min(100, Math.round(absVal * 300));
                  return (
                    <div key={idx} className="ai-contrib-item">
                      <div className="ai-contrib-row">
                        <span className="ai-contrib-feat">{feat.feature}</span>
                        <span className="ai-contrib-val">
                          {feat.contribution > 0 ? `+${feat.contribution}` : feat.contribution}
                        </span>
                      </div>
                      <div className="ai-contrib-bar-wrap">
                        <div
                          className="ai-contrib-bar-fill"
                          style={{
                            width: `${Math.max(8, barWidth)}%`,
                            backgroundColor: feat.contribution > 0 ? '#ef4444' : '#0284c7',
                          }}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] text-slate-400">
                        <span>val: {feat.feature_value !== undefined ? feat.feature_value : 'N/A'}</span>
                        <span>{feat.label || 'model feature contribution'}</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-xs text-slate-500">Feature contributions loading...</p>
              )}
            </div>

            <p className="text-[11px] text-slate-400 italic mt-2 border-t pt-2">
              Note: "Model feature contribution" reflects tree ensemble feature attribution. These metrics indicate statistical model weight, not confirmed physical causality.
            </p>
          </div>

          {/* Box 2: Institutional Historical Offset Evidence (Strictly Separated) */}
          <div className="ai-evidence-box">
            <div>
              <div className="ai-box-title">
                <Layers size={18} className="text-blue-600" />
                <span>Historical Offset Evidence</span>
              </div>
              <p className="ai-box-subtitle">
                Verified incidents recorded in offset wells within the {prediction.formation || 'correlated formation'}.
              </p>
            </div>

            <div className="ai-evidence-list">
              {prediction.historical_offset_evidence && prediction.historical_offset_evidence.length > 0 ? (
                prediction.historical_offset_evidence.map((line, idx) => (
                  <div key={idx} className="ai-evidence-card">
                    <Info size={18} className="ai-evidence-icon" />
                    <span>{line}</span>
                  </div>
                ))
              ) : (
                <div className="ai-evidence-card">
                  <Info size={18} className="ai-evidence-icon" />
                  <span>No verified historical offset drilling events recorded in this formation.</span>
                </div>
              )}

              {prediction.offset_summary && (
                <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t text-xs">
                  <div className="bg-slate-50 p-2 rounded border border-slate-100">
                    <span className="text-slate-500 block">Nearby Offset Wells:</span>
                    <strong className="text-slate-800 text-sm">
                      {prediction.offset_summary.nearby_wells || 0} wells
                    </strong>
                  </div>
                  <div className="bg-slate-50 p-2 rounded border border-slate-100">
                    <span className="text-slate-500 block">Closest Hazard Well:</span>
                    <strong className="text-slate-800 text-sm">
                      {prediction.offset_summary.nearest_hazard_km ? `${prediction.offset_summary.nearest_hazard_km.toFixed(1)} km` : 'None'}
                    </strong>
                  </div>
                </div>
              )}
            </div>

            <p className="text-[11px] text-slate-400 italic mt-2 border-t pt-2">
              Provenance: Strictly derived from <code>nwis_historical_drilling_events_15108.csv</code> and spatial offsets. Not merged into a composite score.
            </p>
          </div>
        </div>
      )}

      {/* Expandable Model Selection & Benchmark Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
        <button
          onClick={() => setShowBenchmark(!showBenchmark)}
          className="w-full flex items-center justify-between text-left font-bold text-slate-800 text-sm"
        >
          <div className="flex items-center gap-2">
            <Cpu size={16} className="text-sky-600" />
            <span>Model Selection & Multi-Algorithm Benchmark Report (Held-out Wells)</span>
          </div>
          {showBenchmark ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {showBenchmark && (
          <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col gap-3">
            <p className="text-xs text-slate-600">
              Evaluated 4 algorithms (Random Forest, XGBoost, LightGBM, CatBoost) on 15% held-out test wells using grouped splitting by <code>well_id</code>. Selected automatically using primary metric: <strong>PR-AUC</strong> and secondary: <strong>Recall</strong>.
            </p>

            <div className="overflow-x-auto">
              <table className="ai-benchmark-table">
                <thead>
                  <tr>
                    <th>Hazard</th>
                    <th>Algorithm</th>
                    <th>PR-AUC</th>
                    <th>ROC-AUC</th>
                    <th>Recall</th>
                    <th>Precision</th>
                    <th>F1</th>
                    <th>False Neg</th>
                    <th>False Pos</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmark.map((b, i) => {
                    const isSelected = selectionReport?.selected_models?.[b.hazard]?.selected_algorithm === b.algorithm;
                    return (
                      <tr key={i} className={isSelected ? 'winner-row' : ''}>
                        <td><strong>{b.hazard}</strong></td>
                        <td>
                          {b.algorithm} {isSelected && <span className="text-[10px] bg-sky-100 text-sky-800 font-bold px-1.5 py-0.5 rounded ml-1">SELECTED</span>}
                        </td>
                        <td>{b.pr_auc.toFixed(4)}</td>
                        <td>{b.roc_auc.toFixed(4)}</td>
                        <td>{b.recall.toFixed(4)}</td>
                        <td>{b.precision.toFixed(4)}</td>
                        <td>{b.f1.toFixed(4)}</td>
                        <td>{b.false_negatives}</td>
                        <td>{b.false_positives}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
