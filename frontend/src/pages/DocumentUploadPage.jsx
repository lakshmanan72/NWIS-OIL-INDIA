import React, { useState, useRef } from 'react';
import {
  Upload,
  FileText,
  AlertTriangle,
  CheckCircle2,
  ArrowLeft,
  ShieldCheck,
  Cpu,
  Layers,
  FileCode,
  Info,
} from 'lucide-react';

export default function DocumentUploadPage({ onNavigate }) {
  const [file, setFile] = useState(null);
  const [docType, setDocType] = useState('WCR');
  const [uploadedBy, setUploadedBy] = useState('Drilling Operations Engineer');
  const [sourceDesc, setSourceDesc] = useState('Institutional Field WCR/DDR Archive');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const MAX_MB = 50;

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    setUploadError(null);
    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['pdf', 'txt'].includes(ext)) {
      setUploadError(`Unsupported format: .${ext}. Only .pdf and .txt files are supported.`);
      return;
    }

    if (selectedFile.size > MAX_MB * 1024 * 1024) {
      setUploadError(`File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds maximum limit (${MAX_MB} MB).`);
      return;
    }

    setFile(selectedFile);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setUploadError('Please select a PDF or TXT file to upload.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);
    if (docType && docType !== 'AUTO') {
      formData.append('document_type', docType);
    }
    formData.append('uploaded_by', uploadedBy);
    formData.append('source', sourceDesc);

    try {
      const res = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned status ${res.status}`);
      }

      const data = await res.json();
      setUploadSuccess(data);

      // Navigate to review cockpit after brief delay
      setTimeout(() => {
        onNavigate('review-document', data.document.document_id);
      }, 1200);
    } catch (err) {
      console.error('Upload failed:', err);
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="doc-page-container">
      <div className="doc-page-wrapper" style={{ maxWidth: '800px' }}>
        {/* Navigation back */}
        <div style={{ marginBottom: '1.5rem' }}>
          <button onClick={() => onNavigate('documents')} className="doc-back-link">
            <ArrowLeft size={16} />
            <span>Back to Document Repository</span>
          </button>
        </div>

        {/* Hero Card */}
        <div className="doc-upload-card">
          <div className="doc-upload-head">
            <div className="doc-icon-pill">
              <Upload size={22} className="text-cyan-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">Ingest Technical Drilling Document</h2>
              <p className="text-sm text-slate-500">
                Upload Well Completion Reports (WCR), Daily Drilling Reports (DDR), or Mud Logs for automated section extraction, entity parsing, and institutional memory indexing.
              </p>
            </div>
          </div>

          {/* Security & Validation Notice */}
          <div className="doc-security-banner">
            <ShieldCheck size={18} className="text-emerald-600 flex-shrink-0" />
            <div className="text-xs text-slate-600">
              <strong>Human-In-The-Loop Approval Gate:</strong> Extracted facts are not published to canonical data layers or RAG until an engineer formally reviews and signs off on the parsed evidence.
            </div>
          </div>

          <form onSubmit={handleSubmit} className="doc-upload-form">
            {/* Drag & Drop Box */}
            <div
              className={`doc-dropzone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />

              {file ? (
                <div className="doc-selected-file">
                  <div className="doc-file-icon">
                    <FileText size={36} className="text-cyan-600" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-800 text-sm">{file.name}</h4>
                    <p className="text-xs text-slate-500 font-mono">
                      {(file.size / 1024).toFixed(1)} KB • {file.type || 'Plain Document'}
                    </p>
                    <span className="text-xs text-cyan-600 font-semibold mt-1 inline-block">
                      Click or drop another file to change
                    </span>
                  </div>
                </div>
              ) : (
                <div className="doc-dropzone-prompt">
                  <div className="doc-drop-icon-wrap">
                    <Upload size={28} className="text-slate-400" />
                  </div>
                  <h4 className="font-semibold text-slate-700">
                    Click to browse or drag and drop a technical report
                  </h4>
                  <p className="text-xs text-slate-500 mt-1">
                    Supports high-resolution text PDFs, scanned PDF reports (OCR auto-fallback), and plain text logs (Max {MAX_MB} MB).
                  </p>
                </div>
              )}
            </div>

            {/* Document Attributes */}
            <div className="doc-form-grid">
              <div className="doc-form-field">
                <label className="doc-form-label">Document Classification Type</label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="doc-input"
                >
                  <option value="WCR">WCR — Well Completion Report</option>
                  <option value="DDR">DDR — Daily Drilling Report</option>
                  <option value="MUD_LOG">Mud Logging Report</option>
                  <option value="COMPLETION_REPORT">Well Completion Summary</option>
                  <option value="DRILLING_REPORT">End of Well / Drilling Recap</option>
                  <option value="AUTO">Auto-Detect via Domain Classifier</option>
                  <option value="OTHER">Other Technical Report</option>
                </select>
                <span className="doc-field-hint">
                  Allows engineer to guide the parser if automatic classification is uncertain.
                </span>
              </div>

              <div className="doc-form-field">
                <label className="doc-form-label">Reviewing Engineer / Uploaded By</label>
                <input
                  type="text"
                  value={uploadedBy}
                  onChange={(e) => setUploadedBy(e.target.value)}
                  placeholder="e.g. Lead Geomechanics Specialist"
                  className="doc-input"
                />
              </div>

              <div className="doc-form-field" style={{ gridColumn: 'span 2' }}>
                <label className="doc-form-label">Data Source / Provenance Note</label>
                <input
                  type="text"
                  value={sourceDesc}
                  onChange={(e) => setSourceDesc(e.target.value)}
                  placeholder="e.g. Field Archive - Western Offshore Basin"
                  className="doc-input"
                />
              </div>
            </div>

            {/* Error Banner */}
            {uploadError && (
              <div className="doc-error-banner">
                <AlertTriangle size={18} />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Success Banner */}
            {uploadSuccess && (
              <div className="doc-success-banner">
                <CheckCircle2 size={18} />
                <div>
                  <strong>Document Ingested Successfully!</strong>
                  <p className="text-xs mt-0.5">
                    ID: {uploadSuccess.document.document_id} • Extracted {uploadSuccess.extractions_count} entities and {uploadSuccess.events_count} events. Redirecting to Review Cockpit...
                  </p>
                </div>
              </div>
            )}

            {/* Submit Button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button
                type="submit"
                disabled={!file || isUploading}
                className="doc-submit-btn"
              >
                {isUploading ? (
                  <>
                    <div className="doc-spinner-sm"></div>
                    <span>Extracting Entities & Chunking Document...</span>
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    <span>Upload & Initiate AI Ingestion</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
