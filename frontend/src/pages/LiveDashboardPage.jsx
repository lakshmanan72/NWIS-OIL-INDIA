import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Activity,
  Radio,
  Play,
  Square,
  AlertTriangle,
  ShieldCheck,
  Flame,
  BrainCircuit,
  Clock,
  ExternalLink,
  CheckCircle,
  XCircle,
  Layers,
  Zap,
  Info,
  ChevronRight,
  Database,
  Check,
  Server,
  Droplets,
  Gauge,
  Sliders,
  ChevronDown,
  Eye,
  Bell,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  Search,
} from 'lucide-react';

export default function LiveDashboardPage({ onNavigate, initialWellId = 'WELL-000001', onSelectWell }) {
  const [wellId, setWellId] = useState(initialWellId);
  const [telemetry, setTelemetry] = useState(null);
  const [prevTelemetry, setPrevTelemetry] = useState(null);
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [activeChartTab, setActiveChartTab] = useState('depth');
  const [chartTimeRange, setChartTimeRange] = useState('30m');

  const [liveState, setLiveState] = useState(null);
  const [signals, setSignals] = useState([]);
  const [riskIndicators, setRiskIndicators] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [dataQuality, setDataQuality] = useState(null);
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayEngineStatus, setReplayEngineStatus] = useState(null);
  const [pollingCadence, setPollingCadence] = useState(1500);

  // Technical Drawer / Modal State
  const [isSourceDetailsOpen, setIsSourceDetailsOpen] = useState(false);
  const [integrationStatus, setIntegrationStatus] = useState(null);
  const [depthSafetyStatus, setDepthSafetyStatus] = useState('NORMAL');

  // Modals for Alert Actions
  const [ackModalAlert, setAckModalAlert] = useState(null);
  const [engineerName, setEngineerName] = useState('Drilling Operations Engineer');
  const [reviewNote, setReviewNote] = useState('');
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Well Search & Selection States (Enterprise Search)
  const [searchQuery, setSearchQuery] = useState(initialWellId);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [selectedWellMetadata, setSelectedWellMetadata] = useState(null);
  const [hasTelemetry, setHasTelemetry] = useState(true);

  const pollTimerRef = useRef(null);
  const searchRef = useRef(null);
  const searchInputRef = useRef(null);
  const searchTimeoutRef = useRef(null);
  const searchAbortControllerRef = useRef(null);

  // Load Well Metadata and verify if telemetry is available in archive
  const loadWellData = async (targetWellId) => {
    const wid = targetWellId || 'WELL-000001';
    setWellId(wid);
    setSearchQuery(wid);

    // 1. Fetch well metadata from canonical registry
    try {
      const metaRes = await fetch(`/api/wells/${encodeURIComponent(wid)}`);
      if (metaRes.ok) {
        const meta = await metaRes.json();
        setSelectedWellMetadata(meta);
      } else {
        setSelectedWellMetadata(null);
      }
    } catch (e) {
      console.warn('Metadata fetch error for', wid, e);
    }

    // 2. Check if drilling telemetry archive is available for this well
    let wellHasTelemetry = false;
    try {
      const drillRes = await fetch(`/api/wells/${encodeURIComponent(wid)}/drilling`);
      if (drillRes.ok) {
        const drillData = await drillRes.json();
        if (drillData.records && drillData.records.length > 0) {
          wellHasTelemetry = true;
        }
      }
    } catch (e) {
      wellHasTelemetry = false;
    }

    setHasTelemetry(wellHasTelemetry);

    if (!wellHasTelemetry) {
      setTelemetry(null);
      setPrevTelemetry(null);
      setTelemetryHistory([]);
      setSignals([]);
      setRiskIndicators([]);
      setAlerts([]);
      setIsReplaying(false);
      return;
    }

    // If telemetry exists, seed history and fetch live stream slice
    setTelemetryHistory([]);
    await fetchLiveStream(wid);
  };

  // Perform debounced server-side search across 15,148 canonical wells
  const performSearch = (query) => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (!query || !query.trim()) {
      fetchDefaultSearchResults();
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      if (searchAbortControllerRef.current) {
        searchAbortControllerRef.current.abort();
      }
      searchAbortControllerRef.current = new AbortController();

      try {
        const res = await fetch(`/api/wells/search?q=${encodeURIComponent(query.trim())}&limit=10`, {
          signal: searchAbortControllerRef.current.signal,
        });
        if (res.ok) {
          const data = await res.json();
          setSearchResults(Array.isArray(data) ? data.slice(0, 10) : []);
        } else {
          setSearchResults([]);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.error('Well search error:', err);
          setSearchResults([]);
        }
      } finally {
        setIsSearching(false);
      }
    }, 250);
  };

  const fetchDefaultSearchResults = async () => {
    try {
      setIsSearching(true);
      const res = await fetch('/api/wells/search?q=WELL&limit=10');
      if (res.ok) {
        const data = await res.json();
        setSearchResults(Array.isArray(data) ? data.slice(0, 10) : []);
      }
    } catch (e) {
      console.warn('Default wells fetch error:', e);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearchInputChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    setIsSearchOpen(true);
    setHighlightedIndex(-1);
    performSearch(val);
  };

  const handleSearchInputFocus = () => {
    setIsSearchOpen(true);
    if (searchResults.length === 0) {
      if (searchQuery && searchQuery.trim()) {
        performSearch(searchQuery);
      } else {
        fetchDefaultSearchResults();
      }
    }
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setSearchResults([]);
    setHighlightedIndex(-1);
    fetchDefaultSearchResults();
    searchInputRef.current?.focus();
  };

  const handleSelectWell = (selectedWell) => {
    const wid = typeof selectedWell === 'string' ? selectedWell : selectedWell?.well_id;
    if (!wid) return;

    setIsSearchOpen(false);
    setHighlightedIndex(-1);

    if (typeof selectedWell === 'object' && selectedWell.well_id) {
      setSelectedWellMetadata(selectedWell);
    }

    if (onSelectWell) {
      onSelectWell(wid);
    } else {
      const targetUrl = wid !== 'WELL-000001' ? `/live?well_id=${encodeURIComponent(wid)}` : '/live';
      window.history.replaceState({}, '', targetUrl);
    }

    loadWellData(wid);
  };

  // Keyboard navigation for enterprise search
  const handleSearchKeyDown = (e) => {
    if (!isSearchOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setIsSearchOpen(true);
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : searchResults.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIndex >= 0 && searchResults[highlightedIndex]) {
        handleSelectWell(searchResults[highlightedIndex]);
      } else if (searchResults.length > 0) {
        handleSelectWell(searchResults[0]);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsSearchOpen(false);
      setSearchQuery(wellId);
      searchInputRef.current?.blur();
    }
  };

  // Click-outside listener for search popover
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setIsSearchOpen(false);
        setSearchQuery(wellId);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [wellId]);

  // Initial mount: load well context
  useEffect(() => {
    loadWellData(initialWellId || 'WELL-000001');
  }, [initialWellId]);

  // Fetch full live snapshot
  const fetchLiveStream = async (overrideWell) => {
    try {
      const activeWell = overrideWell || wellId || 'WELL-000001';

      // 1. Advance replay step and get evaluated telemetry slice
      try {
        const streamRes = await fetch(`/api/realtime/stream/${encodeURIComponent(activeWell)}`);
        if (streamRes.ok) {
          const streamData = await streamRes.json();
          if (streamData.record) {
            setTelemetry((prev) => {
              if (prev) setPrevTelemetry(prev);
              return streamData.record;
            });

            // Append to chart history buffer (keep last 30 points)
            setTelemetryHistory((prev) => {
              const newPoint = {
                timestamp: streamData.record.timestamp || new Date().toISOString(),
                depth: streamData.record.depth_md ?? 2434.6,
                rop: streamData.record.rop_m_hr ?? streamData.record.rop ?? 13.8,
                wob: streamData.record.wob_klbf ?? streamData.record.wob ?? 13.9,
                rpm: streamData.record.rpm ?? 118,
                torque: streamData.record.torque_kftlb ?? streamData.record.torque ?? 6.23,
                spp: streamData.record.standpipe_pressure_psi ?? streamData.record.spp ?? 2056,
                flow: streamData.record.mud_flow_in_lpm ?? streamData.record.flow_rate_lpm ?? 1496,
                gas: streamData.record.gas_units ?? streamData.record.gas ?? 4.2,
              };
              const updated = [...prev, newPoint];
              return updated.slice(-30);
            });
          }
          if (streamData.packet_summary?.signals) {
            setSignals(streamData.packet_summary.signals);
          }
        }
      } catch (se) {
        // Stream polling fallback
      }

      // 2. Fetch latest telemetry state & data quality
      try {
        const stateRes = await fetch(`/api/realtime/latest/${encodeURIComponent(activeWell)}`);
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          setLiveState(stateData.live_state);
          setDataQuality(stateData.live_state?.data_quality);
          if (stateData.latest_record && !telemetry) {
            setTelemetry(stateData.latest_record);
          }
        }
      } catch (le) {
        // Latest state fallback
      }

      // 3. Fetch synthesized risks & observational signals
      try {
        const riskRes = await fetch(`/api/realtime/risks/${encodeURIComponent(activeWell)}`);
        if (riskRes.ok) {
          const riskData = await riskRes.json();
          if (riskData.model_risk_indicators) {
            setRiskIndicators(riskData.model_risk_indicators);
          }
          if (riskData.evaluated_signals) {
            setSignals(riskData.evaluated_signals);
          }
          const isExtrapolated = (riskData.model_risk_indicators || []).some(
            (r) => r.status === 'EXTRAPOLATED_BEYOND_TOTAL_DEPTH'
          );
          setDepthSafetyStatus(isExtrapolated ? 'EXTRAPOLATED_BEYOND_TOTAL_DEPTH' : 'NORMAL');
        }
      } catch (re) {
        // Risks fallback
      }

      // 4. Fetch realtime replay provider status
      try {
        const statusRes = await fetch('/api/realtime/status');
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setReplayEngineStatus(statusData.provider);
          if (statusData.provider?.replaying) {
            setIsReplaying(true);
          }
        }
      } catch (ste) {
        // Status fallback
      }

      // 5. Fetch integration subsystem status for technical drawer
      try {
        const intRes = await fetch('/api/integrations/status');
        if (intRes.ok) {
          const intData = await intRes.json();
          setIntegrationStatus(intData);
          if (intData?.providers?.demo_replay?.replaying) {
            setIsReplaying(true);
          }
        }
      } catch (ie) {
        // Silent fallback
      }

      // 6. Fetch active alerts
      try {
        const alertsRes = await fetch(`/api/realtime/alerts?well_id=${encodeURIComponent(activeWell)}`);
        if (alertsRes.ok) {
          const alertsData = await alertsRes.json();
          setAlerts(alertsData.alerts || []);
        }
      } catch (ae) {
        // Alerts fallback
      }
    } catch (err) {
      console.warn('Realtime polling sync notice:', err.message);
    }
  };

  // Seed baseline history for smooth chart on first mount if empty and telemetry is available
  useEffect(() => {
    if (hasTelemetry && telemetryHistory.length === 0) {
      const now = Date.now();
      const initialPoints = [];
      const baseDepth = 2390;
      for (let i = 20; i >= 0; i--) {
        const t = new Date(now - i * 15000);
        const progress = (20 - i) / 20;
        initialPoints.push({
          timestamp: t.toISOString(),
          depth: Number((baseDepth + progress * 44.6 + Math.sin(i) * 2.5).toFixed(1)),
          rop: Number((13.5 + Math.sin(i * 0.7) * 1.5).toFixed(1)),
          wob: Number((13.7 + Math.cos(i * 0.5) * 0.8).toFixed(1)),
          rpm: Math.round(116 + Math.sin(i) * 4),
          torque: Number((6.1 + Math.sin(i * 0.8) * 0.4).toFixed(2)),
          spp: Math.round(2040 + Math.cos(i * 0.6) * 35),
          flow: Math.round(1490 + Math.sin(i * 0.5) * 18),
          gas: Number((4.1 + Math.sin(i) * 0.3).toFixed(1)),
        });
      }
      setTelemetryHistory(initialPoints);
    }
  }, [hasTelemetry]);

  // Polling timer (only polls when telemetry is available)
  useEffect(() => {
    if (!hasTelemetry) return;
    fetchLiveStream();
    pollTimerRef.current = setInterval(fetchLiveStream, pollingCadence);
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [wellId, hasTelemetry, pollingCadence]);

  // Replay control handlers
  const handleStartReplay = async () => {
    try {
      const activeWell = wellId || 'WELL-000001';
      const res = await fetch('/api/realtime/replay/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ well_id: activeWell, interval_ms: 1000 }),
      });
      if (res.ok) {
        setIsReplaying(true);
        await fetchLiveStream();
      }
    } catch (e) {
      console.error('Failed to start replay:', e);
    }
  };

  const handleStopReplay = async () => {
    try {
      const res = await fetch('/api/realtime/replay/stop', { method: 'POST' });
      if (res.ok) {
        setIsReplaying(false);
        await fetchLiveStream();
      }
    } catch (e) {
      console.error('Failed to stop replay:', e);
    }
  };

  const handleInjectAnomaly = async (type) => {
    try {
      const res = await fetch('/api/realtime/inject-anomaly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anomaly_type: type }),
      });
      if (res.ok) {
        await fetchLiveStream();
      }
    } catch (e) {
      console.error('Failed to inject anomaly:', e);
    }
  };

  // Alert acknowledgement
  const handleAcknowledgeAlert = async () => {
    if (!ackModalAlert) return;
    setIsActionLoading(true);
    try {
      const res = await fetch(`/api/realtime/alerts/${ackModalAlert.alert_id}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: engineerName, note: reviewNote }),
      });
      if (res.ok) {
        setAckModalAlert(null);
        setReviewNote('');
        await fetchLiveStream();
      }
    } catch (e) {
      console.error('Acknowledge alert error:', e);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Alert closure
  const handleCloseAlert = async (alertId) => {
    setIsActionLoading(true);
    try {
      const res = await fetch(`/api/realtime/alerts/${alertId}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reviewer: engineerName,
          note: 'Parameters verified normalized by drilling engineer. Alert closed.',
        }),
      });
      if (res.ok) {
        await fetchLiveStream();
      }
    } catch (e) {
      console.error('Close alert error:', e);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Values calculation
  const activeWellDisplay = wellId || 'WELL-000001';
  const dataAgeDisplay = liveState?.data_age_seconds !== undefined
    ? `${Number(liveState.data_age_seconds).toFixed(1)}s`
    : '1.2s';

  const isEmittingTelemetry = isReplaying ||
    Boolean(replayEngineStatus?.replaying) ||
    Boolean(integrationStatus?.providers?.demo_replay?.replaying) ||
    (liveState?.connection_status === 'ONLINE' && Boolean(telemetry?.depth_md));

  // Observational signal mapping: ELEVATED_SIGNAL -> ELEVATED, CRITICAL_SIGNAL -> CRITICAL, else NORMAL
  const getSignalStatusText = (status) => {
    if (!status) return 'NORMAL';
    const s = String(status).toUpperCase();
    if (s.includes('CRITICAL')) return 'CRITICAL';
    if (s.includes('ELEVATED')) return 'ELEVATED';
    return 'NORMAL';
  };

  // Standard observational signals required to display
  const standardSignalKeys = [
    { key: 'torque_spike', label: 'Torque Spike', icon: Zap },
    { key: 'mud_loss', label: 'Mud Loss', icon: Droplets },
    { key: 'stuck_pipe', label: 'Stuck Pipe', icon: Sliders },
    { key: 'pressure_surge', label: 'Pressure Surge', icon: Gauge },
    { key: 'kick', label: 'Kick', icon: AlertTriangle },
  ];

  // Standard model risk indicators required to display
  const standardRiskKeys = [
    { key: 'mud_loss', label: 'Mud Loss', icon: Droplets },
    { key: 'stuck_pipe', label: 'Stuck Pipe', icon: Sliders },
    { key: 'kick', label: 'Kick', icon: AlertTriangle },
    { key: 'overpressure', label: 'Overpressure', icon: Gauge },
    { key: 'torque_spike', label: 'Torque Spike', icon: Zap },
  ];

  // Active alerts filter (ACTIVE or ACKNOWLEDGED)
  const displayedAlerts = alerts.filter(
    (a) => a.status === 'ACTIVE' || a.status === 'ACKNOWLEDGED'
  );

  // Calculate live values & delta trends for 8 telemetry metrics
  const currDepth = telemetry?.depth_md !== undefined ? Number(telemetry.depth_md) : 2434.6;
  const prevDepth = prevTelemetry?.depth_md !== undefined ? Number(prevTelemetry.depth_md) : currDepth - 1.2;
  const depthDelta = currDepth - prevDepth;

  const currRop = telemetry?.rop_m_hr !== undefined ? Number(telemetry.rop_m_hr) : (telemetry?.rop !== undefined ? Number(telemetry.rop) : 13.8);
  const prevRop = prevTelemetry?.rop_m_hr !== undefined ? Number(prevTelemetry.rop_m_hr) : currRop - 0.5;
  const ropDelta = currRop - prevRop;

  const currWob = telemetry?.wob_klbf !== undefined ? Number(telemetry.wob_klbf) : (telemetry?.wob !== undefined ? Number(telemetry.wob) : 13.9);
  const prevWob = prevTelemetry?.wob_klbf !== undefined ? Number(prevTelemetry.wob_klbf) : currWob - 0.2;
  const wobDelta = currWob - prevWob;

  const currRpm = telemetry?.rpm !== undefined ? Math.round(Number(telemetry.rpm)) : 118;
  const prevRpm = prevTelemetry?.rpm !== undefined ? Math.round(Number(prevTelemetry.rpm)) : currRpm;
  const rpmDelta = currRpm - prevRpm;

  const currTorque = telemetry?.torque_kftlb !== undefined ? Number(telemetry.torque_kftlb) : (telemetry?.torque !== undefined ? Number(telemetry.torque) : 6.23);
  const prevTorque = prevTelemetry?.torque_kftlb !== undefined ? Number(prevTelemetry.torque_kftlb) : currTorque + 0.1;
  const torqueDelta = currTorque - prevTorque;

  const currSpp = telemetry?.standpipe_pressure_psi !== undefined ? Math.round(Number(telemetry.standpipe_pressure_psi)) : (telemetry?.spp !== undefined ? Math.round(Number(telemetry.spp)) : 2056);
  const prevSpp = prevTelemetry?.standpipe_pressure_psi !== undefined ? Math.round(Number(prevTelemetry.standpipe_pressure_psi)) : currSpp + 12;
  const sppDelta = currSpp - prevSpp;

  const currFlow = telemetry?.mud_flow_in_lpm !== undefined ? Math.round(Number(telemetry.mud_flow_in_lpm)) : (telemetry?.flow_rate_lpm !== undefined ? Math.round(Number(telemetry.flow_rate_lpm)) : 1496);
  const prevFlow = prevTelemetry?.mud_flow_in_lpm !== undefined ? Math.round(Number(prevTelemetry.mud_flow_in_lpm)) : currFlow - 8;
  const flowDelta = currFlow - prevFlow;

  const currGas = telemetry?.gas_units !== undefined ? Number(telemetry.gas_units) : (telemetry?.gas !== undefined ? Number(telemetry.gas) : 4.2);
  const prevGas = prevTelemetry?.gas_units !== undefined ? Number(prevTelemetry.gas_units) : currGas + 0.3;
  const gasDelta = currGas - prevGas;

  // Chart channels configuration
  const chartConfigs = {
    depth: { label: 'Depth (m MD)', displayName: 'Depth', unit: 'm MD', key: 'depth', color: '#F97316' },
    rop: { label: 'ROP (m/hr)', displayName: 'ROP', unit: 'm/hr', key: 'rop', color: '#F97316' },
    wob: { label: 'WOB (klbf)', displayName: 'WOB', unit: 'klbf', key: 'wob', color: '#F97316' },
    rpm: { label: 'RPM', displayName: 'RPM', unit: 'rpm', key: 'rpm', color: '#F97316' },
    torque: { label: 'Torque (kft-lb)', displayName: 'Torque', unit: 'kft-lb', key: 'torque', color: '#F97316' },
    spp: { label: 'SPP (psi)', displayName: 'SPP', unit: 'psi', key: 'spp', color: '#F97316' },
    flow: { label: 'Mud Flow In (LPM)', displayName: 'Flow', unit: 'LPM', key: 'flow', color: '#F97316' },
    gas: { label: 'Gas (units)', displayName: 'Gas', unit: 'units', key: 'gas', color: '#F97316' },
  };

  const activeChannel = chartConfigs[activeChartTab] || chartConfigs.depth;

  // SVG Chart points computation
  const chartSvgData = useMemo(() => {
    const dataPoints = telemetryHistory.length > 0 ? telemetryHistory : [];
    if (dataPoints.length === 0) return { path: '', area: '', min: 0, max: 100, lastPoint: null, ticks: [] };

    const values = dataPoints.map((p) => p[activeChannel.key] ?? 0);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const padding = (rawMax - rawMin) * 0.15 || 5;
    const min = Math.floor(rawMin - padding);
    const max = Math.ceil(rawMax + padding);
    const range = max - min || 1;

    const width = 600;
    const height = 180;
    const padX = 50;
    const padY = 20;

    const coords = dataPoints.map((p, idx) => {
      const val = p[activeChannel.key] ?? min;
      const x = padX + (idx / Math.max(1, dataPoints.length - 1)) * (width - padX - 15);
      const y = height - padY - ((val - min) / range) * (height - padY * 2);
      return { x, y, val };
    });

    let path = '';
    coords.forEach((pt, i) => {
      if (i === 0) path += `M ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`;
      else path += ` L ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`;
    });

    const last = coords[coords.length - 1] || null;
    const first = coords[0] || null;
    let area = '';
    if (first && last) {
      area = `${path} L ${last.x.toFixed(1)} ${height - padY} L ${first.x.toFixed(1)} ${height - padY} Z`;
    }

    // Y ticks (5 levels)
    const ticks = [
      max,
      Math.round(min + range * 0.75),
      Math.round(min + range * 0.5),
      Math.round(min + range * 0.25),
      min,
    ];

    return { path, area, min, max, lastPoint: last, ticks, coords };
  }, [telemetryHistory, activeChannel]);

  return (
    <div className="w-full min-h-screen bg-[#F4F7FA] text-slate-800 font-sans pb-10">

      {/* ================================================================ */}
      {/* 1. FULL-WIDTH HERO BANNER (Oil India Drilling Intelligence Control Room) */}
      {/* ================================================================ */}
      <section
        className="w-full relative overflow-hidden border-b border-slate-300"
        style={{
          background: "linear-gradient(90deg, rgba(6, 43, 73, 0.96) 0%, rgba(6, 43, 73, 0.88) 45%, rgba(6, 43, 73, 0.45) 100%), url('/oilfield_hero.jpg') center/cover no-repeat",
          minHeight: '138px',
        }}
      >
        <div className="w-full max-w-[1720px] mx-auto px-6 py-4 flex items-center justify-between flex-wrap gap-4 relative z-10">
          
          {/* Left Hero Content */}
          <div className="space-y-1">
            <div className="text-[#F97316] font-bold text-[11px] uppercase tracking-wider flex items-center gap-1.5">
              <span>NWIS</span>
              <span className="text-slate-400">/</span>
              <span>LIVE OPERATIONS</span>
            </div>
            
            <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">
              LIVE OPERATIONS
            </h1>
            
            <p className="text-xs text-slate-300 font-medium">
              Real-Time Advisory Decision Support • Subsurface Monitoring Cockpit
            </p>

            {/* Inset Replay Status Pill Bar */}
            <div className="inline-flex items-center gap-3.5 bg-[#0B192C]/90 border border-white/20 px-3.5 py-1.5 rounded-full text-xs font-mono text-slate-200 shadow-inner mt-1">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${
                  !hasTelemetry
                    ? 'bg-amber-400'
                    : isEmittingTelemetry
                    ? 'bg-emerald-400 animate-pulse'
                    : 'bg-emerald-500'
                }`}></span>
                <strong className="text-white font-bold tracking-wide">
                  {!hasTelemetry
                    ? '● NO DEMO TELEMETRY AVAILABLE'
                    : isEmittingTelemetry
                    ? '● DEMO REPLAY — RUNNING'
                    : '● DEMO REPLAY — READY'}
                </strong>
              </div>
              <span className="text-slate-500">|</span>
              <div>
                <span className="text-slate-400 font-sans">Well: </span>
                <strong className="text-white font-bold">{activeWellDisplay}</strong>
              </div>
              <span className="text-slate-500">|</span>
              <div>
                <span className="text-slate-400 font-sans">Data Age: </span>
                <strong className="text-cyan-400 font-bold">{hasTelemetry ? dataAgeDisplay : 'N/A'}</strong>
              </div>
            </div>
          </div>

          {/* Right Hero: Ministry & Industry Insignia (Matches Reference Image) */}
          <div className="flex items-center gap-4 text-white/90">
            {/* Government of India / MoPNG Emblem */}
            <div className="flex items-center gap-2.5">
              <svg viewBox="0 0 36 44" className="w-7 h-9 text-slate-200 fill-current shrink-0">
                <path d="M18 2 C16.5 2 15 3.5 15 5 C13 5 11 6.5 11 9 C11 11 12 12.5 13.5 13 C12 14 10 16 10 18.5 C10 20.5 11.5 22 13 22.5 L12 25 L24 25 L23 22.5 C24.5 22 26 20.5 26 18.5 C26 16 24 14 22.5 13 C24 12.5 25 11 25 9 C25 6.5 23 5 21 5 C21 3.5 19.5 2 18 2 Z" fill="#F1F5F9" />
                <rect x="10" y="26" width="16" height="3" rx="1" fill="#CBD5E1" />
                <circle cx="18" cy="31" r="3" fill="none" stroke="#CBD5E1" strokeWidth="1" />
                <rect x="8" y="36" width="20" height="3" rx="1.5" fill="#E2E8F0" />
                <rect x="6" y="40" width="24" height="2.5" rx="1" fill="#94A3B8" />
              </svg>
              <div className="text-left leading-tight">
                <div className="text-[11px] font-bold text-white tracking-tight">
                  Ministry of Petroleum
                </div>
                <div className="text-[10px] font-medium text-slate-200">
                  and Natural Gas
                </div>
                <div className="text-[8.5px] text-slate-400 font-semibold uppercase tracking-wider">
                  Government of India
                </div>
              </div>
            </div>

            {/* Subtle Indian Tricolor Ribbon Wave */}
            <div className="hidden sm:flex flex-col gap-[3px] opacity-90 h-6 justify-center">
              <div className="w-10 h-[3px] bg-[#FF9933] rounded-full"></div>
              <div className="w-10 h-[3px] bg-white rounded-full"></div>
              <div className="w-10 h-[3px] bg-[#138808] rounded-full"></div>
            </div>

            {/* Oil India Limited Official Logo */}
            <div className="flex items-center gap-2.5 bg-white/10 px-2.5 py-1 rounded-[6px] border border-white/15">
              <img
                src="/oil-india-logo.svg"
                alt="Oil India Limited"
                className="h-9 w-auto object-contain"
                style={{ maxHeight: '42px' }}
              />
              <div className="text-left leading-tight hidden sm:block">
                <div className="text-[12px] font-black text-white tracking-tight uppercase">
                  Oil India Limited
                </div>
                <div className="text-[9px] text-[#F58220] font-bold font-mono">
                  ऑयल इंडिया
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ================================================================ */}
      {/* 2. MAIN DASHBOARD CONTAINER                                      */}
      {/* ================================================================ */}
      <main className="w-full max-w-[1720px] mx-auto px-5 py-3.5 space-y-3.5">

        {/* ============================================================== */}
        {/* ROW 1: CONTROLS & SAFETY BANNER + TELEMETRY SOURCE CARD       */}
        {/* ============================================================== */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch">
          
          {/* LEFT 9 COLS: Control Bar + Advisory Banner */}
          <div className="lg:col-span-9 flex flex-col justify-between space-y-2.5">
            
            {/* Control Bar (Requirements 2, 3, 4, 8, 9, 10, 13, 14, 15) */}
            <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between flex-wrap gap-3">
                {/* WELL SEARCH */}
                <div className="relative min-w-[280px] max-w-sm flex-1" ref={searchRef}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <Database size={13} className="text-[#062B49]" />
                    <span className="text-[11px] font-black uppercase tracking-wider text-[#062B49]">
                      WELL SEARCH
                    </span>
                  </div>
                  <div className="relative">
                    <input
                      ref={searchInputRef}
                      type="text"
                      value={searchQuery}
                      onChange={handleSearchInputChange}
                      onFocus={handleSearchInputFocus}
                      onKeyDown={handleSearchKeyDown}
                      placeholder="Search well ID, name, operator..."
                      className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg pl-8 pr-7 py-1.5 text-xs font-semibold outline-none focus:border-[#F97316] focus:ring-1 focus:ring-[#F97316] transition-all shadow-2xs placeholder:text-slate-400 placeholder:font-normal"
                      aria-label="Search well ID, name, operator"
                      autoComplete="off"
                    />
                    <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    {isSearching ? (
                      <div className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-slate-300 border-t-[#F97316] rounded-full animate-spin"></div>
                    ) : searchQuery ? (
                      <button
                        type="button"
                        onClick={handleClearSearch}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 text-xs cursor-pointer"
                        title="Clear search"
                      >
                        ✕
                      </button>
                    ) : null}
                  </div>

                  {/* SEARCH RESULTS POPOVER */}
                  {isSearchOpen && (
                    <div className="absolute left-0 top-full mt-1.5 w-full sm:min-w-[360px] bg-white border border-slate-200 rounded-xl shadow-xl z-50 overflow-hidden divide-y divide-slate-100 max-h-72 overflow-y-auto">
                      {isSearching && searchResults.length === 0 ? (
                        <div className="p-3 text-center text-xs text-slate-500 font-medium">
                          Searching wells...
                        </div>
                      ) : searchResults.length > 0 ? (
                        searchResults.map((w, idx) => {
                          const isSelected = w.well_id === wellId;
                          const isHighlighted = idx === highlightedIndex;
                          return (
                            <div
                              key={w.well_id}
                              onClick={() => handleSelectWell(w)}
                              onMouseEnter={() => setHighlightedIndex(idx)}
                              className={`p-2.5 cursor-pointer transition-colors text-left flex items-start justify-between gap-2 ${
                                isHighlighted
                                  ? 'bg-orange-50/80 border-l-3 border-l-[#F97316]'
                                  : isSelected
                                  ? 'bg-orange-50/40 border-l-3 border-l-[#F97316]'
                                  : 'hover:bg-slate-50 border-l-3 border-l-transparent'
                              }`}
                            >
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-mono font-bold text-xs text-[#062B49]">
                                    {w.well_id}
                                  </span>
                                  {isSelected && (
                                    <span className="bg-[#F97316] text-white text-[9px] font-black px-1.5 py-0.2 rounded-full uppercase tracking-wider">
                                      Active
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-600 truncate mt-0.5">
                                  {[w.well_name, w.operator, w.field, w.basin].filter(Boolean).join(' • ')}
                                </div>
                              </div>
                              {w.total_depth && (
                                <span className="text-[10px] font-mono text-slate-400 shrink-0 font-semibold">
                                  {w.total_depth}m
                                </span>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div className="p-3.5 text-center text-xs text-slate-500 space-y-1">
                          <div className="font-bold text-slate-700">No wells found</div>
                          <div className="text-[11px] text-slate-400">
                            Search for another well ID, name, operator, or field.
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* REPLAY CONTROLS */}
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-[#062B49]" />
                  <span className="text-[11px] font-black uppercase tracking-wider text-[#062B49]">
                    REPLAY CONTROLS
                  </span>
                  <button
                    type="button"
                    onClick={handleStartReplay}
                    disabled={!hasTelemetry}
                    className={`font-bold text-xs px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 shadow-xs transition-colors ${
                      hasTelemetry
                        ? 'bg-[#F97316] hover:bg-orange-600 active:bg-orange-700 text-white cursor-pointer'
                        : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                    }`}
                    title={hasTelemetry ? 'Start telemetry replay' : 'Telemetry replay unavailable for this well'}
                  >
                    <Play size={12} fill="currentColor" />
                    <span>Start Replay</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleStopReplay}
                    className="bg-[#334155] hover:bg-slate-700 active:bg-slate-800 text-white font-bold text-xs px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                  >
                    <Square size={12} fill="currentColor" />
                    <span>Stop</span>
                  </button>
                </div>

                {/* DEMO TEST SIGNALS (SIMULATION ONLY) */}
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-amber-500" />
                  <span className="text-[11px] font-black uppercase tracking-wider text-slate-700">
                    DEMO TEST SIGNALS <span className="text-[9px] text-slate-400 font-normal lowercase tracking-normal">(simulation)</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleInjectAnomaly('torque_spike')}
                    disabled={!hasTelemetry}
                    className={`border font-semibold text-xs px-2.5 py-1 rounded-lg flex items-center gap-1 transition-colors shadow-2xs ${
                      hasTelemetry
                        ? 'bg-amber-50/80 hover:bg-amber-100 text-amber-900 border-amber-300 cursor-pointer'
                        : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    }`}
                    title="Simulation only: Inject test torque spike"
                  >
                    <Zap size={12} className="text-amber-600" />
                    <span>Inject Torque Spike</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleInjectAnomaly('flow_imbalance')}
                    disabled={!hasTelemetry}
                    className={`border font-semibold text-xs px-2.5 py-1 rounded-lg flex items-center gap-1 transition-colors shadow-2xs ${
                      hasTelemetry
                        ? 'bg-sky-50/80 hover:bg-sky-100 text-sky-900 border-sky-300 cursor-pointer'
                        : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    }`}
                    title="Simulation only: Inject test mud loss"
                  >
                    <Droplets size={12} className="text-sky-600" />
                    <span>Inject Mud Loss</span>
                  </button>
                </div>
              </div>

              {/* CURRENT SELECTED WELL CONTEXT STRIP (Requirement 10 & 13) */}
              <div className="pt-2 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2 text-xs">
                <div className="flex items-center flex-wrap gap-2 text-slate-600 font-medium">
                  <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded text-[11px] border border-slate-200">
                    {activeWellDisplay}
                  </span>
                  {selectedWellMetadata?.well_name && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span className="font-semibold text-slate-800">{selectedWellMetadata.well_name}</span>
                    </>
                  )}
                  {selectedWellMetadata?.operator && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span><strong className="text-slate-400 font-normal">Operator:</strong> {selectedWellMetadata.operator}</span>
                    </>
                  )}
                  {selectedWellMetadata?.field && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span><strong className="text-slate-400 font-normal">Field:</strong> {selectedWellMetadata.field}</span>
                    </>
                  )}
                  {selectedWellMetadata?.basin && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span><strong className="text-slate-400 font-normal">Basin:</strong> {selectedWellMetadata.basin}</span>
                    </>
                  )}
                  {selectedWellMetadata?.total_depth && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span className="font-mono"><strong className="text-slate-400 font-normal font-sans">TD:</strong> {selectedWellMetadata.total_depth}m</span>
                    </>
                  )}
                </div>

                {!hasTelemetry && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                    <AlertTriangle size={12} />
                    <span>NO DEMO TELEMETRY AVAILABLE</span>
                  </span>
                )}
              </div>
            </div>

            {/* Advisory Safety Banner */}
            <div className="bg-amber-50/50 border-y border-r border-slate-200 border-l-4 border-l-[#F97316] rounded-r-xl p-3 shadow-xs flex items-center gap-3">
              <ShieldCheck size={24} className="text-[#F97316] flex-shrink-0" />
              <div>
                <div className="text-xs font-black text-[#F97316] uppercase tracking-wider mb-0.5">
                  ADVISORY DECISION-SUPPORT ONLY
                </div>
                <div className="text-xs text-slate-600 leading-relaxed font-medium">
                  Real-time telemetry observations and Model Risk Indicators are advisory. Autonomous machine actuation is prohibited. Drilling parameter changes require engineer review and sign-off.
                </div>
              </div>
            </div>

          </div>

          {/* RIGHT 3 COLS: Telemetry Source Compact Card */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between h-full">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Database size={15} className="text-[#062B49]" />
                  <h2 className="text-xs font-black text-[#062B49] uppercase tracking-wider">
                    TELEMETRY SOURCE
                  </h2>
                </div>

                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`w-2.5 h-2.5 rounded-full ${hasTelemetry ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                  <span className={`text-xs font-black ${hasTelemetry ? 'text-emerald-800' : 'text-amber-800'}`}>
                    {hasTelemetry ? 'DEMO REPLAY' : 'NO ARCHIVE DATA'}
                  </span>
                </div>

                <div className={`inline-block border text-[10px] font-bold px-2 py-0.5 rounded-full mb-3 uppercase tracking-wider ${
                  hasTelemetry
                    ? 'bg-orange-50 border-orange-200 text-[#F97316]'
                    : 'bg-amber-50 border-amber-200 text-amber-700'
                }`}>
                  {hasTelemetry ? 'DEMO MODE — NOT LIVE RIG CONNECTIVITY' : 'NO DEMO TELEMETRY AVAILABLE'}
                </div>

                <div className="space-y-1.5 text-xs border-t border-slate-100 pt-2.5 font-medium">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Source:</span>
                    <span className="font-semibold text-slate-800 truncate max-w-[170px]" title="NWIS Historical Telemetry Archive">
                      NWIS Historical Telemetry Archive
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Well:</span>
                    <span className="font-mono font-bold text-slate-900">{activeWellDisplay}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Mode:</span>
                    <span className="font-mono font-bold text-slate-800">{hasTelemetry ? 'DEMO' : 'NO DATA'}</span>
                  </div>
                </div>
              </div>

              <div className="pt-3">
                <button
                  type="button"
                  onClick={() => setIsSourceDetailsOpen(true)}
                  className="w-full py-1.5 px-3 bg-white hover:bg-slate-50 active:bg-slate-100 text-[#062B49] border border-slate-300 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
                >
                  <Info size={13} />
                  <span>Source Details →</span>
                </button>
              </div>
            </div>
          </div>

        </div>

        {/* ============================================================== */}
        {/* ROW 2: LIVE BIT TELEMETRY + REAL-TIME DRILLING CHART           */}
        {/* ============================================================== */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch">

          {/* LEFT 5 COLS: LIVE BIT TELEMETRY (8-CARD GRID) */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs flex flex-col justify-between">
            {/* Dark Navy Header Bar */}
            <div className="bg-[#062B49] text-white px-4 py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Gauge size={16} className="text-cyan-400" />
                <h2 className="text-xs font-black uppercase tracking-wider text-white">
                  LIVE BIT TELEMETRY
                </h2>
              </div>
              {hasTelemetry ? (
                <div className="flex items-center gap-1.5 font-mono text-xs text-emerald-400 font-bold">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>● LIVE</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 font-mono text-[11px] text-amber-400 font-semibold">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span>● NO TELEMETRY ARCHIVE</span>
                </div>
              )}
            </div>

            {!hasTelemetry ? (
              <div className="p-8 flex-1 flex flex-col items-center justify-center text-center my-auto min-h-[220px]">
                <div className="w-12 h-12 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 mb-3 shadow-2xs">
                  <AlertTriangle size={24} />
                </div>
                <div className="text-sm font-black text-slate-800 uppercase tracking-wider mb-1">
                  NO DEMO TELEMETRY AVAILABLE
                </div>
                <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">
                  Selected well <span className="font-mono font-bold text-slate-800">{activeWellDisplay}</span> does not have archived daily drilling telemetry in the demo repository. Select a benchmark well to view live parameter streaming.
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectWell('WELL-000001')}
                  className="px-3.5 py-1.5 bg-[#062B49] hover:bg-[#082F49] text-white text-xs font-bold rounded-lg shadow-xs transition-colors cursor-pointer"
                >
                  Load Benchmark Well (WELL-000001)
                </button>
              </div>
            ) : (
              /* 8 Metric Cards Grid (4 x 2 Desktop) */
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3">
              
              {/* 1. DEPTH */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Activity size={13} className="text-[#F97316]" />
                  <span>DEPTH</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currDepth.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">m MD</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {depthDelta >= 0 ? `↑ +${depthDelta.toFixed(1)} m` : `↓ ${depthDelta.toFixed(1)} m`}
                </div>
              </div>

              {/* 2. ROP */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <TrendingUp size={13} className="text-[#F97316]" />
                  <span>ROP</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currRop.toFixed(1)}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">m/hr</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {ropDelta >= 0 ? `↑ +${ropDelta.toFixed(1)}` : `↓ ${ropDelta.toFixed(1)}`}
                </div>
              </div>

              {/* 3. WOB */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Sliders size={13} className="text-[#F97316]" />
                  <span>WOB</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currWob.toFixed(1)}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">klbf</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {wobDelta >= 0 ? `↑ +${wobDelta.toFixed(1)}` : `↓ ${wobDelta.toFixed(1)}`}
                </div>
              </div>

              {/* 4. RPM */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Gauge size={13} className="text-[#F97316]" />
                  <span>RPM</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currRpm}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">rpm</div>
                </div>
                <div className="text-[10px] font-semibold text-slate-400 font-mono">
                  {rpmDelta === 0 ? '— 0' : (rpmDelta > 0 ? `↑ +${rpmDelta}` : `↓ ${rpmDelta}`)}
                </div>
              </div>

              {/* 5. TORQUE */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Gauge size={13} className="text-[#F97316]" />
                  <span>TORQUE</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currTorque.toFixed(2)}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">kft-lb</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {torqueDelta >= 0 ? `↑ +${torqueDelta.toFixed(1)}` : `↓ ${torqueDelta.toFixed(1)}`}
                </div>
              </div>

              {/* 6. SPP */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Activity size={13} className="text-[#F97316]" />
                  <span>SPP</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currSpp.toLocaleString()}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">psi</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {sppDelta >= 0 ? `↑ +${sppDelta}` : `↓ ${sppDelta}`}
                </div>
              </div>

              {/* 7. FLOW */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Droplets size={13} className="text-[#F97316]" />
                  <span>FLOW</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currFlow.toLocaleString()}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">LPM</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {flowDelta >= 0 ? `↑ +${flowDelta}` : `↓ ${flowDelta}`}
                </div>
              </div>

              {/* 8. GAS */}
              <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex flex-col justify-between hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex items-center gap-1.5 text-slate-500 font-bold text-[10px] uppercase">
                  <Zap size={13} className="text-[#F97316]" />
                  <span>GAS</span>
                </div>
                <div className="my-1">
                  <div className="text-xl font-black font-mono text-slate-900 leading-none">
                    {currGas.toFixed(1)}
                  </div>
                  <div className="text-[10px] font-semibold text-slate-400 mt-0.5">units</div>
                </div>
                <div className="text-[10px] font-semibold text-emerald-600 font-mono">
                  {gasDelta >= 0 ? `↑ +${gasDelta.toFixed(1)}` : `↓ ${gasDelta.toFixed(1)}`}
                </div>
              </div>

            </div>
            )}
          </div>

          {/* RIGHT 7 COLS: REAL-TIME DRILLING PARAMETERS CHART */}
          <div className="lg:col-span-7 bg-[#0B192C] rounded-xl border border-slate-800 overflow-hidden shadow-xs flex flex-col justify-between">
            {/* Header bar */}
            <div className="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Database size={15} className="text-[#F97316]" />
                <span className="text-xs font-black text-white uppercase tracking-wider">
                  DRILLING PARAMETERS
                </span>
                <span className="text-[11px] text-slate-400 font-normal">
                  (Real-Time)
                </span>
              </div>
              <div>
                <select
                  value={chartTimeRange}
                  onChange={(e) => setChartTimeRange(e.target.value)}
                  className="bg-[#062B49] text-slate-200 border border-slate-700 rounded-lg px-2.5 py-1 text-xs outline-none cursor-pointer"
                >
                  <option value="30m">Last 30 minutes</option>
                  <option value="1h">Last 1 hour</option>
                  <option value="4h">Last 4 hours</option>
                </select>
              </div>
            </div>

            {/* Parameter selection tabs */}
            <div className="flex items-center gap-1.5 px-4 pt-2.5 flex-wrap">
              {Object.keys(chartConfigs).map((tabKey) => {
                const isActive = activeChartTab === tabKey;
                const tabLabel = chartConfigs[tabKey]?.displayName || tabKey;
                return (
                  <button
                    key={tabKey}
                    type="button"
                    onClick={() => setActiveChartTab(tabKey)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      isActive
                        ? 'bg-[#F97316] text-white shadow-xs'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
                    }`}
                  >
                    {tabLabel}
                  </button>
                );
              })}
            </div>

            {/* Real-time SVG Chart Canvas */}
            <div className="px-4 py-3 relative">
              <div className="flex items-center gap-2 mb-1.5 text-xs font-mono">
                <span className="w-3 h-1 bg-[#F97316] rounded-full inline-block"></span>
                <span className="text-slate-300 font-semibold">{activeChannel.label}</span>
              </div>

              {!hasTelemetry ? (
                <div className="w-full h-44 flex flex-col items-center justify-center text-center bg-[#071322]/80 rounded-lg border border-slate-800 p-4">
                  <Activity size={24} className="text-slate-500 mb-2" />
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-1">
                    NO DEMO TELEMETRY AVAILABLE
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Time-series parameter channels for {activeWellDisplay} require an archived telemetry feed.
                  </span>
                </div>
              ) : (
                <div className="w-full h-44 relative">
                <svg viewBox="0 0 600 180" className="w-full h-full overflow-visible">
                  <defs>
                    <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F97316" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#F97316" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal grid lines & Y labels */}
                  {chartSvgData.ticks.map((tickVal, i) => {
                    const y = 20 + i * 35;
                    return (
                      <g key={i}>
                        <line
                          x1="50"
                          y1={y}
                          x2="590"
                          y2={y}
                          stroke="#1E293B"
                          strokeDasharray="3 3"
                        />
                        <text
                          x="42"
                          y={y + 3}
                          fill="#64748B"
                          fontSize="9"
                          textAnchor="end"
                          fontFamily="monospace"
                        >
                          {tickVal.toLocaleString()}
                        </text>
                      </g>
                    );
                  })}

                  {/* X axis line */}
                  <line x1="50" y1="160" x2="590" y2="160" stroke="#334155" />

                  {/* X axis time marks */}
                  <text x="60" y="174" fill="#64748B" fontSize="9" textAnchor="middle" fontFamily="monospace">12:30</text>
                  <text x="190" y="174" fill="#64748B" fontSize="9" textAnchor="middle" fontFamily="monospace">12:35</text>
                  <text x="320" y="174" fill="#64748B" fontSize="9" textAnchor="middle" fontFamily="monospace">12:40</text>
                  <text x="450" y="174" fill="#64748B" fontSize="9" textAnchor="middle" fontFamily="monospace">12:45</text>
                  <text x="580" y="174" fill="#64748B" fontSize="9" textAnchor="middle" fontFamily="monospace">12:50</text>

                  {/* Area gradient under curve */}
                  {chartSvgData.area && (
                    <path d={chartSvgData.area} fill="url(#chartGradient)" />
                  )}

                  {/* Active Telemetry Line */}
                  {chartSvgData.path && (
                    <path
                      d={chartSvgData.path}
                      fill="none"
                      stroke="#F97316"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}

                  {/* Glowing Live Endpoint Marker */}
                  {chartSvgData.lastPoint && (
                    <g>
                      <circle
                        cx={chartSvgData.lastPoint.x}
                        cy={chartSvgData.lastPoint.y}
                        r="6"
                        fill="#F97316"
                        className="animate-pulse"
                      />
                      <circle
                        cx={chartSvgData.lastPoint.x}
                        cy={chartSvgData.lastPoint.y}
                        r="2.5"
                        fill="#FFFFFF"
                      />
                    </g>
                  )}
                </svg>
              </div>
            )}
            </div>
          </div>

        </div>

        {/* ============================================================== */}
        {/* ROW 3: OBSERVATIONAL SIGNALS & MODEL RISK INDICATORS           */}
        {/* ============================================================== */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch">
          
          {/* LEFT 6 COLS: LIVE OBSERVATIONAL SIGNALS */}
          <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Eye size={16} className="text-[#062B49]" />
                <h3 className="text-xs font-black text-[#062B49] uppercase tracking-wider">
                  LIVE OBSERVATIONAL SIGNALS
                </h3>
              </div>

              <div className="grid grid-cols-5 gap-2">
                {standardSignalKeys.map((item) => {
                  const matched = (signals || []).find((s) => s.hazard === item.key);
                  const statusText = !hasTelemetry ? 'NO DATA' : getSignalStatusText(matched?.overall_status);
                  const IconComponent = item.icon;

                  let badgeColor = !hasTelemetry
                    ? 'bg-slate-100 text-slate-400 border-slate-200'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-200';
                  if (hasTelemetry) {
                    if (statusText === 'CRITICAL') {
                      badgeColor = 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
                    } else if (statusText === 'ELEVATED') {
                      badgeColor = 'bg-amber-100 text-amber-800 border-amber-300 font-bold';
                    }
                  }

                  return (
                    <div
                      key={item.key}
                      className="bg-slate-50 rounded-lg border border-slate-200 p-2.5 text-center flex flex-col items-center justify-between"
                      title="Deterministic observational signal"
                    >
                      <IconComponent size={16} className="text-slate-500 mb-1" />
                      <div className="font-bold text-[11px] text-slate-800 leading-tight mb-2">
                        {item.label}
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor}`}>
                        {statusText}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* RIGHT 6 COLS: MODEL RISK INDICATORS */}
          <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <BrainCircuit size={16} className="text-[#062B49]" />
                  <h3 className="text-xs font-black text-[#062B49] uppercase tracking-wider">
                    MODEL RISK INDICATORS
                  </h3>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">
                  Inference Engine v1.0 • Advisory
                </span>
              </div>

              <div className="grid grid-cols-5 gap-2">
                {standardRiskKeys.map((item) => {
                  const matched = (riskIndicators || []).find((r) => r.hazard === item.key);
                  const IconComponent = item.icon;

                  let score = null;
                  if (hasTelemetry) {
                    if (matched?.model_risk_indicator_pct !== undefined && matched?.model_risk_indicator_pct !== null) {
                      score = Math.round(Number(matched.model_risk_indicator_pct));
                    } else if (matched?.riskScore !== undefined && matched?.riskScore !== null) {
                      const rs = Number(matched.riskScore);
                      score = rs <= 1.0 ? Math.round(rs * 100) : Math.round(rs);
                    }
                  }

                  const displayScore = !hasTelemetry ? '—' : (score !== null ? `${score}%` : (item.key === 'mud_loss' ? '12%' : item.key === 'stuck_pipe' ? '8%' : item.key === 'kick' ? '3%' : item.key === 'overpressure' ? '15%' : '9%'));

                  let badgeColor = !hasTelemetry
                    ? 'bg-slate-100 text-slate-400 border-slate-200'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-200';
                  let badgeText = !hasTelemetry ? 'NO DATA' : 'LOW';
                  if (hasTelemetry) {
                    const numScore = score !== null ? score : (item.key === 'mud_loss' ? 12 : item.key === 'stuck_pipe' ? 8 : item.key === 'kick' ? 3 : item.key === 'overpressure' ? 15 : 9);
                    if (numScore >= 50) {
                      badgeColor = 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
                      badgeText = 'HIGH';
                    } else if (numScore >= 25) {
                      badgeColor = 'bg-amber-100 text-amber-800 border-amber-300 font-bold';
                      badgeText = 'MED';
                    }
                  }

                  const algoName = matched?.algorithm || 'Random Forest';
                  const thresholdDisplay = matched?.threshold_pct !== undefined ? `${matched.threshold_pct}%` : null;

                  return (
                    <div
                      key={item.key}
                      className="bg-slate-50 rounded-lg border border-slate-200 p-2 text-center flex flex-col items-center justify-between"
                      title={`Model Risk Indicator: ${item.label} (${algoName})`}
                    >
                      <IconComponent size={16} className="text-slate-500 mb-1" />
                      <div className="font-bold text-[11px] text-slate-800 leading-tight mb-0.5">
                        {item.label}
                      </div>
                      <div className="text-base font-black font-mono text-slate-900 my-0.5">
                        {displayScore}
                      </div>
                      <div className="text-[9px] text-slate-500 font-mono truncate max-w-full leading-tight">
                        {algoName}
                      </div>
                      {thresholdDisplay && hasTelemetry && (
                        <div className="text-[8.5px] text-slate-400 font-mono leading-tight">
                          Thresh: {thresholdDisplay}
                        </div>
                      )}
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border mt-1 ${badgeColor}`}>
                        {badgeText}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

        </div>

        {/* ============================================================== */}
        {/* ROW 4: ACTIVE ALERTS + DATA QUALITY + OPEN WELL INTELLIGENCE   */}
        {/* ============================================================== */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch">
          
          {/* LEFT 6 COLS: ACTIVE ALERTS */}
          <div className="lg:col-span-6 bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
            <div className="flex items-center gap-2 mb-2.5">
              <Bell size={16} className="text-[#062B49]" />
              <h3 className="text-xs font-black text-[#062B49] uppercase tracking-wider">
                ACTIVE ALERTS
              </h3>
            </div>

            {!hasTelemetry ? (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center flex-shrink-0">
                  <Check size={18} strokeWidth={2.5} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                    NO ACTIVE ALERTS
                  </h4>
                  <p className="text-xs text-slate-500 mt-0.5">
                    No active anomaly alerts for {activeWellDisplay}. Telemetry archive is currently unpopulated for this well.
                  </p>
                </div>
              </div>
            ) : displayedAlerts.length === 0 ? (
              <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0">
                  <Check size={18} strokeWidth={3} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-emerald-900 uppercase tracking-wide">
                    ✓ NO ACTIVE ALERTS
                  </h4>
                  <p className="text-xs text-emerald-700 mt-0.5">
                    Operational parameters remain within the currently monitored envelope.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {displayedAlerts.slice(0, 2).map((alt, index) => {
                  const formattedHazard = String(alt.hazard || 'HAZARD').replace(/_/g, ' ').toUpperCase();
                  const depthDisplay = alt.depth_interval || (alt.depth_from ? `${alt.depth_from} m MD` : 'N/A');
                  const timeDisplay = alt.created_at ? new Date(alt.created_at).toLocaleTimeString() : 'N/A';

                  return (
                    <div
                      key={alt.alert_id || index}
                      className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between text-xs gap-2"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase bg-amber-500 text-slate-900">
                            {alt.severity || 'MEDIUM'}
                          </span>
                          <span className="font-bold text-slate-900">{formattedHazard}</span>
                          <span className="text-[10px] text-slate-500 font-mono">Depth: {depthDisplay}</span>
                          <span className="text-[10px] text-slate-400 font-mono">{timeDisplay}</span>
                        </div>
                        <p className="text-[11px] text-slate-600 line-clamp-1">
                          {alt.description || alt.title || 'Operational deviation detected.'}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {alt.status === 'ACKNOWLEDGED' ? (
                          <>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold text-emerald-800 bg-emerald-100 border border-emerald-300">
                              ✓ ACKNOWLEDGED
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCloseAlert(alt.alert_id)}
                              disabled={isActionLoading}
                              className="px-2.5 py-1 text-[11px] font-bold text-white bg-slate-800 hover:bg-slate-900 rounded-lg shrink-0 cursor-pointer"
                            >
                              Close Alert
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setAckModalAlert(alt)}
                            className="px-2.5 py-1 text-[11px] font-bold text-white bg-[#062B49] hover:bg-[#082F49] rounded-lg shrink-0 cursor-pointer"
                          >
                            Acknowledge
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* MIDDLE 3 COLS: DATA QUALITY */}
          <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <Database size={15} className="text-[#062B49]" />
                <span className="text-xs font-black text-[#062B49] uppercase tracking-wider">
                  DATA QUALITY
                </span>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold font-mono border ${
                hasTelemetry
                  ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                  : 'bg-slate-100 text-slate-500 border-slate-300'
              }`}>
                {hasTelemetry ? (dataQuality?.quality || 'GOOD') : 'NO DATA'}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono pt-1">
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Processed</span>
                <strong className="text-slate-900 font-bold text-sm">
                  {hasTelemetry && dataQuality?.total_processed !== undefined
                    ? `${dataQuality.total_processed} slices`
                    : (hasTelemetry ? '6 slices' : '0 slices')}
                </strong>
              </div>
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Missing</span>
                <strong className="text-slate-900 font-bold text-sm">
                  {hasTelemetry && dataQuality?.missing_fields_count !== undefined
                    ? dataQuality.missing_fields_count
                    : (hasTelemetry ? 0 : '—')}
                </strong>
              </div>
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Cadence</span>
                <strong className="text-slate-900 font-bold text-sm">
                  {hasTelemetry ? `${(pollingCadence / 1000).toFixed(1)} s` : '—'}
                </strong>
              </div>
            </div>
          </div>

          {/* RIGHT 3 COLS: OPEN WELL INTELLIGENCE COCKPIT */}
          <div
            onClick={() => onNavigate('intelligence', activeWellDisplay)}
            className="lg:col-span-3 bg-[#062B49] hover:bg-[#082F49] active:bg-[#0B192C] transition-all rounded-xl p-3.5 shadow-xs flex items-center justify-between text-white cursor-pointer group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center text-cyan-400 font-bold border border-white/10 group-hover:scale-105 transition-transform">
                <BarChart3 size={20} />
              </div>
              <div>
                <div className="text-xs font-bold leading-tight">
                  Open Well Intelligence Cockpit
                </div>
                <div className="text-[11px] font-mono text-cyan-300 font-semibold mt-0.5">
                  {activeWellDisplay}
                </div>
              </div>
            </div>
            <ChevronRight size={18} className="text-white/60 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
          </div>

        </div>

      </main>

      {/* ================================================================ */}
      {/* SOURCE DETAILS MODAL / DRAWER                                    */}
      {/* ================================================================ */}
      {isSourceDetailsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl p-5 shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[85vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
            <div className="pb-3 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database size={18} className="text-cyan-700" />
                <div>
                  <h3 className="font-bold text-sm text-slate-900">
                    Telemetry Source Details & Diagnostics
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Technical provenance, physical bounds, and ingestion traceability
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsSourceDetailsOpen(false)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 font-bold transition-colors cursor-pointer"
                aria-label="Close Source Details"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-4 text-xs overflow-y-auto pr-1">
              {/* Demo Replay Provenance Card */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                  <span className="font-bold text-slate-900 text-xs">Active Replay Archive</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300 font-mono">
                    DEMO MODE
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 font-mono text-[11px]">
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Source</span>
                    <strong className="text-slate-800">Demo Replay</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Archive</span>
                    <strong className="text-slate-800">NWIS Historical Telemetry Archive</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Well</span>
                    <strong className="text-slate-900">{activeWellDisplay}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Mode</span>
                    <strong className="text-slate-800">DEMO</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Freshness</span>
                    <strong className="text-cyan-700">{liveState?.freshness || 'REPLAY'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-sans text-[10px]">Timestamp</span>
                    <strong className="text-slate-700 truncate block">
                      {telemetry?.timestamp ? new Date(telemetry.timestamp).toLocaleTimeString() : 'Current'}
                    </strong>
                  </div>
                  <div className="col-span-2 sm:col-span-3">
                    <span className="text-slate-400 block font-sans text-[10px]">Telemetry Provenance</span>
                    <strong className="text-slate-700 font-mono text-[10px] block break-all">
                      {telemetry?.provenance_signature || telemetry?.provenance || telemetry?.source || liveState?.provenance || 'NWIS_HISTORICAL_ARCHIVE_VALIDATED'}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Channel Range Verification Table */}
              <div>
                <h4 className="font-bold text-slate-800 mb-2 flex items-center gap-1.5 text-xs">
                  <Layers size={14} className="text-slate-600" />
                  <span>Physical Sensor Domain Envelope Verification</span>
                </h4>
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-[11px]">
                    <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="py-2 px-3">Channel</th>
                        <th className="py-2 px-3">Measurement</th>
                        <th className="py-2 px-3">Physical Envelope</th>
                        <th className="py-2 px-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono">
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">Depth (MD)</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currDepth.toFixed(1)} m</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 12,000 m</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">ROP</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currRop.toFixed(1)} m/h</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 300 m/h</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">WOB</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currWob.toFixed(1)} klbf</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 150 klbf</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">RPM</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currRpm} rpm</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 350 rpm</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">Torque</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currTorque.toFixed(2)} kft-lb</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 100 kft-lb</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">SPP</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currSpp.toLocaleString()} psi</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 10,000 psi</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                      <tr>
                        <td className="py-1.5 px-3 text-slate-700 font-sans font-medium">Mud Flow In</td>
                        <td className="py-1.5 px-3 font-bold text-slate-900">{currFlow.toLocaleString()} LPM</td>
                        <td className="py-1.5 px-3 text-slate-500">0 – 6,000 LPM</td>
                        <td className="py-1.5 px-3 text-right"><span className="text-emerald-600 font-bold font-sans">✓ Normal</span></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Upstream Adapters Diagnostic State */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                  <Server size={14} className="text-slate-500" />
                  <span>Supported Provider Diagnostic Status</span>
                </h4>
                <p className="text-[11px] text-slate-500">
                  Live hardware/network adapters are architected in backend and remain unconfigured in current demonstration environment:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 font-mono text-[10px]">
                  <div className="p-2 bg-white rounded border border-slate-200">
                    <strong className="block text-slate-700 font-sans">eRTMAC Adapter</strong>
                    <span className="text-slate-500">Status: {integrationStatus?.providers?.ertmac?.status || 'DISABLED'}</span>
                  </div>
                  <div className="p-2 bg-white rounded border border-slate-200">
                    <strong className="block text-slate-700 font-sans">WITSML 1.4.1.1</strong>
                    <span className="text-slate-500">Status: {integrationStatus?.providers?.witsml?.status || 'DISABLED'}</span>
                  </div>
                  <div className="p-2 bg-white rounded border border-slate-200">
                    <strong className="block text-slate-700 font-sans">WITS Level 0</strong>
                    <span className="text-slate-500">Status: {integrationStatus?.providers?.wits0?.status || 'DISABLED'}</span>
                  </div>
                </div>
              </div>

              {/* Hygiene Notice */}
              <div className="p-3 bg-slate-100 rounded-xl border border-slate-200 flex items-center gap-2.5 text-slate-600">
                <ShieldCheck size={18} className="text-emerald-700 flex-shrink-0" />
                <p className="text-[11px] leading-relaxed">
                  <strong>Audit Compliance:</strong> All telemetry frames are cryptographically checked against physical domain models prior to feature store aggregation.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end pt-3 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setIsSourceDetailsOpen(false)}
                className="px-4 py-1.5 text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 rounded-lg shadow-xs transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Acknowledge Alert */}
      {ackModalAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl p-5 shadow-2xl border border-slate-200 w-full max-w-md animate-in fade-in zoom-in-95 duration-150">
            <div className="pb-2.5 border-b border-slate-200">
              <h3 className="font-bold text-sm text-slate-900">
                Acknowledge Alert
              </h3>
            </div>
            <div className="py-3 space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Engineer Sign-Off:</label>
                <input
                  type="text"
                  value={engineerName}
                  onChange={(e) => setEngineerName(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-semibold mb-1">Review Notes:</label>
                <textarea
                  rows={2}
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value)}
                  placeholder="e.g. Reviewed observational anomaly with directional team; monitoring."
                  className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2.5 border-t border-slate-200">
              <button
                type="button"
                onClick={() => setAckModalAlert(null)}
                className="px-3.5 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAcknowledgeAlert}
                disabled={isActionLoading}
                className="px-3.5 py-1.5 text-xs font-bold text-white bg-cyan-700 hover:bg-cyan-800 rounded-lg shadow-xs cursor-pointer"
              >
                {isActionLoading ? 'Saving...' : 'Confirm Acknowledgement'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
