import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Search,
  Filter,
  Eye,
  ArrowRight,
  RefreshCw,
  Layers,
  ChevronRight,
  BookOpen,
} from 'lucide-react';

export default function DocumentsPage({ onNavigate }) {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    processing: 0,
    review_required: 0,
    approved: 0,
    rejected: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedType, setSelectedType] = useState('');

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      let url = '/api/documents?limit=100';
      if (selectedStatus) url += `&status=${encodeURIComponent(selectedStatus)}`;
      if (selectedType) url += `&document_type=${encodeURIComponent(selectedType)}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
        if (data.stats) setStats(data.stats);
      }
    } catch (err) {
      console.error('Failed to fetch document registry:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [selectedStatus, selectedType]);

  const filteredDocs = documents.filter((doc) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      doc.document_id.toLowerCase().includes(q) ||
      doc.filename.toLowerCase().includes(q) ||
      (doc.well_id && doc.well_id.toLowerCase().includes(q)) ||
      doc.document_type.toLowerCase().includes(q)
    );
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="doc-status-pill approved">
            <CheckCircle2 size={12} /> Approved
          </span>
        );
      case 'REVIEW_REQUIRED':
        return (
          <span className="doc-status-pill review-required">
            <AlertTriangle size={12} /> Review Required
          </span>
        );
      case 'REJECTED':
        return (
          <span className="doc-status-pill rejected">
            <XCircle size={12} /> Rejected
          </span>
        );
      case 'PROCESSING':
        return (
          <span className="doc-status-pill processing">
            <Clock size={12} className="animate-spin" /> Processing
          </span>
        );
      default:
        return <span className="doc-status-pill">{status}</span>;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case 'WCR':
        return <span className="doc-type-pill wcr">WCR</span>;
      case 'DDR':
        return <span className="doc-type-pill ddr">DDR</span>;
      case 'MUD_LOG':
        return <span className="doc-type-pill mud">MUD LOG</span>;
      case 'COMPLETION_REPORT':
        return <span className="doc-type-pill completion">COMPLETION</span>;
      default:
        return <span className="doc-type-pill other">{type || 'OTHER'}</span>;
    }
  };

  return (
    <div className="doc-page-container">
      <div className="doc-page-wrapper">
        {/* Top Header */}
        <div className="doc-header-row">
          <div>
            <div className="doc-hero-badge">
              <BookOpen size={14} />
              <span>INSTITUTIONAL MEMORY & REPOSITORY</span>
            </div>
            <h1 className="doc-page-title">Technical Document Repository</h1>
            <p className="doc-page-subtitle">
              Verified well completion reports (WCR), daily drilling reports (DDR), and institutional knowledge.
            </p>
          </div>
          <div className="doc-header-actions">
            <button
              onClick={() => onNavigate('upload-document')}
              className="doc-upload-primary-btn"
            >
              <Upload size={16} />
              <span>Upload Document</span>
            </button>
            <button
              onClick={() => onNavigate('institutional-memory')}
              className="doc-memory-secondary-btn"
            >
              <Search size={16} />
              <span>RAG Intelligence Query</span>
            </button>
          </div>
        </div>

        {/* Aggregate Stats Cards */}
        <div className="doc-stats-grid">
          <div className="doc-stat-card" onClick={() => setSelectedStatus('')}>
            <div className="doc-stat-icon-wrap total">
              <FileText size={20} />
            </div>
            <div className="doc-stat-data">
              <span className="doc-stat-val">{stats.total}</span>
              <span className="doc-stat-lbl">Total Documents</span>
            </div>
          </div>

          <div
            className={`doc-stat-card ${selectedStatus === 'REVIEW_REQUIRED' ? 'active-filter' : ''}`}
            onClick={() => setSelectedStatus(selectedStatus === 'REVIEW_REQUIRED' ? '' : 'REVIEW_REQUIRED')}
          >
            <div className="doc-stat-icon-wrap review">
              <AlertTriangle size={20} />
            </div>
            <div className="doc-stat-data">
              <span className="doc-stat-val text-amber-600">{stats.review_required}</span>
              <span className="doc-stat-lbl">Review Required</span>
            </div>
          </div>

          <div
            className={`doc-stat-card ${selectedStatus === 'APPROVED' ? 'active-filter' : ''}`}
            onClick={() => setSelectedStatus(selectedStatus === 'APPROVED' ? '' : 'APPROVED')}
          >
            <div className="doc-stat-icon-wrap approved">
              <CheckCircle2 size={20} />
            </div>
            <div className="doc-stat-data">
              <span className="doc-stat-val text-emerald-600">{stats.approved}</span>
              <span className="doc-stat-lbl">Approved Institutional Records</span>
            </div>
          </div>

          <div
            className={`doc-stat-card ${selectedStatus === 'REJECTED' ? 'active-filter' : ''}`}
            onClick={() => setSelectedStatus(selectedStatus === 'REJECTED' ? '' : 'REJECTED')}
          >
            <div className="doc-stat-icon-wrap rejected">
              <XCircle size={20} />
            </div>
            <div className="doc-stat-data">
              <span className="doc-stat-val text-red-600">{stats.rejected}</span>
              <span className="doc-stat-lbl">Rejected / Isolated</span>
            </div>
          </div>

          <div
            className={`doc-stat-card ${selectedStatus === 'PROCESSING' ? 'active-filter' : ''}`}
            onClick={() => setSelectedStatus(selectedStatus === 'PROCESSING' ? '' : 'PROCESSING')}
          >
            <div className="doc-stat-icon-wrap processing">
              <Clock size={20} />
            </div>
            <div className="doc-stat-data">
              <span className="doc-stat-val text-blue-600">{stats.processing}</span>
              <span className="doc-stat-lbl">Processing Pipeline</span>
            </div>
          </div>
        </div>

        {/* Filter / Search Bar */}
        <div className="doc-controls-bar">
          <div className="doc-search-box">
            <Search size={16} className="text-slate-400" />
            <input
              type="text"
              placeholder="Search by Document ID, filename, Well ID, or report type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="doc-search-input"
            />
          </div>

          <div className="doc-filters-group">
            <div className="doc-select-wrap">
              <Filter size={14} className="text-slate-400" />
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="doc-select"
              >
                <option value="">All Document Types</option>
                <option value="WCR">WCR (Well Completion Report)</option>
                <option value="DDR">DDR (Daily Drilling Report)</option>
                <option value="MUD_LOG">Mud Log</option>
                <option value="COMPLETION_REPORT">Completion Report</option>
                <option value="DRILLING_REPORT">Drilling Recap</option>
                <option value="OTHER">Other</option>
              </select>
            </div>

            <div className="doc-select-wrap">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="doc-select"
              >
                <option value="">All Review Statuses</option>
                <option value="REVIEW_REQUIRED">Review Required</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
                <option value="PROCESSING">Processing</option>
              </select>
            </div>

            <button onClick={fetchDocuments} className="doc-refresh-btn" title="Refresh list">
              <RefreshCw size={15} />
            </button>
          </div>
        </div>

        {/* Documents Table */}
        <div className="doc-table-card">
          {isLoading ? (
            <div className="doc-loading-state">
              <div className="doc-spinner"></div>
              <span>Loading institutional technical document registry...</span>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="doc-empty-state">
              <FileText size={40} className="text-slate-300" />
              <h3>No Technical Documents Found</h3>
              <p>
                {searchQuery || selectedStatus || selectedType
                  ? 'No documents matched the active search and filter criteria.'
                  : 'No engineering documents have been ingested yet. Upload a Well Completion Report (WCR) or Daily Drilling Report (DDR) to initiate the AI parsing pipeline.'}
              </p>
              <button
                onClick={() => onNavigate('upload-document')}
                className="doc-upload-primary-btn"
                style={{ marginTop: '1rem' }}
              >
                <Upload size={16} />
                <span>Upload First Document</span>
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="doc-table">
                <thead>
                  <tr>
                    <th>Document ID</th>
                    <th>Filename</th>
                    <th>Document Type</th>
                    <th>Associated Well</th>
                    <th>Review Status</th>
                    <th>Ingested Date</th>
                    <th>Uploaded By</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDocs.map((doc) => {
                    const isUnmatched = !doc.well_id || doc.well_id === 'UNMATCHED_WELL';
                    return (
                      <tr key={doc.document_id}>
                        <td className="font-mono text-cyan-600 font-bold">
                          {doc.document_id}
                        </td>
                        <td>
                          <div className="doc-name-cell">
                            <span className="doc-filename" title={doc.filename}>
                              {doc.filename}
                            </span>
                            {doc.ocr_applied && (
                              <span className="doc-ocr-tag" title="Processed via OCR">
                                OCR
                              </span>
                            )}
                          </div>
                        </td>
                        <td>{getTypeBadge(doc.document_type)}</td>
                        <td>
                          {isUnmatched ? (
                            <span className="doc-unmatched-pill" title="Not linked to canonical registry">
                              Unmatched Well
                            </span>
                          ) : (
                            <span className="doc-well-pill">
                              {doc.well_id}
                              {doc.matched_well_name && ` (${doc.matched_well_name})`}
                            </span>
                          )}
                        </td>
                        <td>{getStatusBadge(doc.processing_status)}</td>
                        <td className="text-xs text-slate-500 font-mono">
                          {doc.upload_timestamp ? doc.upload_timestamp.split('T')[0] : 'N/A'}
                        </td>
                        <td className="text-xs text-slate-600">{doc.uploaded_by || 'Engineer'}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            onClick={() => onNavigate('review-document', doc.document_id)}
                            className="doc-review-action-btn"
                          >
                            <Eye size={14} />
                            <span>
                              {doc.processing_status === 'REVIEW_REQUIRED' ? 'Review Cockpit' : 'View Record'}
                            </span>
                            <ChevronRight size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
