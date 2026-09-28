import React, { useState, useEffect } from 'react';
import {
  BrainCircuit,
  Search,
  BookOpen,
  ShieldCheck,
  AlertTriangle,
  Layers,
  MapPin,
  FileText,
  Sliders,
  Sparkles,
  ExternalLink,
  Info,
  Activity,
  Cpu,
  RefreshCw,
  Compass,
} from 'lucide-react';

export default function InstitutionalMemoryPage({ onNavigate }) {
  const [query, setQuery] = useState('What mud loss events occurred near this depth?');
  const [activeWellId, setActiveWellId] = useState('WELL-010267');
  const [depthMd, setDepthMd] = useState('2434.6');
  const [formation, setFormation] = useState('Barail');
  const [radiusKm, setRadiusKm] = useState(25);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [statusInfo, setStatusInfo] = useState(null);
  const [error, setError] = useState(null);

  // Fetch intelligence subsystem status
  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/intelligence/status');
      if (res.ok) {
        const data = await res.json();
        setStatusInfo(data);
      }
    } catch (e) {
      console.warn('Status lookup failed:', e);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleQuerySubmit = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const payload = {
        query: query.trim(),
        well_id: activeWellId.trim() || null,
        depth_md: depthMd ? parseFloat(depthMd) : null,
        formation: formation.trim() || null,
        radius_km: parseFloat(radiusKm) || 25.0,
      };

      const res = await fetch('/api/intelligence/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error('Copilot query error:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const sampleQuestions = [
    'What drilling problems were reported near this depth?',
    'Show historical mud loss events in nearby wells.',
    'What happened in the same formation?',
    'Are there similar stuck-pipe events?',
    'What historical evidence is relevant to the current interval?',
    'What risk indicators are currently available?',
  ];

  const [activeSourceModal, setActiveSourceModal] = useState(null);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'EVIDENCE_SUPPORTED':
        return <span className="doc-status-pill approved">EVIDENCE_SUPPORTED</span>;
      case 'PARTIALLY_SUPPORTED':
        return <span className="doc-status-pill review-required">PARTIALLY_SUPPORTED</span>;
      case 'INSUFFICIENT_EVIDENCE':
        return <span className="doc-status-pill rejected">INSUFFICIENT_EVIDENCE</span>;
      default:
        return <span className="doc-status-pill">{status || 'RETRIEVAL_ONLY'}</span>;
    }
  };

  return (
    <div className="doc-page-container">
      <div className="doc-page-wrapper">
        {/* Top Header / Hero */}
        <div className="doc-memory-hero">
          <div className="flex items-center justify-between">
            <div className="doc-hero-badge">
              <Sparkles size={14} />
              <span>SEMANTIC RAG + ENGINEERING COPILOT</span>
            </div>
            {statusInfo && (
              <div className="flex items-center gap-2 text-xs bg-slate-900/60 text-slate-300 px-3 py-1.5 rounded-full border border-slate-700/60 font-mono">
                <Cpu size={13} className="text-cyan-400" />
                <span>Mode: <strong className="text-cyan-300">{statusInfo.retrieval_mode?.toUpperCase()}</strong></span>
                <span>•</span>
                <span>Vector Store: {statusInfo.vector_store}</span>
                <span>•</span>
                <span>Chunks: {statusInfo.indexed_chunks}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#0B5EA8]" />
            <h1 className="text-xl sm:text-2xl font-black text-[#063B73] tracking-tight uppercase">
              ENGINEERING COPILOT
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] max-w-2xl mt-1 font-medium">
            Source-grounded decision support powered by semantic vector retrieval, stratigraphic & depth filtering, and verified historical evidence.
          </p>
        </div>

        {/* Operational Safety Banner */}
        <div className="doc-security-banner" style={{ marginBottom: '1.5rem' }}>
          <ShieldCheck size={20} className="text-emerald-600 flex-shrink-0" />
          <div className="text-xs text-slate-600">
            <strong>Decision-Support Only:</strong> Synthesized answers are constrained strictly to verified institutional evidence packets. Prohibits autonomous commands; all operational adjustments require engineer review.
          </div>
        </div>

        {/* Copilot Query Input Card */}
        <div className="doc-rag-card">
          <form onSubmit={handleQuerySubmit}>
            <div className="doc-query-input-wrap">
              <Search size={20} className="text-slate-400 flex-shrink-0" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask an operational drilling question (e.g. What lost circulation occurred in Barail?)..."
                className="doc-query-input"
              />
              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="doc-query-btn"
              >
                {isLoading ? (
                  <>
                    <div className="doc-spinner-sm"></div>
                    <span>Synthesizing Evidence...</span>
                  </>
                ) : (
                  <>
                    <BrainCircuit size={16} />
                    <span>Ask Copilot</span>
                  </>
                )}
              </button>
            </div>

            {/* Spatial & Physical Filters */}
            <div className="doc-rag-params-row">
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-slate-400" />
                <label className="text-xs text-slate-600 font-semibold">Active Well:</label>
                <input
                  type="text"
                  value={activeWellId}
                  onChange={(e) => setActiveWellId(e.target.value)}
                  placeholder="e.g. WELL-000050"
                  className="doc-param-input font-mono"
                />
              </div>

              <div className="flex items-center gap-2">
                <Layers size={14} className="text-slate-400" />
                <label className="text-xs text-slate-600 font-semibold">Depth (MD):</label>
                <input
                  type="number"
                  value={depthMd}
                  onChange={(e) => setDepthMd(e.target.value)}
                  placeholder="e.g. 1132"
                  className="doc-param-input font-mono"
                  style={{ width: '90px' }}
                />
                <span className="text-xs text-slate-400">m</span>
              </div>

              <div className="flex items-center gap-2">
                <Compass size={14} className="text-slate-400" />
                <label className="text-xs text-slate-600 font-semibold">Formation:</label>
                <input
                  type="text"
                  value={formation}
                  onChange={(e) => setFormation(e.target.value)}
                  placeholder="e.g. Barail"
                  className="doc-param-input"
                  style={{ width: '110px' }}
                />
              </div>

              <div className="flex items-center gap-2">
                <Sliders size={14} className="text-slate-400" />
                <label className="text-xs text-slate-600 font-semibold">Radius: {radiusKm} km</label>
                <input
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={radiusKm}
                  onChange={(e) => setRadiusKm(Number(e.target.value))}
                  className="doc-slider"
                />
              </div>
            </div>
          </form>

          {/* Suggested Questions */}
          <div className="doc-prompt-chips">
            <span className="text-xs text-slate-400 font-medium">Suggested Questions:</span>
            {sampleQuestions.map((sq, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setQuery(sq);
                }}
                className="doc-prompt-chip"
              >
                {sq}
              </button>
            ))}
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="doc-error-banner" style={{ marginTop: '1.5rem' }}>
            <AlertTriangle size={18} />
            <span>Copilot Query Error: {error}</span>
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="doc-results-section">
            {/* Copilot Response Card */}
            <div className="doc-answer-card">
              <div className="doc-answer-head">
                <div className="flex items-center gap-2">
                  <BrainCircuit size={18} className="text-cyan-600" />
                  <span className="font-bold text-slate-800 text-sm tracking-wide">
                    ENGINEERING COPILOT SYNTHESIS
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(result.evidence_status)}
                  <span className="text-xs font-mono bg-cyan-50 text-cyan-700 px-2.5 py-1 rounded font-semibold border border-cyan-200">
                    Mode: {result.retrieval_mode?.toUpperCase()}
                  </span>
                  <span className="doc-page-badge">{result.source_count} Citations</span>
                </div>
              </div>

              <div className="doc-answer-body">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Question: "{query}"
                </div>
                <p className="text-base text-slate-800 leading-relaxed font-normal mt-2">
                  {result.answer}
                </p>
              </div>

              <div className="doc-answer-foot flex items-center justify-between">
                <span className="text-xs text-slate-500 italic">
                  {result.advisory || 'Engineering review required. Decision support only.'}
                </span>
                {result.retrieval_relevance > 0 && (
                  <span className="text-xs font-mono text-slate-500">
                    Top Relevance: <strong>{(result.retrieval_relevance * 100).toFixed(0)}%</strong>
                  </span>
                )}
              </div>
            </div>

            {/* Model Risk Indicators Panel (Phase 3.1 Integration) */}
            {result.risk_indicators && result.risk_indicators.length > 0 && (
              <div className="doc-rag-card" style={{ marginTop: '1.5rem' }}>
                <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-cyan-600" />
                    <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
                      Model Risk Indicators ({result.active_well || activeWellId})
                    </h3>
                  </div>
                  <span className="text-xs text-slate-400 italic">
                    Model Risk Indicators are predictive scores, not calibrated probabilities.
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                  {result.risk_indicators.map((r, i) => (
                    <div key={i} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                      <span className="text-xs font-semibold text-slate-600 uppercase block">
                        {r.hazard.replace('_', ' ')}
                      </span>
                      <span className="text-lg font-bold text-slate-900 block my-1">
                        {r.model_risk_indicator_pct}%
                      </span>
                      <span className="text-[10px] text-slate-400 block font-mono">
                        Model Risk Indicator ({r.algorithm})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Citations & Evidence Packet Cards */}
            <div style={{ marginTop: '1.75rem' }}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">
                  Verified Evidence Cards ({result.evidence?.length || 0})
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  Grounded in approved institutional records
                </span>
              </div>

              {(!result.evidence || result.evidence.length === 0) ? (
                <div className="doc-evidence-empty">
                  <Info size={20} className="text-slate-400" />
                  <span>No matching citations found in approved institutional records for the requested parameters.</span>
                </div>
              ) : (
                <div className="doc-evidence-grid">
                  {result.evidence.map((ev, idx) => (
                    <div key={idx} className="doc-evidence-card">
                      <div className="doc-evidence-head">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold bg-slate-800 text-cyan-300 px-2 py-0.5 rounded">
                            [{ev.evidence_id || `EVID-${String(idx + 1).padStart(3, '0')}`}]
                          </span>
                          <span className="doc-well-pill font-mono">{ev.well_id}</span>
                          {ev.distance_km !== null && ev.distance_km !== undefined && (
                            <span className="text-xs text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded">
                              {ev.distance_km} km away
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-400 font-mono">
                            Doc: {ev.document_id}
                          </span>
                          <span className="doc-page-badge">Page {ev.page || ev.page_number}</span>
                        </div>
                      </div>

                      <div className="doc-evidence-body">
                        <div className="doc-evidence-meta-row">
                          <span>
                            Formation: <strong>{ev.formation || 'Unspecified'}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Depth:{' '}
                            <strong>
                              {ev.depth_from && ev.depth_to
                                ? `${ev.depth_from}–${ev.depth_to} m`
                                : ev.depth_md
                                ? `${ev.depth_md} m MD`
                                : 'N/A'}
                            </strong>
                          </span>
                          <span>•</span>
                          <span>
                            Section: <strong className="text-cyan-700">{ev.section || ev.event}</strong>
                          </span>
                        </div>

                        {ev.component_scores && (
                          <div className="flex items-center gap-2 my-1 text-[11px] text-slate-400 font-mono">
                            <span>Score: <strong>{(ev.retrieval_score * 100).toFixed(0)}%</strong></span>
                            <span>(Sem: {(ev.component_scores.semantic_score * 100).toFixed(0)}% | Form: {(ev.component_scores.formation_score * 100).toFixed(0)}% | Depth: {(ev.component_scores.depth_score * 100).toFixed(0)}% | Spat: {(ev.component_scores.spatial_score * 100).toFixed(0)}%)</span>
                          </div>
                        )}

                        <blockquote className="doc-evidence-quote">
                          "{ev.excerpt}"
                        </blockquote>
                      </div>

                      <div className="doc-evidence-foot flex items-center justify-between">
                        <button
                          type="button"
                          onClick={() => setActiveSourceModal(ev)}
                          className="doc-citation-link doc-view-source-btn"
                        >
                          <BookOpen size={12} />
                          <span>View Source</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (ev.document_id && !ev.document_id.startsWith('DOC-UNKNOWN') && !ev.document_id.startsWith('HISTORICAL')) {
                              onNavigate('review-document', ev.document_id);
                            } else {
                              onNavigate('documents');
                            }
                          }}
                          className="doc-citation-link text-slate-400 hover:text-slate-600"
                          title="Open document review record"
                        >
                          <ExternalLink size={12} />
                          <span>Record Details</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* View Source Modal (Section 18 Source Verification) */}
        {activeSourceModal && (
          <div className="doc-modal-overlay doc-source-modal">
            <div className="doc-modal-box max-w-2xl">
              <div className="doc-modal-header flex items-center justify-between pb-3 border-b border-slate-200">
                <div className="flex items-center gap-2">
                  <BookOpen size={18} className="text-cyan-600" />
                  <h3 className="text-base font-bold text-slate-900">
                    Source Verification — [{activeSourceModal.evidence_id || 'EVID-VERIFIED'}]
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveSourceModal(null)}
                  className="doc-modal-close text-slate-400 hover:text-slate-600 text-lg font-bold"
                >
                  ×
                </button>
              </div>

              <div className="doc-modal-body py-4 space-y-4">
                {/* Metadata grid: Document, Page, Well, Section, Depth */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                  <div>
                    <span className="text-slate-400 block font-semibold">Document:</span>
                    <span className="font-mono font-bold text-slate-800">{activeSourceModal.document_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Page:</span>
                    <span className="font-mono font-bold text-slate-800">{activeSourceModal.page || activeSourceModal.page_number || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Well:</span>
                    <span className="font-mono font-bold text-slate-800">{activeSourceModal.well_id || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Section:</span>
                    <span className="font-mono font-bold text-slate-800">{activeSourceModal.section || activeSourceModal.event || 'Technical'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Depth:</span>
                    <span className="font-mono font-bold text-slate-800">
                      {activeSourceModal.depth_from && activeSourceModal.depth_to
                        ? `${activeSourceModal.depth_from}–${activeSourceModal.depth_to} m`
                        : activeSourceModal.depth_md
                        ? `${activeSourceModal.depth_md} m MD`
                        : 'Unspecified'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-semibold">Formation:</span>
                    <span className="font-mono font-bold text-slate-800">{activeSourceModal.formation || 'Unspecified'}</span>
                  </div>
                </div>

                {/* Section 18: Clearly label SOURCE EXCERPT and AI / SYSTEM INTERPRETATION */}
                <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg">
                  <div className="flex items-center gap-1.5 mb-1 text-xs font-bold text-amber-900 tracking-wider uppercase">
                    <FileText size={14} className="text-amber-700" />
                    <span>SOURCE EXCERPT</span>
                    <span className="text-[10px] font-normal text-amber-700 ml-auto">(Verbatim text from uploaded WCR/DDR record)</span>
                  </div>
                  <blockquote className="text-xs text-slate-800 font-mono italic whitespace-pre-wrap bg-white/80 p-2.5 rounded border border-amber-100">
                    "{activeSourceModal.excerpt || activeSourceModal.source_excerpt || 'No excerpt text provided'}"
                  </blockquote>
                </div>

                <div className="p-3 bg-cyan-50/70 border border-cyan-200 rounded-lg">
                  <div className="flex items-center gap-1.5 mb-1 text-xs font-bold text-cyan-900 tracking-wider uppercase">
                    <BrainCircuit size={14} className="text-cyan-700" />
                    <span>AI / SYSTEM INTERPRETATION</span>
                    <span className="text-[10px] font-normal text-cyan-700 ml-auto">(Synthesized decision-support claim)</span>
                  </div>
                  <div className="text-xs text-slate-800 bg-white/80 p-2.5 rounded border border-cyan-100">
                    {result?.answer ? (
                      <p>{result.answer}</p>
                    ) : (
                      <p>Evidence-supported finding. Retrievable with strict provenance back to approved document chunk.</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="doc-modal-footer flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => {
                    const docId = activeSourceModal.document_id;
                    setActiveSourceModal(null);
                    if (docId && !docId.startsWith('DOC-UNKNOWN') && !docId.startsWith('HISTORICAL')) {
                      onNavigate('review-document', docId);
                    }
                  }}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded border border-slate-300"
                >
                  Open Document Details
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSourceModal(null)}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
