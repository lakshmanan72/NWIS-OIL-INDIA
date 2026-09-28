import React, { useState, useRef } from 'react';
import {
  Upload,
  FileText,
  AlertTriangle,
  CheckCircle2,
  MapPin,
  Compass,
  Layers,
  ArrowRight,
  ShieldCheck,
  RotateCcw,
  ExternalLink,
  ChevronRight,
  FileCheck,
  Search,
  Database,
  Building2,
  Calendar,
  Zap,
  Info,
  Edit3,
  Copy,
} from 'lucide-react';

export default function WcrUploadPage({ onNavigate, onWellCreated }) {
  // Processing States: 'IDLE' | 'UPLOADED' | 'PARSING' | 'EXTRACTING' | 'VALIDATING' | 'READY_TO_ADD' | 'INSUFFICIENT_EVIDENCE' | 'DUPLICATE_REVIEW' | 'ADDED_TO_NWIS' | 'FAILED'
  const [pipelineStep, setPipelineStep] = useState('IDLE');
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Extraction Payload from Server
  const [extractionResult, setExtractionResult] = useState(null);

  // Editable Form for Well Creation / Manual Coordinate Entry
  const [manualCoords, setManualCoords] = useState({
    latitude: '',
    longitude: '',
  });
  const [showManualCoordForm, setShowManualCoordForm] = useState(false);
  const [wellForm, setWellForm] = useState({
    well_name: '',
    operator: 'Oil India Limited',
    field: '',
    basin: '',
    block: '',
    total_depth: '',
    well_type: 'Exploration',
    well_status: 'Active',
    trajectory_type: 'Vertical',
    formation: '',
    spud_date: '',
    completion_date: '',
  });

  // Duplicate Resolution State
  const [forceConfirmDuplicate, setForceConfirmDuplicate] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [addedWellResult, setAddedWellResult] = useState(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile) => {
    setErrorMsg(null);
    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['pdf', 'txt'].includes(ext)) {
      setErrorMsg(`Unsupported format: .${ext}. Please upload a standard WCR PDF or text report.`);
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      setErrorMsg(`File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds 50 MB limit.`);
      return;
    }

    setFile(selectedFile);
    processWcrFile(selectedFile);
  };

  const processWcrFile = async (wcrFile) => {
    setErrorMsg(null);
    setPipelineStep('UPLOADED');
    setProgress(20);

    const formData = new FormData();
    formData.append('file', wcrFile);
    formData.append('uploaded_by', 'Drilling Operations Engineer');

    try {
      // Simulate stages for smooth engineer visual feedback
      setTimeout(() => {
        setPipelineStep('PARSING');
        setProgress(45);
      }, 500);

      setTimeout(() => {
        setPipelineStep('EXTRACTING');
        setProgress(75);
      }, 1000);

      const res = await fetch('/api/wcr/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error status ${res.status}`);
      }

      const data = await res.json();
      setProgress(100);
      setExtractionResult(data);

      const meta = data.extracted_metadata || {};
      const coords = data.coordinates || {};

      setWellForm({
        well_name: meta.well_name || '',
        operator: meta.operator || 'Oil India Limited',
        field: meta.field || '',
        basin: meta.basin || '',
        block: meta.block || '',
        total_depth: meta.total_depth !== null && meta.total_depth !== undefined ? String(meta.total_depth) : '',
        well_type: meta.well_type || 'Exploration',
        well_status: meta.well_status || 'Active',
        trajectory_type: meta.trajectory_type || 'Vertical',
        formation: meta.formation || '',
        spud_date: meta.spud_date || '',
        completion_date: meta.completion_date || '',
      });

      if (coords.latitude !== null && coords.latitude !== undefined) {
        setManualCoords({
          latitude: String(coords.latitude),
          longitude: String(coords.longitude),
        });
      }

      // Check status
      if (coords.location_status !== 'VALID') {
        setPipelineStep('INSUFFICIENT_EVIDENCE');
        setShowManualCoordForm(true);
      } else if (data.duplicate_detection && data.duplicate_detection.is_duplicate) {
        setPipelineStep('DUPLICATE_REVIEW');
      } else {
        setPipelineStep('READY_TO_ADD');
      }
    } catch (err) {
      console.error('WCR Processing Failed:', err);
      setPipelineStep('FAILED');
      setErrorMsg(err.message || 'WCR processing pipeline encountered an unexpected error.');
    }
  };

  const handleApplyManualCoords = (e) => {
    e.preventDefault();
    const lat = parseFloat(manualCoords.latitude);
    const lon = parseFloat(manualCoords.longitude);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      alert('Latitude must be a valid number between -90.0 and 90.0');
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      alert('Longitude must be a valid number between -180.0 and 180.0');
      return;
    }

    // Update extraction result with verified engineer coordinates
    const updatedCoord = {
      location_status: 'VALID',
      latitude: lat,
      longitude: lon,
      coordinate_source: 'ENGINEER_ENTERED',
      coordinate_confidence: 1.0,
      is_india_region: lat >= 4.0 && lat <= 38.5 && lon >= 65.0 && lon <= 98.5,
      message: 'Coordinates manually verified and entered by engineer.',
    };

    setExtractionResult((prev) => ({
      ...prev,
      coordinates: updatedCoord,
    }));

    if (extractionResult?.duplicate_detection?.is_duplicate && !forceConfirmDuplicate) {
      setPipelineStep('DUPLICATE_REVIEW');
    } else {
      setPipelineStep('READY_TO_ADD');
    }
    setShowManualCoordForm(false);
  };

  const handleAddWellToNwis = async () => {
    if (!extractionResult) return;
    setIsSubmitting(true);
    setErrorMsg(null);

    const docId = extractionResult.document_id;
    const lat = parseFloat(manualCoords.latitude || extractionResult.coordinates?.latitude);
    const lon = parseFloat(manualCoords.longitude || extractionResult.coordinates?.longitude);
    const coordSource = extractionResult.coordinates?.coordinate_source || 'WCR_DOCUMENT';

    if (isNaN(lat) || isNaN(lon)) {
      setErrorMsg('Valid coordinates are strictly required to plot the well on the interactive map.');
      setIsSubmitting(false);
      return;
    }

    const payload = {
      well_name: wellForm.well_name.trim(),
      latitude: lat,
      longitude: lon,
      coordinate_source: coordSource,
      operator: wellForm.operator.trim(),
      field: wellForm.field.trim(),
      basin: wellForm.basin.trim(),
      block: wellForm.block.trim(),
      total_depth: wellForm.total_depth ? parseFloat(wellForm.total_depth) : null,
      spud_date: wellForm.spud_date || null,
      completion_date: wellForm.completion_date || null,
      well_type: wellForm.well_type || 'Exploration',
      well_status: wellForm.well_status || 'Active',
      trajectory_type: wellForm.trajectory_type || 'Vertical',
      formation: wellForm.formation || null,
      force_confirm: forceConfirmDuplicate,
      reviewer: 'Drilling Operations Engineer',
    };

    try {
      const res = await fetch(`/api/wcr/${docId}/create-well`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail?.message || errJson.detail || `Error creating well (${res.status})`);
      }

      const createdData = await res.json();
      setAddedWellResult(createdData);
      setPipelineStep('ADDED_TO_NWIS');

      // Notify parent app to reload markers & update dynamic count immediately
      if (onWellCreated) {
        onWellCreated(createdData);
      }
    } catch (err) {
      console.error('Failed to create well from WCR:', err);
      setErrorMsg(err.message || 'Failed to insert well into NWIS canonical database.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUseExistingWell = () => {
    const existing = extractionResult?.duplicate_detection?.existing_well;
    if (existing?.well_id) {
      onNavigate('intelligence', existing.well_id);
    } else {
      onNavigate('map');
    }
  };

  const handleFocusNewWellOnMap = () => {
    if (addedWellResult && onWellCreated) {
      onWellCreated(addedWellResult);
    }
    onNavigate('map');
  };

  const coords = extractionResult?.coordinates;
  const duplicate = extractionResult?.duplicate_detection;
  const events = extractionResult?.drilling_events || [];

  return (
    <div className="wcr-upload-page-container min-h-screen bg-[#F8FAFC] pb-16">
      {/* Top Banner */}
      <div className="wcr-header bg-gradient-to-r from-[#063B73] via-[#0B5EA8] to-[#0A4B86] text-white py-8 px-6 shadow-md border-b border-[#063B73]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono tracking-wider text-[#93C5FD] uppercase mb-1">
              <Zap size={14} className="text-[#F58220]" />
              <span>NWIS Autonomous Ingestion Engine</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">
              WCR PDF → New Well Extraction & Map Integration
            </h1>
            <p className="text-sm text-[#E2E8F0] mt-1 max-w-2xl font-normal leading-relaxed">
              Upload Well Completion Reports. NWIS extracts coordinates, validates against all active canonical wells (Original canonical seed dataset: 15,108 wells),
              creates PostGIS spatial geometries, and dynamically plots the new well on the map.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigate('map')}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-bold border border-white/20 transition-all flex items-center gap-1.5"
            >
              <Compass size={14} />
              <span>Return to Map</span>
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 mt-8">
        {/* Pipeline Stepper */}
        <div className="pipeline-stepper bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm mb-8">
          <div className="text-xs font-bold uppercase tracking-wider text-[#64748B] mb-3 flex items-center justify-between">
            <span>Processing Pipeline Status</span>
            <span className="font-mono text-[#0B5EA8] lowercase">{pipelineStep}</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
            {[
              { id: 'UPLOADED', label: '1. UPLOADED' },
              { id: 'PARSING', label: '2. PARSING' },
              { id: 'EXTRACTING', label: '3. EXTRACTING' },
              { id: 'VALIDATING', label: '4. VALIDATING' },
              { id: 'READY_TO_ADD', label: '5. READY TO ADD' },
              { id: 'ADDED_TO_NWIS', label: '6. ADDED TO NWIS' },
            ].map((step, idx) => {
              const stepOrder = ['UPLOADED', 'PARSING', 'EXTRACTING', 'VALIDATING', 'READY_TO_ADD', 'ADDED_TO_NWIS'];
              const currentIdx = stepOrder.indexOf(pipelineStep);
              const thisIdx = stepOrder.indexOf(step.id);
              const isDone = currentIdx > thisIdx || pipelineStep === 'ADDED_TO_NWIS';
              const isCurrent = pipelineStep === step.id;
              const isWarning =
                (pipelineStep === 'INSUFFICIENT_EVIDENCE' || pipelineStep === 'DUPLICATE_REVIEW') &&
                step.id === 'VALIDATING';

              return (
                <div
                  key={step.id}
                  className={`flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all ${
                    isDone
                      ? 'bg-[#EBF9F1] border-[#B7EBCA] text-[#16834B]'
                      : isCurrent
                      ? 'bg-[#EBF5FB] border-[#0B5EA8] text-[#0B5EA8] font-bold shadow-sm'
                      : isWarning
                      ? 'bg-[#FEF9E7] border-[#FAD7A0] text-[#B7950B] font-bold'
                      : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#94A3B8]'
                  }`}
                >
                  <div className="text-xs font-mono font-bold">{step.label}</div>
                  {isDone && <CheckCircle2 size={13} className="mt-1 text-[#16834B]" />}
                  {isCurrent && <div className="w-2 h-2 rounded-full bg-[#0B5EA8] animate-ping mt-1"></div>}
                  {isWarning && <AlertTriangle size={13} className="mt-1 text-[#F58220]" />}
                </div>
              );
            })}
          </div>
        </div>

        {/* Upload Zone */}
        {pipelineStep === 'IDLE' && (
          <div
            className={`upload-drop-card bg-white rounded-2xl p-10 border-2 border-dashed transition-all text-center ${
              dragActive ? 'border-[#0B5EA8] bg-[#F0F7FD]' : 'border-[#CBD5E1] hover:border-[#0B5EA8]'
            } shadow-sm`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="w-20 h-20 rounded-2xl bg-[#EBF5FB] border border-[#BFDBFE] text-[#0B5EA8] flex items-center justify-center mx-auto mb-5 shadow-inner">
              <Upload size={38} className="animate-bounce" />
            </div>
            <h2 className="text-xl font-bold text-[#1E293B]">Drag & Drop WCR PDF Document</h2>
            <p className="text-sm text-[#64748B] mt-2 max-w-md mx-auto">
              Select or drop an official Well Completion Report (WCR) or Daily Drilling Report (DDR). Supports native and scanned PDF files.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 mt-6">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-6 py-3 bg-[#0B5EA8] hover:bg-[#063B73] text-white font-bold text-sm rounded-xl shadow transition-all flex items-center gap-2"
              >
                <FileText size={18} />
                <span>Browse Files</span>
              </button>
            </div>
            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-[#94A3B8]">
              <span>✓ Supported: PDF, TXT</span>
              <span>✓ Max File Size: 50 MB</span>
              <span>✓ PyMuPDF & OCR Engine Ready</span>
            </div>
          </div>
        )}

        {/* Upload in Progress */}
        {['UPLOADED', 'PARSING', 'EXTRACTING'].includes(pipelineStep) && (
          <div className="bg-white rounded-2xl p-8 border border-[#E2E8F0] shadow-sm text-center">
            <div className="w-16 h-16 rounded-full border-4 border-[#0B5EA8] border-t-transparent animate-spin mx-auto mb-4"></div>
            <h3 className="text-lg font-bold text-[#1E293B]">Analyzing WCR Document...</h3>
            <p className="text-sm text-[#64748B] mt-1 font-mono">
              {pipelineStep === 'UPLOADED' && 'Uploading document to secure NWIS storage...'}
              {pipelineStep === 'PARSING' && 'Parsing native PDF text streams & running OCR if needed...'}
              {pipelineStep === 'EXTRACTING' && 'Extracting surface coordinates, canonical metadata & drilling events...'}
            </p>
            <div className="w-full bg-[#E2E8F0] h-2.5 rounded-full overflow-hidden max-w-md mx-auto mt-5">
              <div
                className="bg-[#0B5EA8] h-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            {file && (
              <div className="mt-4 text-xs font-mono text-[#475569]">
                File: {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </div>
            )}
          </div>
        )}

        {/* Error State */}
        {errorMsg && (
          <div className="bg-[#FEF2F2] border border-[#FECACA] rounded-xl p-4 mb-6 flex items-start gap-3">
            <AlertTriangle size={20} className="text-[#DC2626] shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold text-[#991B1B]">Extraction Notice</div>
              <div className="text-xs text-[#B91C1C] mt-0.5 whitespace-pre-line">{errorMsg}</div>
            </div>
          </div>
        )}

        {/* Extracted Data Cockpit */}
        {extractionResult && pipelineStep !== 'ADDED_TO_NWIS' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Extracted Metadata & Coordinates */}
            <div className="lg:col-span-2 space-y-6">
              {/* Coordinates Card (CRITICAL) */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
                <div className="bg-[#F8FAFC] px-5 py-3 border-b border-[#E2E8F0] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Compass size={18} className="text-[#0B5EA8]" />
                    <span className="font-bold text-sm text-[#1E293B]">Surface Coordinates (Section 3)</span>
                  </div>
                  <span
                    className={`text-xs px-2.5 py-1 rounded-md font-bold font-mono ${
                      coords?.location_status === 'VALID'
                        ? 'bg-[#EBF9F1] text-[#16834B] border border-[#B7EBCA]'
                        : 'bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A]'
                    }`}
                  >
                    {coords?.location_status || 'UNKNOWN'}
                  </span>
                </div>

                <div className="p-5">
                  {coords?.location_status === 'VALID' ? (
                    <div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="p-3 bg-[#F1F5F9] rounded-lg border border-[#E2E8F0]">
                          <div className="text-[11px] font-mono text-[#64748B] uppercase">Latitude (Decimal Degrees)</div>
                          <div className="text-xl font-bold font-mono text-[#063B73] mt-0.5">
                            {coords.latitude?.toFixed(6)}° N
                          </div>
                          {coords.raw_latitude && (
                            <div className="text-[11px] text-[#64748B] mt-1 font-mono">
                              Raw: {coords.raw_latitude}
                            </div>
                          )}
                        </div>

                        <div className="p-3 bg-[#F1F5F9] rounded-lg border border-[#E2E8F0]">
                          <div className="text-[11px] font-mono text-[#64748B] uppercase">Longitude (Decimal Degrees)</div>
                          <div className="text-xl font-bold font-mono text-[#063B73] mt-0.5">
                            {coords.longitude?.toFixed(6)}° E
                          </div>
                          {coords.raw_longitude && (
                            <div className="text-[11px] text-[#64748B] mt-1 font-mono">
                              Raw: {coords.raw_longitude}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs">
                        <span className="px-2.5 py-1 rounded bg-[#EBF5FB] text-[#0B5EA8] font-mono font-semibold border border-[#BFDBFE]">
                          Source: {coords.coordinate_source || 'WCR_DOCUMENT'}
                        </span>
                        <span className="px-2.5 py-1 rounded bg-[#F8FAFC] text-[#475569] font-mono border border-[#E2E8F0]">
                          PostGIS: {coords.postgis_point || `POINT(${coords.longitude} ${coords.latitude})`}
                        </span>
                        {coords.is_india_region && (
                          <span className="px-2.5 py-1 rounded bg-[#EBF9F1] text-[#16834B] font-semibold border border-[#B7EBCA]">
                            ✓ Verified Indian Geographic Bounds
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => setShowManualCoordForm(!showManualCoordForm)}
                          className="ml-auto text-xs text-[#0B5EA8] hover:underline flex items-center gap-1 font-semibold"
                        >
                          <Edit3 size={13} />
                          <span>Edit Coordinates</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* INSUFFICIENT EVIDENCE STATE */
                    <div className="bg-[#FFFBEB] border border-[#FDE68A] rounded-xl p-5 text-center">
                      <div className="w-12 h-12 rounded-full bg-[#FEF3C7] text-[#D97706] flex items-center justify-center mx-auto mb-3">
                        <AlertTriangle size={24} />
                      </div>
                      <h4 className="font-bold text-[#92400E] text-base">Insufficient Coordinate Evidence</h4>
                      <p className="text-xs text-[#B45309] max-w-lg mx-auto mt-1 leading-relaxed">
                        Location coordinates were not reliably extracted from this WCR. The well cannot be placed on the geographic map until valid coordinates are provided.
                      </p>
                      <button
                        type="button"
                        onClick={() => setShowManualCoordForm(true)}
                        className="mt-4 px-4 py-2 bg-[#D97706] hover:bg-[#B45309] text-white text-xs font-bold rounded-lg transition-all"
                      >
                        Enter Coordinates Manually →
                      </button>
                    </div>
                  )}

                  {/* Manual Coordinate Form Modal / Accordion */}
                  {showManualCoordForm && (
                    <form onSubmit={handleApplyManualCoords} className="mt-4 p-4 bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl">
                      <div className="text-xs font-bold text-[#1E293B] mb-2 flex items-center justify-between">
                        <span>Engineer Manual Coordinate Entry</span>
                        <span className="text-[11px] font-mono text-[#D97706]">coordinate_source = ENGINEER_ENTERED</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[11px] font-semibold text-[#475569] mb-1">
                            Latitude [-90.0 to 90.0]
                          </label>
                          <input
                            type="number"
                            step="0.000001"
                            value={manualCoords.latitude}
                            onChange={(e) => setManualCoords({ ...manualCoords, latitude: e.target.value })}
                            placeholder="e.g. 27.209583"
                            required
                            className="w-full px-3 py-2 text-xs font-mono border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-[#475569] mb-1">
                            Longitude [-180.0 to 180.0]
                          </label>
                          <input
                            type="number"
                            step="0.000001"
                            value={manualCoords.longitude}
                            onChange={(e) => setManualCoords({ ...manualCoords, longitude: e.target.value })}
                            placeholder="e.g. 95.123389"
                            required
                            className="w-full px-3 py-2 text-xs font-mono border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setShowManualCoordForm(false)}
                          className="px-3 py-1.5 text-xs text-[#64748B] hover:text-[#1E293B]"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="px-4 py-1.5 bg-[#0B5EA8] hover:bg-[#063B73] text-white text-xs font-bold rounded-lg shadow-sm"
                        >
                          Confirm & Apply Coordinates
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>

              {/* Duplicate Detection Alert (Section 5) */}
              {duplicate?.is_duplicate && (
                <div className="bg-[#FFFBEB] rounded-xl border border-[#FCD34D] p-5 shadow-sm">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={22} className="text-[#D97706] shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="font-bold text-sm text-[#92400E]">POSSIBLE DUPLICATE WELL DETECTED</h4>
                        <span className="text-[10px] font-mono px-2 py-0.5 bg-[#FEF3C7] text-[#92400E] rounded font-bold">
                          DUPLICATE GUARD
                        </span>
                      </div>
                      <p className="text-xs text-[#B45309] mt-1 leading-relaxed">
                        {duplicate.similarity_reason}
                      </p>

                      {duplicate.existing_well && (
                        <div className="mt-3 p-3 bg-white/80 rounded-lg border border-[#FDE68A] text-xs font-mono grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <div>
                            <span className="text-[#94A3B8] block text-[10px]">EXISTING ID</span>
                            <span className="font-bold text-[#063B73]">{duplicate.existing_well.well_id}</span>
                          </div>
                          <div>
                            <span className="text-[#94A3B8] block text-[10px]">WELL NAME</span>
                            <span className="font-bold text-[#1E293B]">{duplicate.existing_well.well_name}</span>
                          </div>
                          <div>
                            <span className="text-[#94A3B8] block text-[10px]">OPERATOR</span>
                            <span>{duplicate.existing_well.operator}</span>
                          </div>
                          <div>
                            <span className="text-[#94A3B8] block text-[10px]">COORDINATES</span>
                            <span>
                              {duplicate.existing_well.latitude?.toFixed(4)}, {duplicate.existing_well.longitude?.toFixed(4)}
                            </span>
                          </div>
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={handleUseExistingWell}
                          className="px-4 py-2 bg-[#063B73] hover:bg-[#0B5EA8] text-white text-xs font-bold rounded-lg shadow-sm"
                        >
                          Use Existing Well ({duplicate.existing_well?.well_id})
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setForceConfirmDuplicate(true);
                            setPipelineStep('READY_TO_ADD');
                          }}
                          className={`px-4 py-2 border text-xs font-bold rounded-lg transition-all ${
                            forceConfirmDuplicate
                              ? 'bg-[#10B981] text-white border-[#10B981]'
                              : 'bg-white text-[#92400E] border-[#FCD34D] hover:bg-[#FEF3C7]'
                          }`}
                        >
                          {forceConfirmDuplicate ? '✓ Confirmed as Distinct Well' : 'Confirm & Create New Well'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Extracted Metadata Form Preview */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Building2 size={18} className="text-[#0B5EA8]" />
                    <h3 className="font-bold text-sm text-[#1E293B]">Well Metadata Preview</h3>
                  </div>
                  <span className="text-xs text-[#64748B] font-mono">
                    Confidence: {Math.round((extractionResult.extracted_metadata?.extraction_confidence || 0.85) * 100)}%
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Well Name</label>
                    <input
                      type="text"
                      value={wellForm.well_name}
                      onChange={(e) => setWellForm({ ...wellForm, well_name: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs font-semibold border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Operator</label>
                    <input
                      type="text"
                      value={wellForm.operator}
                      onChange={(e) => setWellForm({ ...wellForm, operator: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Field</label>
                    <input
                      type="text"
                      value={wellForm.field}
                      onChange={(e) => setWellForm({ ...wellForm, field: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Basin</label>
                    <input
                      type="text"
                      value={wellForm.basin}
                      onChange={(e) => setWellForm({ ...wellForm, basin: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Total Depth (m)</label>
                    <input
                      type="number"
                      value={wellForm.total_depth}
                      onChange={(e) => setWellForm({ ...wellForm, total_depth: e.target.value })}
                      placeholder="e.g. 3850"
                      className="w-full px-3 py-1.5 text-xs font-mono border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-[#64748B] mb-1">Formation</label>
                    <input
                      type="text"
                      value={wellForm.formation}
                      onChange={(e) => setWellForm({ ...wellForm, formation: e.target.value })}
                      placeholder="e.g. Barail / Tipam"
                      className="w-full px-3 py-1.5 text-xs border border-[#CBD5E1] rounded-lg focus:outline-none focus:border-[#0B5EA8]"
                    />
                  </div>
                </div>
              </div>

              {/* Historical Drilling Events Section (Section 8) */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={18} className="text-[#0B5EA8]" />
                    <h3 className="font-bold text-sm text-[#1E293B]">
                      Historical Drilling Events ({events.length})
                    </h3>
                  </div>
                  <span className="text-xs text-[#64748B] font-mono">Grounded strictly in report text</span>
                </div>

                {events.length > 0 ? (
                  <div className="space-y-2.5">
                    {events.map((evt, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              evt.severity === 'CRITICAL'
                                ? 'bg-[#FEE2E2] text-[#991B1B]'
                                : evt.severity === 'HIGH'
                                ? 'bg-[#FEF3C7] text-[#92400E]'
                                : 'bg-[#EBF5FB] text-[#0B5EA8]'
                            }`}
                          >
                            {evt.event_type}
                          </span>
                          <span className="text-xs font-mono text-[#64748B]">
                            {evt.depth ? `${evt.depth} m` : 'Depth unstated'}
                          </span>
                          {evt.formation && (
                            <span className="text-xs font-semibold text-[#475569]">{evt.formation}</span>
                          )}
                        </div>
                        <div className="text-xs text-[#334155] italic max-w-md line-clamp-1">
                          "{evt.description}"
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-[#94A3B8] p-3 text-center italic bg-[#F8FAFC] rounded-lg">
                    No explicit drilling hazard incidents reported in this document.
                  </div>
                )}
              </div>
            </div>

            {/* Right Col: Summary & Action Card */}
            <div className="space-y-6">
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 sticky top-6">
                <h3 className="text-base font-bold text-[#1E293B] mb-4">Ingestion Action Gate</h3>

                <div className="space-y-3 text-xs mb-6">
                  <div className="flex justify-between py-1.5 border-b border-[#F1F5F9]">
                    <span className="text-[#64748B]">Document:</span>
                    <span className="font-mono font-bold text-[#1E293B] max-w-[160px] truncate">
                      {extractionResult.filename}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-[#F1F5F9]">
                    <span className="text-[#64748B]">Coordinates Status:</span>
                    <span
                      className={`font-bold font-mono ${
                        coords?.location_status === 'VALID' ? 'text-[#16834B]' : 'text-[#D97706]'
                      }`}
                    >
                      {coords?.location_status}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-[#F1F5F9]">
                    <span className="text-[#64748B]">Events Extracted:</span>
                    <span className="font-bold text-[#1E293B]">{events.length}</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-[#F1F5F9]">
                    <span className="text-[#64748B]">Duplicate Status:</span>
                    <span
                      className={`font-bold ${
                        duplicate?.is_duplicate && !forceConfirmDuplicate ? 'text-[#D97706]' : 'text-[#16834B]'
                      }`}
                    >
                      {duplicate?.is_duplicate
                        ? forceConfirmDuplicate
                          ? 'Override Confirmed'
                          : 'Duplicate Review'
                        : 'No Duplicate'}
                    </span>
                  </div>
                </div>

                {/* Primary Button */}
                <button
                  type="button"
                  onClick={handleAddWellToNwis}
                  disabled={coords?.location_status !== 'VALID' || (duplicate?.is_duplicate && !forceConfirmDuplicate) || isSubmitting}
                  className={`w-full py-3 px-4 rounded-xl font-bold text-sm shadow transition-all flex items-center justify-center gap-2 ${
                    coords?.location_status === 'VALID' && (!duplicate?.is_duplicate || forceConfirmDuplicate)
                      ? 'bg-[#10B981] hover:bg-[#059669] text-white cursor-pointer shadow-md'
                      : 'bg-[#E2E8F0] text-[#94A3B8] cursor-not-allowed'
                  }`}
                >
                  {isSubmitting ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <MapPin size={16} />
                      <span>Add Well to NWIS & Plot on Map</span>
                    </>
                  )}
                </button>

                {coords?.location_status !== 'VALID' && (
                  <p className="text-[11px] text-[#D97706] mt-2 text-center leading-normal">
                    Valid coordinates required before this well can be added.
                  </p>
                )}
                {duplicate?.is_duplicate && !forceConfirmDuplicate && (
                  <p className="text-[11px] text-[#D97706] mt-2 text-center leading-normal">
                    Please confirm or resolve duplicate well check above.
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setPipelineStep('IDLE');
                    setExtractionResult(null);
                    setFile(null);
                  }}
                  className="w-full mt-3 py-2 text-xs text-[#64748B] hover:text-[#1E293B] border border-[#CBD5E1] rounded-xl flex items-center justify-center gap-1"
                >
                  <RotateCcw size={13} />
                  <span>Upload Different Document</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Banner (ADDED TO NWIS) */}
        {pipelineStep === 'ADDED_TO_NWIS' && addedWellResult && (
          <div className="bg-white rounded-2xl border-2 border-[#10B981] p-8 shadow-lg text-center max-w-2xl mx-auto animate-fade-in">
            <div className="w-16 h-16 rounded-full bg-[#EBF9F1] border-2 border-[#10B981] text-[#10B981] flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 size={36} />
            </div>

            <h2 className="text-2xl font-black text-[#1E293B] tracking-tight">WELL ADDED TO NWIS</h2>
            <p className="text-sm text-[#475569] mt-1">
              New well record created with PostGIS spatial coordinates and linked to WCR document.
            </p>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 my-6 text-left text-xs font-mono space-y-2">
              <div className="flex justify-between">
                <span className="text-[#64748B]">Canonical ID:</span>
                <span className="font-bold text-[#063B73]">{addedWellResult.well_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748B]">Well Name:</span>
                <span className="font-bold text-[#1E293B]">{addedWellResult.well_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748B]">Coordinates:</span>
                <span className="font-bold text-[#10B981]">
                  {addedWellResult.latitude?.toFixed(6)}° N, {addedWellResult.longitude?.toFixed(6)}° E
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748B]">Coordinate Source:</span>
                <span>{addedWellResult.coordinate_source}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748B]">Events Extracted:</span>
                <span>{addedWellResult.events_count} events</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-[#E2E8F0]">
                <span className="text-[#64748B]">Updated NWIS Wells Count:</span>
                <span className="font-bold text-[#0B5EA8]">{addedWellResult.total_wells?.toLocaleString()}</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="button"
                onClick={handleFocusNewWellOnMap}
                className="w-full sm:w-auto px-6 py-3 bg-[#063B73] hover:bg-[#0B5EA8] text-white font-bold text-sm rounded-xl shadow transition-all flex items-center justify-center gap-2"
              >
                <Compass size={18} />
                <span>Open Interactive Map & Focus New Well →</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setPipelineStep('IDLE');
                  setExtractionResult(null);
                  setFile(null);
                  setAddedWellResult(null);
                }}
                className="w-full sm:w-auto px-5 py-3 border border-[#CBD5E1] text-[#475569] hover:bg-[#F1F5F9] font-bold text-sm rounded-xl transition-all"
              >
                Upload Another WCR
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
