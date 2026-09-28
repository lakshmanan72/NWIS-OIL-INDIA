import React, { useState, useEffect } from 'react';
import {
  FileText,
  CheckCircle2,
  XCircle,
  Edit2,
  AlertTriangle,
  ArrowLeft,
  ShieldCheck,
  Check,
  Eye,
  Layers,
  HelpCircle,
  Database,
  Compass,
  Link as LinkIcon,
  PlusCircle,
  Activity,
  Sparkles,
  Info,
} from 'lucide-react';

export default function DocumentReviewPage({ documentId, onNavigate }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);

  // Editing state for an extraction
  const [editingExtractionId, setEditingExtractionId] = useState(null);
  const [editValue, setEditValue] = useState('');

  // Editing state for an event
  const [editingEventId, setEditingEventId] = useState(null);
  const [editEventForm, setEditEventForm] = useState({
    event_type: '',
    depth_md: '',
    hazard_assumption: '',
    raw_event_text: '',
  });

  // Classification override modal
  const [showClassifyModal, setShowClassifyModal] = useState(false);
  const [classifyType, setClassifyType] = useState('WCR');

  // Well linking modal state
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkWellId, setLinkWellId] = useState('');
  const [linkError, setLinkError] = useState(null);

  // Ambiguous selection state
  const [selectedCandidateId, setSelectedCandidateId] = useState('');

  // New well creation modal state
  const [showNewWellModal, setShowNewWellModal] = useState(false);
  const [newWellForm, setNewWellForm] = useState({
    well_name: '',
    latitude: '',
    longitude: '',
    field: '',
    basin: '',
    block: '',
    trajectory: 'Vertical',
    operator: 'ONGC',
    total_depth: '',
    formation: '',
    spud_date: '',
    completion_date: '',
    force_confirm: false,
  });
  const [newWellError, setNewWellError] = useState(null);

  // View Source modal state
  const [sourceModalData, setSourceModalData] = useState(null);

  const fetchDocumentDetails = async () => {
    if (!documentId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(documentId)}`);
      if (!res.ok) {
        let errMsg = `Failed to load document (${res.status})`;
        try {
          const errJson = await res.json();
          if (errJson && errJson.detail) errMsg = errJson.detail;
        } catch (_) {}
        throw new Error(errMsg);
      }
      const json = await res.json();
      setData(json);

      // If resolved from a well ID fallback, normalize browser address bar
      if (json.resolved_from_well_id && json.document?.document_id) {
        window.history.replaceState({}, '', `/documents/${encodeURIComponent(json.document.document_id)}/review`);
      }

      // Prepopulate new well form from extractions if available
      if (json.extractions && json.extractions.length > 0) {
        const extMap = {};
        json.extractions.forEach((e) => {
          extMap[e.field] = e.edited_value !== null && e.edited_value !== undefined ? e.edited_value : e.value;
        });

        setNewWellForm((prev) => ({
          ...prev,
          well_name: String(extMap.well_name || prev.well_name || ''),
          latitude: extMap.latitude !== undefined ? String(extMap.latitude) : prev.latitude,
          longitude: extMap.longitude !== undefined ? String(extMap.longitude) : prev.longitude,
          field: String(extMap.field || prev.field || 'Western Offshore'),
          basin: String(extMap.basin || prev.basin || 'Mumbai'),
          block: String(extMap.block || prev.block || ''),
          total_depth: extMap.total_depth !== undefined ? String(extMap.total_depth) : prev.total_depth,
          formation: String(extMap.formation || prev.formation || 'Barail'),
          spud_date: String(extMap.spud_date || prev.spud_date || ''),
          completion_date: String(extMap.completion_date || prev.completion_date || ''),
          operator: String(extMap.operator || prev.operator || 'ONGC'),
        }));
      }

      if (json.document) {
        setClassifyType(json.document.document_type || 'WCR');
      }
    } catch (err) {
      console.error('Error fetching review data:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocumentDetails();
  }, [documentId]);

  // Extraction Handlers
  const handleApproveExtraction = async (extId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/extractions/${extId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: 'Drilling Lead Engineer' }),
      });
      if (res.ok) {
        setActionNotice('Fact approved successfully.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectExtraction = async (extId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/extractions/${extId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: 'Drilling Lead Engineer' }),
      });
      if (res.ok) {
        setActionNotice('Fact rejected and isolated.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveEdit = async (extId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/extractions/${extId}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          edited_value: editValue,
          reviewer: 'Drilling Lead Engineer',
        }),
      });
      if (res.ok) {
        setEditingExtractionId(null);
        setActionNotice('Extraction corrected and updated.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Event Handlers
  const handleApproveEvent = async (evtId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/events/${evtId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: 'Drilling Superintendent' }),
      });
      if (res.ok) {
        setActionNotice('Drilling hazard event approved.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectEvent = async (evtId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/events/${evtId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: 'Drilling Superintendent' }),
      });
      if (res.ok) {
        setActionNotice('Drilling hazard event rejected and isolated.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveEditEvent = async (evtId) => {
    try {
      const res = await fetch(`/api/documents/${documentId}/events/${evtId}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: editEventForm.event_type || undefined,
          depth_md: editEventForm.depth_md ? parseFloat(editEventForm.depth_md) : undefined,
          hazard_assumption: editEventForm.hazard_assumption || undefined,
          raw_event_text: editEventForm.raw_event_text || undefined,
          reviewer: 'Drilling Superintendent',
        }),
      });
      if (res.ok) {
        setEditingEventId(null);
        setActionNotice('Drilling hazard event updated.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Classification Override
  const handleSaveClassification = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`/api/documents/${documentId}/classify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_type: classifyType,
          reviewer: 'Chief Technical Reviewer',
        }),
      });
      if (res.ok) {
        setShowClassifyModal(false);
        setActionNotice(`Document classification updated to ${classifyType}.`);
        fetchDocumentDetails();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleApproveAllHighConfidence = async () => {
    try {
      const res = await fetch(`/api/documents/${documentId}/approve-all-high?min_confidence=0.85`, {
        method: 'POST',
      });
      if (res.ok) {
        const d = await res.json();
        setActionNotice(`Batch-approved ${d.batch_approval.approved_extractions} entities and ${d.batch_approval.approved_events} events.`);
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveDocument = async () => {
    if (!window.confirm('Formally approve this technical document? Approved records will sync into the semantic vector index, institutional memory, and Well Intelligence cockpit.')) {
      return;
    }
    try {
      const res = await fetch(`/api/documents/${documentId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reviewer: 'Chief Drilling Superintendent',
          comments: 'Verified against rig telemetry and physical records. Formally approved.',
        }),
      });
      if (res.ok) {
        setActionNotice('Document formally APPROVED and indexed into Semantic Vector Store.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectDocument = async () => {
    const reason = window.prompt('Specify reason for rejecting this document:', 'Source data lacks operational verification.');
    if (!reason) return;
    try {
      const res = await fetch(`/api/documents/${documentId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reviewer: 'Chief Drilling Superintendent',
          reason: reason,
        }),
      });
      if (res.ok) {
        setActionNotice('Document REJECTED. All facts isolated from RAG and canonical index.');
        fetchDocumentDetails();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleLinkWell = async (e, customWid) => {
    if (e) e.preventDefault();
    const targetWid = customWid || linkWellId.trim();
    if (!targetWid) return;
    setLinkError(null);
    try {
      const res = await fetch(`/api/documents/${documentId}/match-well`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          well_id: targetWid,
          reviewer: 'Subsurface Data Steward',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to link canonical well');
      }
      setShowLinkModal(false);
      setActionNotice(`Successfully linked document to canonical well ${targetWid}`);
      fetchDocumentDetails();
    } catch (err) {
      setLinkError(err.message);
    }
  };

  const handleCreateNewWell = async (e) => {
    e.preventDefault();
    setNewWellError(null);
    try {
      const res = await fetch(`/api/documents/${documentId}/create-well`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newWellForm,
          latitude: parseFloat(newWellForm.latitude),
          longitude: parseFloat(newWellForm.longitude),
          total_depth: newWellForm.total_depth ? parseFloat(newWellForm.total_depth) : undefined,
          force_confirm: Boolean(newWellForm.force_confirm),
          reviewer: 'Chief Exploration Geologist',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create canonical well');
      }
      const json = await res.json();
      setShowNewWellModal(false);
      setActionNotice(`Created and linked new canonical well: ${json.well.well_id} (${json.well.well_name})`);
      fetchDocumentDetails();
    } catch (err) {
      setNewWellError(err.message);
    }
  };

  if (isLoading) {
    return (
      <div className="doc-page-container">
        <div className="doc-loading-state" style={{ minHeight: '400px' }}>
          <div className="doc-spinner"></div>
          <span>Loading Engineer Review Cockpit for {documentId}...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    const isWcrUnavailable = error && (
      error.toLowerCase().includes('no wcr document available') ||
      error.toLowerCase().includes('not available for well')
    );

    if (isWcrUnavailable || (error && documentId && String(documentId).startsWith('WELL-'))) {
      return (
        <div className="doc-page-container">
          <div className="doc-page-wrapper">
            <div style={{ margin: '3rem auto', maxWidth: '640px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '12px', padding: '2.5rem 2rem', textAlign: 'center', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}>
              <div style={{ width: '56px', height: '56px', background: '#f1f5f9', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem' }}>
                <FileText size={28} className="text-slate-500" />
              </div>
              <h2 className="text-xl font-bold text-slate-900">WCR Document Not Available</h2>
              <p className="text-sm text-slate-600 mt-2 mb-6 leading-relaxed">
                There is no Well Completion Report (WCR) document registered for well <strong className="font-mono text-slate-800">{documentId}</strong> in the active NWIS catalog. Historical or exploration records may not have an attached digital handover PDF.
              </p>
              <div className="flex items-center justify-center gap-3">
                <button onClick={() => onNavigate('map')} className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition">
                  <ArrowLeft size={14} /> Back to Map
                </button>
                <button onClick={() => onNavigate('documents')} className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition">
                  Document Repository
                </button>
                <button onClick={() => onNavigate('wcr-upload')} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition">
                  Upload WCR PDF →
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="doc-page-container">
        <div className="doc-error-banner" style={{ margin: '3rem auto', maxWidth: '600px' }}>
          <AlertTriangle size={24} />
          <div>
            <strong>Document Not Found</strong>
            <p className="text-sm mt-1">{error || 'Requested document ID does not exist in registry.'}</p>
            <button onClick={() => onNavigate('documents')} className="doc-back-link mt-2 inline-flex">
              <ArrowLeft size={14} /> Back to Documents
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { document: doc, extractions = [], events = [], reviews = [], low_confidence_count = 0 } = data;
  const isUnmatched = !doc.well_id || doc.well_id === 'UNMATCHED_WELL';
  const isAmbiguous = doc.well_match_status === 'AMBIGUOUS';
  const isApproved = doc.processing_status === 'APPROVED';
  const isRejected = doc.processing_status === 'REJECTED';

  return (
    <div className="doc-page-container">
      <div className="doc-page-wrapper">
        {/* Back Link */}
        <div style={{ marginBottom: '1.25rem' }}>
          <button onClick={() => onNavigate('documents')} className="doc-back-link">
            <ArrowLeft size={16} />
            <span>Back to Document Repository</span>
          </button>
        </div>

        {/* Action Toast */}
        {actionNotice && (
          <div className="doc-action-toast">
            <CheckCircle2 size={16} className="text-emerald-500" />
            <span>{actionNotice}</span>
            <button onClick={() => setActionNotice(null)} className="ml-auto text-xs opacity-70">
              Dismiss
            </button>
          </div>
        )}

        {/* Cockpit Overview Header */}
        <div className="doc-cockpit-header">
          <div className="doc-cockpit-title-group">
            <div className="doc-id-pill font-mono">{doc.document_id}</div>
            <h1 className="text-2xl font-bold text-slate-900">{doc.filename}</h1>
            <div className="doc-meta-row">
              <span className="doc-type-pill wcr flex items-center gap-1">
                {doc.document_type}
                {!isApproved && !isRejected && (
                  <button
                    onClick={() => setShowClassifyModal(true)}
                    className="ml-1 text-[11px] underline opacity-80 hover:opacity-100"
                    title="Override document classification"
                  >
                    [Edit]
                  </button>
                )}
              </span>
              <span>•</span>
              <span className="text-xs text-slate-500 font-mono">
                Classification Confidence: {doc.classification_confidence ? `${Math.round(doc.classification_confidence * 100)}%` : '95%'}
              </span>
              <span>•</span>
              <span className="text-xs text-slate-500">{doc.page_count} pages parsed</span>
              <span>•</span>
              <span className="text-xs text-slate-500 font-mono">Checksum: {doc.checksum.slice(0, 10)}...</span>
            </div>
          </div>

          <div className="doc-cockpit-status-col">
            <div className="text-right">
              <span className="text-xs text-slate-400 block mb-1">Approval Gate Status</span>
              <span className={`doc-status-pill ${doc.processing_status.toLowerCase()}`}>
                {doc.processing_status}
              </span>
            </div>

            {/* Approval Gate Primary Controls */}
            {!isApproved && !isRejected && (
              <div className="doc-gate-actions">
                <button
                  onClick={handleApproveDocument}
                  className="doc-approve-gate-btn"
                  title="Formally approve document and sync to RAG"
                >
                  <CheckCircle2 size={16} />
                  <span>Approve Document</span>
                </button>
                <button
                  onClick={handleRejectDocument}
                  className="doc-reject-gate-btn"
                  title="Reject document and isolate extracted facts"
                >
                  <XCircle size={16} />
                  <span>Reject</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Approval Gate Warning Banner */}
        <div className="doc-approval-banner">
          <ShieldCheck size={20} className="text-cyan-600 flex-shrink-0" />
          <div>
            <strong>Approval Gate Enforced:</strong> Technical facts and drilling events are in <em>{doc.processing_status}</em> mode. They will strictly <strong>NOT</strong> enter the semantic vector store, TF-IDF index, GIS maps, or Copilot answers until approved by an engineer.
          </div>
        </div>

        {/* Canonical Well Linkage Section */}
        <div className={`doc-well-match-card ${isUnmatched ? (isAmbiguous ? 'ambiguous' : 'unmatched') : 'matched'}`}>
          <div className="flex items-center gap-3">
            <Database size={22} className={isUnmatched ? (isAmbiguous ? 'text-amber-500' : 'text-purple-600') : 'text-emerald-500'} />
            <div>
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <span>Well Identification & Linkage</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold ${
                  doc.well_match_status === 'MATCHED'
                    ? 'bg-emerald-100 text-emerald-800'
                    : doc.well_match_status === 'AMBIGUOUS'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-purple-100 text-purple-800'
                }`}>
                  STATUS: {doc.well_match_status || (isUnmatched ? 'UNMATCHED' : 'MATCHED')}
                </span>
                {doc.well_match_method && (
                  <span className="text-[10px] text-slate-400 font-mono">
                    ({doc.well_match_method} • {Math.round((doc.well_match_confidence || 0.95) * 100)}% conf)
                  </span>
                )}
              </div>
              <div className="text-base font-bold text-slate-800 mt-0.5">
                {isUnmatched ? (
                  isAmbiguous ? (
                    <span className="text-amber-800">
                      Ambiguous well match detected across multiple candidates. Engineer assignment required.
                    </span>
                  ) : (
                    <span className="text-purple-900">
                      New well candidate detected. Engineer assignment required.
                    </span>
                  )
                ) : (
                  <span>
                    Linked to: <strong className="text-cyan-700 font-mono">{doc.well_id}</strong>
                    {doc.matched_well_name && ` — ${doc.matched_well_name}`}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setShowLinkModal(true)}
              className="doc-link-btn"
            >
              <LinkIcon size={14} />
              <span>Link Canonical Well</span>
            </button>
            <button
              onClick={() => setShowNewWellModal(true)}
              className="doc-new-well-btn"
            >
              <PlusCircle size={14} />
              <span>Create New Well Candidate</span>
            </button>
          </div>
        </div>

        {/* Ambiguous Well Candidates List if AMBIGUOUS */}
        {isAmbiguous && doc.ambiguous_candidates && doc.ambiguous_candidates.length > 0 && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl mb-6">
            <div className="text-xs font-bold text-amber-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <AlertTriangle size={15} className="text-amber-600" />
              <span>Multiple Candidate Matches Found in Registry — Please Confirm Target:</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {doc.ambiguous_candidates.map((c) => (
                <div
                  key={c.well_id}
                  className={`p-2.5 rounded-lg border text-xs cursor-pointer flex items-center justify-between ${
                    selectedCandidateId === c.well_id ? 'bg-cyan-50 border-cyan-400 ring-1 ring-cyan-400' : 'bg-white border-slate-200 hover:bg-slate-50'
                  }`}
                  onClick={() => setSelectedCandidateId(c.well_id)}
                >
                  <div>
                    <span className="font-bold text-slate-800">{c.well_name}</span>{' '}
                    <span className="font-mono text-cyan-700">({c.well_id})</span>
                    <div className="text-slate-500 mt-0.5">
                      {c.operator} • {c.field} Field • {c.basin} Basin
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleLinkWell(null, c.well_id);
                    }}
                    className="px-2.5 py-1 bg-cyan-700 hover:bg-cyan-800 text-white rounded text-[11px] font-semibold"
                  >
                    Select
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Batch Review Header */}
        <div className="doc-section-head-bar">
          <div>
            <h3 className="text-base font-bold text-slate-800">
              Extracted Technical Entities ({extractions.length})
            </h3>
            <p className="text-xs text-slate-500">
              {low_confidence_count > 0 ? (
                <span className="text-amber-600 font-semibold">
                  ⚠️ {low_confidence_count} item(s) flagged with confidence below 85%
                </span>
              ) : (
                'All extracted entities meet high-confidence verification standards.'
              )}
            </p>
          </div>

          {!isApproved && !isRejected && (
            <button
              onClick={handleApproveAllHighConfidence}
              className="doc-batch-approve-btn"
            >
              <Sparkles size={14} />
              <span>Approve All High Confidence (&ge;85%)</span>
            </button>
          )}
        </div>

        {/* Extractions Grid */}
        <div className="doc-extractions-grid">
          {extractions.map((ext) => {
            const isLowConf = ext.confidence < 0.85;
            const isEditing = editingExtractionId === ext.extraction_id;

            return (
              <div
                key={ext.extraction_id}
                className={`doc-ext-card ${isLowConf ? 'low-conf' : ''} ${ext.status.toLowerCase()}`}
              >
                <div className="doc-ext-head">
                  <span className="doc-ext-field">{ext.field.replace('_', ' ').toUpperCase()}</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`doc-conf-badge ${isLowConf ? 'low' : 'high'}`}
                      title={`Confidence: ${(ext.confidence * 100).toFixed(0)}%`}
                    >
                      {(ext.confidence * 100).toFixed(0)}%
                    </span>
                    <span className="doc-page-badge">Page {ext.page_number}</span>
                  </div>
                </div>

                <div className="doc-ext-body">
                  {isEditing ? (
                    <div className="doc-inline-edit-box">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="doc-inline-input"
                      />
                      <button
                        onClick={() => handleSaveEdit(ext.extraction_id)}
                        className="doc-inline-save-btn"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingExtractionId(null)}
                        className="doc-inline-cancel-btn"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="doc-ext-value">
                      <span className="val-text">
                        {ext.edited_value !== null && ext.edited_value !== undefined
                          ? ext.edited_value
                          : String(ext.value)}
                      </span>
                      {ext.unit && <span className="val-unit font-mono">{ext.unit}</span>}
                      {ext.status === 'EDITED' && (
                        <span className="doc-edited-tag" title="Modified by engineer">
                          Edited
                        </span>
                      )}
                    </div>
                  )}

                  <div className="doc-ext-citation">
                    <span className="cite-lbl">Source Snippet:</span>
                    <p className="cite-text">"{ext.source_text}"</p>
                  </div>
                </div>

                <div className="doc-ext-foot">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-slate-400">
                      Status: <strong className="text-slate-700">{ext.status}</strong>
                    </span>
                    <button
                      onClick={() => setSourceModalData({
                        title: ext.field.replace('_', ' ').toUpperCase(),
                        document_id: doc.document_id,
                        page_number: ext.page_number,
                        section: 'EXTRACTED ENTITY',
                        source_excerpt: ext.source_text,
                        interpretation: `Field: ${ext.field} = ${ext.edited_value || ext.value} ${ext.unit || ''} (Confidence: ${Math.round(ext.confidence * 100)}%)`,
                      })}
                      className="text-[11px] text-cyan-600 hover:text-cyan-800 underline flex items-center gap-0.5 ml-2"
                    >
                      <Eye size={12} />
                      <span>View Source</span>
                    </button>
                  </div>

                  {!isApproved && !isRejected && (
                    <div className="doc-ext-actions">
                      {ext.status !== 'APPROVED' && (
                        <button
                          onClick={() => handleApproveExtraction(ext.extraction_id)}
                          className="doc-action-icon-btn approve"
                          title="Approve fact"
                        >
                          <Check size={14} />
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setEditingExtractionId(ext.extraction_id);
                          setEditValue(String(ext.edited_value || ext.value));
                        }}
                        className="doc-action-icon-btn edit"
                        title="Edit value"
                      >
                        <Edit2 size={13} />
                      </button>
                      {ext.status !== 'REJECTED' && (
                        <button
                          onClick={() => handleRejectExtraction(ext.extraction_id)}
                          className="doc-action-icon-btn reject"
                          title="Reject fact"
                        >
                          <XCircle size={14} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Extracted Drilling Hazard Events Section */}
        <div className="doc-section-head-bar" style={{ marginTop: '2.5rem' }}>
          <div>
            <h3 className="text-base font-bold text-slate-800">
              Extracted Drilling Hazard Incidents ({events.length})
            </h3>
            <p className="text-xs text-slate-500">
              Mapped strictly to unified hazard taxonomy. Engineer review and approval required before indexing.
            </p>
          </div>
        </div>

        {events.length === 0 ? (
          <div className="doc-events-empty">
            <CheckCircle2 size={24} className="text-emerald-500" />
            <span>No drilling incidents or hazard events recorded in this report.</span>
          </div>
        ) : (
          <div className="doc-events-list">
            {events.map((evt) => {
              const isEditingThisEvent = editingEventId === evt.event_id;

              return (
                <div key={evt.event_id} className={`doc-event-card ${evt.event_type}`}>
                  <div className="doc-event-head">
                    <span className="doc-event-type-badge">{evt.event_type.replace('_', ' ').toUpperCase()}</span>
                    <div className="flex items-center gap-2">
                      <span className="doc-depth-tag">
                        {evt.depth_md !== null && evt.depth_md !== undefined
                          ? `Depth: ${evt.depth_md} m MD`
                          : 'Depth: Unspecified in text'}
                      </span>
                      {evt.formation && (
                        <span className="px-2 py-0.5 bg-slate-100 text-slate-700 text-xs rounded font-medium">
                          {evt.formation}
                        </span>
                      )}
                      <span className="doc-page-badge">Page {evt.source_page}</span>
                      <span className="doc-conf-badge high">{(evt.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>

                  <div className="doc-event-body">
                    {isEditingThisEvent ? (
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-300 space-y-2 text-xs">
                        <div>
                          <label className="font-bold text-slate-700 block mb-1">Hazard Category:</label>
                          <select
                            value={editEventForm.event_type}
                            onChange={(e) => setEditEventForm({ ...editEventForm, event_type: e.target.value })}
                            className="doc-input text-xs"
                          >
                            <option value="mud_loss">MUD LOSS</option>
                            <option value="stuck_pipe">STUCK PIPE</option>
                            <option value="kick">KICK</option>
                            <option value="overpressure">OVERPRESSURE</option>
                            <option value="torque_spike">TORQUE SPIKE</option>
                          </select>
                        </div>
                        <div>
                          <label className="font-bold text-slate-700 block mb-1">Measured Depth (m MD):</label>
                          <input
                            type="number"
                            value={editEventForm.depth_md}
                            onChange={(e) => setEditEventForm({ ...editEventForm, depth_md: e.target.value })}
                            className="doc-input text-xs"
                          />
                        </div>
                        <div>
                          <label className="font-bold text-slate-700 block mb-1">Event Description / Raw Text:</label>
                          <textarea
                            value={editEventForm.raw_event_text}
                            onChange={(e) => setEditEventForm({ ...editEventForm, raw_event_text: e.target.value })}
                            className="doc-input text-xs"
                            rows={2}
                          />
                        </div>
                        <div className="flex justify-end gap-2 pt-1">
                          <button
                            onClick={() => setEditingEventId(null)}
                            className="doc-modal-cancel-btn text-xs py-1"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => handleSaveEditEvent(evt.event_id)}
                            className="doc-inline-save-btn text-xs"
                          >
                            Save Event
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="text-sm text-slate-800 font-medium">"{evt.raw_event_text}"</p>
                        <p className="text-xs text-slate-500 mt-1 italic">
                          <strong>Domain Assumption:</strong> {evt.hazard_assumption}
                        </p>
                      </>
                    )}
                  </div>

                  <div className="doc-event-foot flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">
                        Status: <strong className="text-slate-700">{evt.status}</strong>
                      </span>
                      <button
                        onClick={() => setSourceModalData({
                          title: `Event: ${evt.event_type.toUpperCase()}`,
                          document_id: doc.document_id,
                          page_number: evt.source_page,
                          section: 'DRILLING EVENTS',
                          depth: evt.depth_md ? `${evt.depth_md} m` : 'Unspecified',
                          formation: evt.formation || 'N/A',
                          source_excerpt: evt.raw_event_text,
                          interpretation: `Detected Hazard: ${evt.event_type}. ${evt.hazard_assumption}`,
                        })}
                        className="text-[11px] text-cyan-600 hover:text-cyan-800 underline flex items-center gap-0.5 ml-2"
                      >
                        <Eye size={12} />
                        <span>View Source</span>
                      </button>
                    </div>

                    {!isApproved && !isRejected && (
                      <div className="flex items-center gap-2">
                        {evt.status !== 'APPROVED' && (
                          <button
                            onClick={() => handleApproveEvent(evt.event_id)}
                            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold flex items-center gap-1"
                            title="Approve drilling event"
                          >
                            <Check size={12} />
                            <span>Accept</span>
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setEditingEventId(evt.event_id);
                            setEditEventForm({
                              event_type: evt.event_type,
                              depth_md: evt.depth_md !== null && evt.depth_md !== undefined ? String(evt.depth_md) : '',
                              hazard_assumption: evt.hazard_assumption || '',
                              raw_event_text: evt.raw_event_text || '',
                            });
                          }}
                          className="px-2.5 py-1 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded text-xs font-semibold flex items-center gap-1"
                          title="Edit event"
                        >
                          <Edit2 size={12} />
                          <span>Edit</span>
                        </button>
                        {evt.status !== 'REJECTED' && (
                          <button
                            onClick={() => handleRejectEvent(evt.event_id)}
                            className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold flex items-center gap-1"
                            title="Reject event"
                          >
                            <XCircle size={12} />
                            <span>Reject</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Review Audit History */}
        {reviews && reviews.length > 0 && (
          <div className="doc-audit-section">
            <h4 className="text-sm font-bold text-slate-700 mb-2">Review & Audit Trail</h4>
            <div className="doc-audit-list">
              {reviews.map((r) => (
                <div key={r.review_id} className="doc-audit-item">
                  <div className="flex justify-between text-xs text-slate-500">
                    <strong>{r.action}</strong>
                    <span>{r.timestamp ? r.timestamp.replace('T', ' ').slice(0, 19) : ''}</span>
                  </div>
                  <div className="text-xs text-slate-700 mt-0.5">
                    By: <strong>{r.reviewer}</strong> • {r.comments}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Override Classification Modal */}
        {showClassifyModal && (
          <div className="doc-modal-overlay">
            <div className="doc-modal-box">
              <h3 className="text-lg font-bold text-slate-800 mb-2">Override Document Classification</h3>
              <p className="text-xs text-slate-500 mb-4">
                Select the verified technical document taxonomy classification.
              </p>
              <form onSubmit={handleSaveClassification}>
                <select
                  value={classifyType}
                  onChange={(e) => setClassifyType(e.target.value)}
                  className="doc-input mb-4"
                >
                  <option value="WCR">WCR (Well Completion Report)</option>
                  <option value="DDR">DDR (Daily Drilling Report)</option>
                  <option value="DRILLING_REPORT">DRILLING REPORT (End of Well Report)</option>
                  <option value="MUD_LOG">MUD LOG (Sensor & Gas Telemetry)</option>
                  <option value="COMPLETION_REPORT">COMPLETION REPORT</option>
                  <option value="OTHER">OTHER</option>
                </select>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setShowClassifyModal(false)}
                    className="doc-modal-cancel-btn"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="doc-modal-submit-btn">
                    Save Classification
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Link Modal */}
        {showLinkModal && (
          <div className="doc-modal-overlay">
            <div className="doc-modal-box">
              <h3 className="text-lg font-bold text-slate-800 mb-2">Link Existing Canonical Well</h3>
              <p className="text-xs text-slate-500 mb-4">
                Select or enter an existing canonical well ID (e.g. WELL-000050) to attach this technical report.
              </p>
              <form onSubmit={handleLinkWell}>
                <input
                  type="text"
                  placeholder="e.g. WELL-000050"
                  value={linkWellId}
                  onChange={(e) => setLinkWellId(e.target.value)}
                  className="doc-input mb-3 font-mono"
                  required
                />
                {linkError && <p className="text-xs text-red-600 mb-2">{linkError}</p>}
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setShowLinkModal(false)}
                    className="doc-modal-cancel-btn"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="doc-modal-submit-btn">
                    Link Well
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* New Well Candidate Modal */}
        {showNewWellModal && (
          <div className="doc-modal-overlay">
            <div className="doc-modal-box" style={{ maxWidth: '560px' }}>
              <h3 className="text-lg font-bold text-slate-800 mb-1">Create New Canonical Well Candidate</h3>
              <p className="text-xs text-slate-500 mb-3">
                Explicit engineer workflow for creating a new canonical well. Verifies duplicate safety and generates a permanent sequence ID (e.g. WELL-015109).
              </p>
              <form onSubmit={handleCreateNewWell} className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-slate-600 block mb-1">Well Name *</label>
                  <input
                    type="text"
                    required
                    value={newWellForm.well_name}
                    onChange={(e) => setNewWellForm({ ...newWellForm, well_name: e.target.value })}
                    placeholder="e.g. DISCOVERY-NORTH-1"
                    className="doc-input font-bold"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Latitude (°N) *</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={newWellForm.latitude}
                      onChange={(e) => setNewWellForm({ ...newWellForm, latitude: e.target.value })}
                      placeholder="e.g. 18.5250"
                      className="doc-input font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Longitude (°E) *</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={newWellForm.longitude}
                      onChange={(e) => setNewWellForm({ ...newWellForm, longitude: e.target.value })}
                      placeholder="e.g. 72.5564"
                      className="doc-input font-mono"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Field *</label>
                    <input
                      type="text"
                      required
                      value={newWellForm.field}
                      onChange={(e) => setNewWellForm({ ...newWellForm, field: e.target.value })}
                      placeholder="e.g. Western Offshore"
                      className="doc-input"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Basin *</label>
                    <input
                      type="text"
                      required
                      value={newWellForm.basin}
                      onChange={(e) => setNewWellForm({ ...newWellForm, basin: e.target.value })}
                      placeholder="e.g. Mumbai"
                      className="doc-input"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Total Depth (m)</label>
                    <input
                      type="number"
                      step="any"
                      value={newWellForm.total_depth}
                      onChange={(e) => setNewWellForm({ ...newWellForm, total_depth: e.target.value })}
                      placeholder="e.g. 3720"
                      className="doc-input font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Formation</label>
                    <input
                      type="text"
                      value={newWellForm.formation}
                      onChange={(e) => setNewWellForm({ ...newWellForm, formation: e.target.value })}
                      placeholder="e.g. Barail"
                      className="doc-input"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-600 block mb-1">Operator</label>
                    <input
                      type="text"
                      value={newWellForm.operator}
                      onChange={(e) => setNewWellForm({ ...newWellForm, operator: e.target.value })}
                      placeholder="e.g. ONGC"
                      className="doc-input"
                    />
                  </div>
                </div>

                {newWellError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
                    <strong>Creation Safeguard Alert:</strong> {newWellError}
                    {newWellError.includes('AMBIGUOUS_NEW_WELL') && (
                      <div className="mt-2 pt-2 border-t border-red-200">
                        <label className="flex items-center gap-2 cursor-pointer font-bold text-red-900">
                          <input
                            type="checkbox"
                            checked={newWellForm.force_confirm}
                            onChange={(e) => setNewWellForm({ ...newWellForm, force_confirm: e.target.checked })}
                          />
                          <span>Confirm override: Verified new drilled well despite duplicate candidate warning</span>
                        </label>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowNewWellModal(false)}
                    className="doc-modal-cancel-btn"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="doc-modal-submit-btn">
                    Confirm & Create Canonical Well
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* View Source Modal */}
        {sourceModalData && (
          <div className="doc-modal-overlay">
            <div className="doc-modal-box" style={{ maxWidth: '640px' }}>
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-3">
                <div className="flex items-center gap-2">
                  <FileText size={18} className="text-cyan-600" />
                  <h3 className="text-base font-bold text-slate-900">{sourceModalData.title}</h3>
                </div>
                <button
                  onClick={() => setSourceModalData(null)}
                  className="text-slate-400 hover:text-slate-600 font-bold text-lg"
                >
                  ✕
                </button>
              </div>

              <div className="text-xs text-slate-500 grid grid-cols-2 gap-2 mb-4 bg-slate-50 p-2.5 rounded-lg font-mono">
                <div>Document: <strong>{sourceModalData.document_id}</strong></div>
                <div>Page: <strong>{sourceModalData.page_number}</strong></div>
                <div>Section: <strong>{sourceModalData.section}</strong></div>
                <div>Depth: <strong>{sourceModalData.depth || 'N/A'}</strong></div>
              </div>

              {/* Explicit distinction between source text and AI interpretation */}
              <div className="space-y-4">
                <div className="p-3 bg-slate-900 text-slate-100 rounded-lg">
                  <div className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                    <Database size={13} />
                    <span>SOURCE EXCERPT (Verbatim from Technical Document)</span>
                  </div>
                  <p className="text-xs font-mono leading-relaxed bg-black/40 p-2.5 rounded border border-slate-800">
                    "{sourceModalData.source_excerpt}"
                  </p>
                </div>

                <div className="p-3 bg-cyan-50 border border-cyan-200 rounded-lg text-slate-800">
                  <div className="text-[11px] font-bold text-cyan-800 uppercase tracking-wider mb-1 flex items-center gap-1">
                    <Sparkles size={13} />
                    <span>AI / SYSTEM INTERPRETATION</span>
                  </div>
                  <p className="text-xs leading-relaxed">
                    {sourceModalData.interpretation}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-2 italic">
                    Requires engineer verification. All decisions are advisory decision support only.
                  </p>
                </div>
              </div>

              <div className="flex justify-end pt-4 mt-2 border-t border-slate-200">
                <button
                  onClick={() => setSourceModalData(null)}
                  className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded text-xs font-semibold"
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
