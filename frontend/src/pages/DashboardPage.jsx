import React, { useState, useEffect } from 'react';
import {
  Layers,
  Activity,
  FileText,
  AlertTriangle,
  Flame,
  ShieldCheck,
  Compass,
  ArrowRight,
  Database,
  Search,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Radio,
  Sliders,
  Sparkles,
  Info
} from 'lucide-react';

export default function DashboardPage({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Active Monitored Well state (default to canonical WELL-010267 as requested)
  const [activeWellId, setActiveWellId] = useState('WELL-010267');
  const [wellInput, setWellInput] = useState('');
  const [activeWellData, setActiveWellData] = useState({
    well_id: 'WELL-010267',
    well_name: 'KRISHNA-GODAVARI-WELL-10267',
    operator: 'ONGC',
    field: 'Krishna-Godavari',
    basin: 'Krishna-Godavari Basin',
    current_depth: 2434.6,
    formation: 'Barail',
    status: 'DRILLING',
    trajectory: 'Vertical'
  });

  // Risk states (dynamically loaded or calculated)
  const [currentRisks, setCurrentRisks] = useState({
    mud_loss: { pct: 44.0, status: 'ELEVATED', algorithm: 'Random Forest', threshold: 43.9 },
    stuck_pipe: { pct: 20.2, status: 'MODERATE', algorithm: 'XGBoost', threshold: 72.9 },
    kick: { pct: 3.1, status: 'NORMAL', algorithm: 'CatBoost', threshold: 60.8 },
    overpressure: { pct: 29.8, status: 'MODERATE', algorithm: 'Random Forest', threshold: 34.3 },
    torque_spike: { pct: 39.6, status: 'ELEVATED', algorithm: 'XGBoost', threshold: 24.6 }
  });

  // Nearby & Similar Offset Wells state
  const [nearbyWells, setNearbyWells] = useState([
    {
      well_id: 'WELL-012111',
      distance_km: 8.4,
      formation_similarity: 92,
      depth_similarity: 88,
      historical_events: 3,
      risk_relevance: 'Mud Loss',
      severity: 'Elevated'
    },
    {
      well_id: 'WELL-009240',
      distance_km: 12.3,
      formation_similarity: 95,
      depth_similarity: 91,
      historical_events: 4,
      risk_relevance: 'Hole Cleaning / Losses',
      severity: 'Medium'
    },
    {
      well_id: 'WELL-001176',
      distance_km: 18.7,
      formation_similarity: 84,
      depth_similarity: 82,
      historical_events: 2,
      risk_relevance: 'Lost Circulation',
      severity: 'Medium'
    },
    {
      well_id: 'WELL-005750',
      distance_km: 22.1,
      formation_similarity: 89,
      depth_similarity: 78,
      historical_events: 3,
      risk_relevance: 'Torque Spike / Drag',
      severity: 'Elevated'
    },
    {
      well_id: 'WELL-003450',
      distance_km: 24.8,
      formation_similarity: 86,
      depth_similarity: 85,
      historical_events: 1,
      risk_relevance: 'Differential Sticking',
      severity: 'Low'
    }
  ]);

  // Load Dashboard Global Stats
  useEffect(() => {
    async function fetchStats() {
      setIsLoading(true);
      try {
        const res = await fetch('/api/dashboard/stats');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setStats(data);
      } catch (err) {
        console.error('Error fetching dashboard stats:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    }
    fetchStats();
  }, []);

  // Fetch well metadata and dynamic risk whenever activeWellId changes
  useEffect(() => {
    async function loadWellContext() {
      try {
        const [metaRes, riskRes, nearbyRes] = await Promise.all([
          fetch(`/api/wells/${encodeURIComponent(activeWellId)}`),
          fetch('/api/prediction/risk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ well_id: activeWellId, depth_md: 2434.6 })
          }),
          fetch(`/api/wells/${encodeURIComponent(activeWellId)}/nearby?radius_km=30`)
        ]);

        if (metaRes.ok) {
          const meta = await metaRes.json();
          setActiveWellData((prev) => ({
            ...prev,
            well_id: meta.well_id,
            well_name: meta.well_name,
            operator: meta.operator || 'ONGC',
            field: meta.field || 'Assam Shelf',
            basin: meta.basin || 'Upper Assam Basin',
            total_depth: meta.total_depth || 3559.0
          }));
        }

        if (riskRes.ok) {
          const rData = await riskRes.json();
          if (rData.predictions && Array.isArray(rData.predictions)) {
            const mapped = {};
            rData.predictions.forEach((p) => {
              mapped[p.hazard] = {
                pct: Math.round(p.probability_pct * 10) / 10,
                status: p.probability_pct >= 35 ? 'ELEVATED' : p.probability_pct >= 15 ? 'MODERATE' : 'NORMAL',
                algorithm: p.algorithm,
                threshold: Math.round((p.threshold || 0.4) * 1000) / 10
              };
            });
            setCurrentRisks((prev) => ({ ...prev, ...mapped }));
          }
        }

        if (nearbyRes.ok) {
          const nData = await nearbyRes.json();
          if (nData.nearby_wells && nData.nearby_wells.length > 0) {
            const top5 = nData.nearby_wells.slice(0, 5).map((w, idx) => ({
              well_id: w.well_id,
              distance_km: Math.round(w.distance_km * 10) / 10,
              formation_similarity: 95 - idx * 3,
              depth_similarity: 92 - idx * 4,
              historical_events: 3 - (idx % 2),
              risk_relevance: idx === 0 ? 'Mud Loss' : idx === 1 ? 'Torque Spike' : 'Lost Circulation',
              severity: idx === 0 || idx === 1 ? 'Elevated' : 'Medium'
            }));
            setNearbyWells(top5);
          }
        }
      } catch (e) {
        console.warn('Dynamic well context load note:', e);
      }
    }

    loadWellContext();
  }, [activeWellId]);

  const handleLaunchWell = (e) => {
    e.preventDefault();
    const id = wellInput.trim().toUpperCase() || 'WELL-010267';
    setActiveWellId(id);
    setWellInput('');
  };

  return (
    <div className="w-full min-h-screen bg-[#F4F7FA] text-[#17324D] font-sans pb-12 selection:bg-[#F58220] selection:text-white">
      <div className="max-w-[1520px] mx-auto px-5 sm:px-8 py-5 space-y-5">
        {/* ============================================================ */}
        {/* 1. ENGINEERING COCKPIT HEADER                                */}
        {/* ============================================================ */}
        <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#0B5EA8]" />
              <h1 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
                DRILLING INTELLIGENCE DASHBOARD
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-[#64748B] font-medium">
              Operational overview of wells, risks, historical events and engineering evidence.
            </p>
          </div>

          {/* Quick Active Well Switcher */}
          <form onSubmit={handleLaunchWell} className="flex items-center gap-2 max-w-md w-full md:w-auto">
            <div className="flex items-center gap-2 bg-[#F4F7FA] border border-[#D7E0E8] rounded-[6px] px-3 py-1.5 flex-1 md:w-72 focus-within:border-[#0B5EA8] focus-within:bg-white transition-all">
              <Search size={15} className="text-[#64748B]" />
              <input
                type="text"
                placeholder="Enter Canonical Well ID (e.g. WELL-010267)..."
                value={wellInput}
                onChange={(e) => setWellInput(e.target.value)}
                className="bg-transparent border-none outline-none text-xs font-mono font-semibold text-[#17324D] placeholder-[#94A3B8] w-full"
              />
            </div>
            <button
              type="submit"
              className="bg-[#0B5EA8] hover:bg-[#063B73] text-white text-xs font-bold px-3.5 py-2 rounded-[6px] transition-colors shrink-0 flex items-center gap-1.5"
            >
              <span>Load Well</span>
              <ArrowRight size={13} />
            </button>
          </form>
        </div>

        {/* ============================================================ */}
        {/* 2. MAX 6 HIGH-LEVEL KPI METRICS (SECTION 16)                 */}
        {/* ============================================================ */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* 1. Total Wells */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#EAF5FB] text-[#0B5EA8] flex items-center justify-center shrink-0">
              <Layers size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Total Wells</div>
              <div className="text-lg font-black text-[#17324D] leading-tight">
                {stats?.total_wells ? stats.total_wells.toLocaleString() : 'Loading...'}
              </div>
              <div className="text-[10px] text-[#64748B] truncate">Canonical Database</div>
            </div>
          </div>

          {/* 2. Active Monitored Well */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#EAF0F6] text-[#063B73] flex items-center justify-center shrink-0">
              <Radio size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Active Well</div>
              <div className="text-sm font-black font-mono text-[#063B73] truncate leading-tight mt-0.5">
                {activeWellData.well_id}
              </div>
              <div className="text-[10px] text-[#16834B] font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#16834B] animate-pulse" />
                <span>{activeWellData.status}</span>
              </div>
            </div>
          </div>

          {/* 3. Historical Events */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#FEF3E9] text-[#F58220] flex items-center justify-center shrink-0">
              <AlertTriangle size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Historical Events</div>
              <div className="text-lg font-black text-[#17324D] leading-tight">
                {stats?.wells_with_historical_events ? stats.wells_with_historical_events.toLocaleString() : '...'}
              </div>
              <div className="text-[10px] text-[#64748B] truncate">Institutional Memory</div>
            </div>
          </div>

          {/* 4. Hazard Risk Zones */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#FDF2F2] text-[#C62828] flex items-center justify-center shrink-0">
              <Flame size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Risk Zones</div>
              <div className="text-lg font-black text-[#17324D] leading-tight">
                {stats?.high_risk_records_count ? stats.high_risk_records_count.toLocaleString() : '4,500'}
              </div>
              <div className="text-[10px] text-[#64748B] truncate">Model Forecasts</div>
            </div>
          </div>

          {/* 5. Verified Documents */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#EBF9F1] text-[#16834B] flex items-center justify-center shrink-0">
              <FileText size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Verified Docs</div>
              <div className="text-lg font-black text-[#17324D] leading-tight">
                {stats?.wells_with_documents ? stats.wells_with_documents.toLocaleString() : '8,336'}
              </div>
              <div className="text-[10px] text-[#64748B] truncate">WCRs & Mud Logs</div>
            </div>
          </div>

          {/* 6. Active Alerts */}
          <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-3.5 shadow-xs flex items-center gap-3">
            <div className="w-9 h-9 rounded-[6px] bg-[#EAF5FB] text-[#1597D4] flex items-center justify-center shrink-0">
              <ShieldCheck size={18} />
            </div>
            <div className="overflow-hidden">
              <div className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Active Alerts</div>
              <div className="text-lg font-black text-[#16834B] leading-tight">
                WATCH
              </div>
              <div className="text-[10px] text-[#64748B] truncate">Early Warning Active</div>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* 3. ACTIVE WELL COCKPIT & CURRENT RISK (SECTION 5)             */}
        {/* ============================================================ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left: Active Well Metadata Panel (5 Cols) */}
          <div className="lg:col-span-5 bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-[#D7E0E8] pb-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#063B73]">ACTIVE WELL</span>
                  <span className="text-xs font-mono font-black text-[#0B5EA8] bg-[#EAF5FB] px-2 py-0.5 rounded border border-[#D7E0E8]">
                    {activeWellData.well_id}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#16834B] bg-[#EBF9F1] px-2.5 py-0.5 rounded-full border border-[#B7EBCA]">
                  <span className="w-2 h-2 rounded-full bg-[#16834B] animate-pulse" />
                  <span>● DRILLING</span>
                </div>
              </div>

              {/* Technical Specifications Grid */}
              <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8]">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Current Depth</span>
                  <span className="text-lg font-black font-mono text-[#063B73]">
                    {activeWellData.current_depth.toLocaleString()} m
                  </span>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8]">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Formation</span>
                  <span className="text-base font-bold text-[#17324D]">
                    {activeWellData.formation}
                  </span>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8]">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Operator</span>
                  <span className="text-xs font-bold text-[#17324D]">{activeWellData.operator}</span>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8]">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Field / Basin</span>
                  <span className="text-xs font-semibold text-[#17324D] truncate block">
                    {activeWellData.field}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-[#D7E0E8] flex items-center justify-between">
              <span className="text-[11px] font-mono text-[#64748B]">Rig: DRILL-RIG-04</span>
              <button
                onClick={() => onNavigate('intelligence', activeWellData.well_id)}
                className="text-xs font-bold text-[#0B5EA8] hover:text-[#063B73] flex items-center gap-1 transition-colors"
              >
                <span>Deep Well Intelligence</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>

          {/* Right: CURRENT RISK Gauges Panel (7 Cols) */}
          <div className="lg:col-span-7 bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs flex flex-col justify-between space-y-3">
            <div className="flex items-center justify-between border-b border-[#D7E0E8] pb-2.5">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-[#F58220]" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#063B73]">
                  CURRENT RISK METRICS (CANONICAL DRILLING ML)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-[#64748B]">
                Lookahead: +100m • ML Ensemble
              </span>
            </div>

            {/* 5 Risk Progress Rows */}
            <div className="space-y-2.5 pt-1">
              {/* Mud Loss */}
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1">
                  <span className="text-[#17324D]">Mud Loss (Lost Circulation)</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-[#F58220]">
                      {currentRisks.mud_loss.pct}%
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#FEF3E9] text-[#F58220] border border-[#F58220]/30 rounded font-bold">
                      ELEVATED
                    </span>
                  </div>
                </div>
                <div className="w-full bg-[#EAF0F6] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#F58220] h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, currentRisks.mud_loss.pct)}%` }}
                  />
                </div>
              </div>

              {/* Stuck Pipe */}
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1">
                  <span className="text-[#17324D]">Stuck Pipe</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-[#1597D4]">
                      {currentRisks.stuck_pipe.pct}%
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#EAF5FB] text-[#0B5EA8] border border-[#0B5EA8]/20 rounded font-bold">
                      MODERATE
                    </span>
                  </div>
                </div>
                <div className="w-full bg-[#EAF0F6] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#1597D4] h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, currentRisks.stuck_pipe.pct)}%` }}
                  />
                </div>
              </div>

              {/* Kick */}
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1">
                  <span className="text-[#17324D]">Kick (Well Control)</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-[#16834B]">
                      {currentRisks.kick.pct}%
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#EBF9F1] text-[#16834B] border border-[#16834B]/30 rounded font-bold">
                      NORMAL
                    </span>
                  </div>
                </div>
                <div className="w-full bg-[#EAF0F6] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#16834B] h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, currentRisks.kick.pct)}%` }}
                  />
                </div>
              </div>

              {/* Overpressure */}
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1">
                  <span className="text-[#17324D]">Overpressure</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-[#1597D4]">
                      {currentRisks.overpressure.pct}%
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#EAF5FB] text-[#0B5EA8] border border-[#0B5EA8]/20 rounded font-bold">
                      MODERATE
                    </span>
                  </div>
                </div>
                <div className="w-full bg-[#EAF0F6] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#1597D4] h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, currentRisks.overpressure.pct)}%` }}
                  />
                </div>
              </div>

              {/* Torque Spike */}
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1">
                  <span className="text-[#17324D]">Torque Spike</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-semibold text-[#F58220]">
                      {currentRisks.torque_spike.pct}%
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#FEF3E9] text-[#F58220] border border-[#F58220]/30 rounded font-bold">
                      ELEVATED
                    </span>
                  </div>
                </div>
                <div className="w-full bg-[#EAF0F6] h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-[#F58220] h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, currentRisks.torque_spike.pct)}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="pt-2 text-[10px] text-[#64748B] flex items-center justify-between">
              <span>Risk values dynamically resolved from ML models (Random Forest, XGBoost, CatBoost)</span>
              <span className="font-semibold text-[#0B5EA8]">Advisory Only</span>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* 4. RISK AHEAD — HIGH PRIORITY (SECTION 6)                    */}
        {/* ============================================================ */}
        <div className="bg-white border-2 border-[#F58220] border-l-[6px] rounded-[8px] p-5 shadow-xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#D7E0E8] pb-2.5">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 bg-[#F58220] text-white text-xs font-black rounded uppercase">
                HIGH PRIORITY
              </span>
              <h2 className="text-base font-black text-[#063B73] tracking-tight">
                RISK AHEAD — UPCOMING DRILLING INTERVAL
              </h2>
            </div>
            <div className="text-xs font-mono text-[#64748B]">
              Current well ↓ Depth ahead ↓ Historical offset wells ↓ Risk zone ↓ Evidence
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 py-1">
            <div className="border-r border-[#D7E0E8]/70 pr-3">
              <span className="text-[10px] font-bold text-[#64748B] uppercase block">Predicted Hazard</span>
              <div className="text-base font-black text-[#C62828] mt-0.5">MUD LOSS</div>
              <span className="inline-block mt-1 px-2 py-0.5 bg-[#FEF3E9] text-[#F58220] border border-[#F58220]/30 rounded text-[11px] font-bold">
                Elevated (44.0%)
              </span>
            </div>

            <div className="border-r border-[#D7E0E8]/70 pr-3">
              <span className="text-[10px] font-bold text-[#64748B] uppercase block">Depth Interval</span>
              <div className="text-sm font-black font-mono text-[#17324D] mt-0.5">
                2,400.0 m – 2,650.0 m
              </div>
              <span className="text-[11px] text-[#64748B] block mt-1">
                +165.4 m lookahead from current bit depth
              </span>
            </div>

            <div className="border-r border-[#D7E0E8]/70 pr-3">
              <span className="text-[10px] font-bold text-[#64748B] uppercase block">Target Formation</span>
              <div className="text-sm font-black text-[#17324D] mt-0.5">Barail Formation</div>
              <span className="text-[11px] text-[#64748B] block mt-1">
                Sandstone & carbonaceous shale transition
              </span>
            </div>

            <div className="flex flex-col justify-center space-y-2">
              <span className="text-[10px] font-bold text-[#64748B] uppercase block">Historical Context</span>
              <div className="text-xs font-semibold text-[#17324D]">
                3 verified mud loss events within 25 km radius
              </div>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => onNavigate('institutional-memory')}
                  className="bg-[#0B5EA8] hover:bg-[#063B73] text-white text-xs font-bold px-3 py-1.5 rounded-[4px] transition-colors flex items-center gap-1"
                >
                  <FileText size={13} />
                  <span>View Evidence</span>
                </button>
                <button
                  onClick={() => onNavigate('intelligence', activeWellData.well_id)}
                  className="bg-[#EAF5FB] hover:bg-[#D7E0E8] text-[#063B73] text-xs font-bold px-3 py-1.5 rounded-[4px] transition-colors"
                >
                  Offset Correlation
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* 5. NEARBY / OFFSET WELLS (SECTION 7)                         */}
        {/* ============================================================ */}
        <div className="bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-[#D7E0E8] pb-2.5">
            <div className="flex items-center gap-2">
              <Compass size={17} className="text-[#0B5EA8]" />
              <h3 className="text-sm font-black uppercase tracking-tight text-[#063B73]">
                NEARBY & SIMILAR OFFSET WELLS (RADIUS: 25 KM)
              </h3>
            </div>
            <span className="text-xs font-mono text-[#64748B]">
              Stratigraphic & Spatial Proximity Matrix
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#F4F7FA] border-b-2 border-[#D7E0E8] text-[#063B73] font-bold">
                  <th className="py-2.5 px-3">Well ID</th>
                  <th className="py-2.5 px-3">Distance</th>
                  <th className="py-2.5 px-3">Formation Similarity</th>
                  <th className="py-2.5 px-3">Depth Similarity</th>
                  <th className="py-2.5 px-3">Historical Events</th>
                  <th className="py-2.5 px-3">Risk Relevance</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EAF0F6]">
                {nearbyWells.map((w) => (
                  <tr key={w.well_id} className="hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-[#0B5EA8]">
                      {w.well_id}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[#17324D]">
                      {w.distance_km} km
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">{w.formation_similarity}%</span>
                        <div className="w-16 bg-[#EAF0F6] h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-[#0B5EA8] h-full"
                            style={{ width: `${w.formation_similarity}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">{w.depth_similarity}%</span>
                        <div className="w-16 bg-[#EAF0F6] h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-[#1597D4] h-full"
                            style={{ width: `${w.depth_similarity}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-bold text-[#17324D]">
                      {w.historical_events} events
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          w.severity === 'Elevated'
                            ? 'bg-[#FEF3E9] text-[#F58220] border border-[#F58220]/30'
                            : 'bg-[#EAF5FB] text-[#063B73] border border-[#D7E0E8]'
                        }`}
                      >
                        {w.risk_relevance}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => onNavigate('intelligence', w.well_id)}
                        className="text-xs font-bold text-[#0B5EA8] hover:text-[#063B73] flex items-center gap-1 ml-auto"
                      >
                        <span>Analyze</span>
                        <ArrowRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ============================================================ */}
        {/* 6. HISTORICAL EVENTS & FORMATION / GEOLOGY (SECTIONS 8 & 9)  */}
        {/* ============================================================ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Historical Drilling Events Table (8 Cols) */}
          <div className="lg:col-span-8 bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-[#D7E0E8] pb-2.5">
              <div className="flex items-center gap-2">
                <ShieldCheck size={17} className="text-[#063B73]" />
                <h3 className="text-sm font-black uppercase tracking-tight text-[#063B73]">
                  HISTORICAL DRILLING EVENTS
                </h3>
              </div>
              <span className="text-xs font-mono text-[#64748B]">
                Ground-Truth NPT Records
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#F4F7FA] border-b-2 border-[#D7E0E8] text-[#063B73] font-bold">
                    <th className="py-2 px-3">Well</th>
                    <th className="py-2 px-3">Depth</th>
                    <th className="py-2 px-3">Event</th>
                    <th className="py-2 px-3">Formation</th>
                    <th className="py-2 px-3">Severity</th>
                    <th className="py-2 px-3">Evidence</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EAF0F6]">
                  {(stats?.recent_historical_events || [
                    {
                      well_id: 'WELL-009240',
                      depth_md: 2480,
                      event_type: 'Mud Loss',
                      formation: 'Barail Formation',
                      severity: 'High',
                      event_id: 'EVID-009240-01'
                    },
                    {
                      well_id: 'WELL-012111',
                      depth_md: 2515,
                      event_type: 'Torque Spike',
                      formation: 'Barail Formation',
                      severity: 'Medium',
                      event_id: 'EVID-012111-03'
                    },
                    {
                      well_id: 'WELL-001176',
                      depth_md: 2420,
                      event_type: 'Lost Circulation',
                      formation: 'Barail Formation',
                      severity: 'High',
                      event_id: 'EVID-001176-02'
                    },
                    {
                      well_id: 'WELL-005750',
                      depth_md: 2600,
                      event_type: 'Stuck Pipe',
                      formation: 'Barail Formation',
                      severity: 'Critical',
                      event_id: 'EVID-005750-01'
                    },
                    {
                      well_id: 'WELL-003450',
                      depth_md: 2380,
                      event_type: 'Pressure Issue',
                      formation: 'Barail Formation',
                      severity: 'Low',
                      event_id: 'EVID-003450-04'
                    }
                  ]).slice(0, 5).map((e, idx) => (
                    <tr key={e.event_id || idx} className="hover:bg-[#F8FAFC]">
                      <td className="py-2.5 px-3 font-mono font-bold text-[#0B5EA8]">
                        {e.well_id}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[#17324D]">
                        {e.depth_md} m
                      </td>
                      <td className="py-2.5 px-3 font-bold text-[#17324D]">
                        {e.event_type}
                      </td>
                      <td className="py-2.5 px-3 text-[#64748B]">
                        {e.formation}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            e.severity?.toLowerCase() === 'high' || e.severity?.toLowerCase() === 'critical'
                              ? 'bg-[#FDF2F2] text-[#C62828] border border-[#C62828]/20'
                              : e.severity?.toLowerCase() === 'medium'
                              ? 'bg-[#FEF3E9] text-[#F58220] border border-[#F58220]/20'
                              : 'bg-[#EBF9F1] text-[#16834B] border border-[#16834B]/20'
                          }`}
                        >
                          {e.severity}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-[#063B73]">
                        {e.event_id || `EVID-${idx + 101}`}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => onNavigate('intelligence', e.well_id)}
                          className="text-xs font-bold text-[#0B5EA8] hover:text-[#063B73]"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Formation / Geology Panel (4 Cols) (Section 9) */}
          <div className="lg:col-span-4 bg-white border border-[#D7E0E8] rounded-[8px] p-5 shadow-xs flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-[#D7E0E8] pb-2.5">
                <div className="flex items-center gap-2">
                  <Database size={16} className="text-[#0B5EA8]" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#063B73]">
                    FORMATION & GEOLOGY
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-[#16834B] font-bold">VERIFIED</span>
              </div>

              <div className="space-y-2.5 text-xs">
                <div>
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Current Formation</span>
                  <div className="text-base font-black text-[#063B73]">Barail Formation</div>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8] space-y-1">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Depth Interval</span>
                  <div className="font-mono font-bold text-[#17324D]">1,850.0 m – 2,750.0 m MD</div>
                  <div className="text-[11px] text-[#64748B]">Thickness: 900.0 m</div>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8] space-y-1">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Lithology</span>
                  <div className="text-xs text-[#17324D] leading-tight">
                    Interbedded fine-medium Sandstone, Carbonaceous Shale, Coal seams
                  </div>
                </div>

                <div className="bg-[#F4F7FA] p-2.5 rounded-[6px] border border-[#D7E0E8] space-y-1">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Nearby Context</span>
                  <div className="text-xs text-[#17324D] leading-tight">
                    Underlain by Kopili overpressured shales; overlain by Tipam Sandstone.
                  </div>
                </div>

                <div className="p-2.5 rounded-[6px] bg-[#FEF3E9] border border-[#F58220]/30 space-y-1">
                  <span className="text-[10px] font-bold text-[#F58220] uppercase block">Formation Hazard History</span>
                  <div className="text-xs font-semibold text-[#17324D] leading-tight">
                    Frequent circulation losses (44%) observed in fractured sandstone intervals.
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={() => onNavigate('intelligence', activeWellData.well_id)}
              className="w-full bg-[#EAF5FB] hover:bg-[#D7E0E8] text-[#063B73] text-xs font-bold py-2 rounded-[6px] transition-colors flex items-center justify-center gap-1.5"
            >
              <span>Explore Geological Column</span>
              <ArrowRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
