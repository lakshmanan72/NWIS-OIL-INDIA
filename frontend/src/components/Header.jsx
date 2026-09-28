import { useState, useEffect } from 'react';
import { Database, MapPin, BarChart3, BrainCircuit, Activity, FileText, UploadCloud, BookOpen, Radio, Info } from 'lucide-react';
import SearchBar from './SearchBar';

export default function Header({
  count,
  markers,
  onSelectWell,
  dataSource,
  currentTab,
  onNavigate,
  activeWellId,
}) {
  const [dbMode, setDbMode] = useState('CSV DEMO');

  useEffect(() => {
    fetch('/api/ready')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          if (data.backend_mode === 'postgres' && data.postgis) {
            setDbMode('PostgreSQL + PostGIS');
          } else if (data.backend_mode === 'postgres') {
            setDbMode('PostgreSQL');
          } else {
            setDbMode('CSV DEMO');
          }
        }
      })
      .catch(() => setDbMode('CSV DEMO'));
  }, []);
  return (
    <header className="nwis-header">
      <div className="header-brand flex items-center gap-3">
        {/* Official Oil India Limited Institutional Logo (36–44px height) */}
        <div
          className="oil-logo-header cursor-pointer flex items-center justify-center shrink-0"
          onClick={() => onNavigate('about-us')}
          title="Oil India Limited (Institutional Context)"
        >
          <img
            src="/oil-india-logo.svg"
            alt="Oil India Limited"
            className="h-9 w-auto object-contain"
            style={{ maxHeight: '38px' }}
          />
        </div>

        <div className="h-7 w-[1px] bg-[#D7E0E8] hidden sm:block shrink-0" />

        {/* NWIS Logo & Brand Identity */}
        <div className="flex items-center gap-2.5">
          <div
            className="brand-icon-wrapper"
            onClick={() => onNavigate('map')}
            style={{ cursor: 'pointer', background: '#063B73' }}
            title="NWIS Engineering Workstation"
          >
            <MapPin size={18} strokeWidth={2.5} className="text-[#F58220]" />
          </div>
          <div className="brand-titles" onClick={() => onNavigate('map')} style={{ cursor: 'pointer' }}>
            <div className="brand-title">
              <span className="brand-acronym font-black text-[#063B73]">NWIS</span>
              <span className="text-[#17324D] font-bold text-sm">Nearby Wells Intelligence System</span>
            </div>
            <div className="brand-subtitle text-[11px] text-[#64748B] font-medium">
              Drilling Intelligence & Early Warning
            </div>
          </div>
        </div>
      </div>

      <nav className="header-nav flex items-center gap-1">
        <button
          className={`nav-tab-btn ${currentTab === 'live' ? 'active' : ''}`}
          onClick={() => onNavigate('live')}
        >
          <Activity size={15} />
          <span>Live Operations</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'map' ? 'active' : ''}`}
          onClick={() => onNavigate('map')}
        >
          <MapPin size={15} />
          <span>Interactive Map</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => onNavigate('dashboard')}
        >
          <BarChart3 size={15} />
          <span>Dashboard</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'intelligence' ? 'active' : ''}`}
          onClick={() => onNavigate('intelligence', activeWellId || 'WELL-000001')}
        >
          <BrainCircuit size={15} />
          <span>Well Intelligence</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'documents' ? 'active' : ''}`}
          onClick={() => onNavigate('documents')}
        >
          <FileText size={15} />
          <span>Documents</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'wcr-upload' || currentTab === 'upload-document' ? 'active' : ''}`}
          onClick={() => onNavigate('wcr-upload')}
        >
          <UploadCloud size={15} />
          <span>Upload WCR</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'institutional-memory' ? 'active' : ''}`}
          onClick={() => onNavigate('institutional-memory')}
        >
          <BookOpen size={15} />
          <span>Institutional Memory</span>
        </button>
        <button
          className={`nav-tab-btn ${currentTab === 'about-us' ? 'active' : ''}`}
          onClick={() => onNavigate('about-us')}
        >
          <Info size={15} />
          <span>About Us</span>
        </button>
      </nav>

      <div className="header-center">
        <SearchBar markers={markers} onSelectWell={onSelectWell} />
      </div>

      <div className="header-stats flex items-center gap-3">
        <div
          className="wells-counter-badge bg-[#EBF9F1] border border-[#B7EBCA] text-[#16834B] font-mono font-bold text-xs px-3 py-1 rounded-md flex items-center gap-1.5"
          title="Dynamic active database count (Original canonical seed dataset: 15,108 wells)"
        >
          <span className="w-2 h-2 rounded-full bg-[#16834B] animate-pulse"></span>
          <span>Current Wells: {count !== null ? count.toLocaleString() : 'Loading...'}</span>
        </div>
        <div className="data-source-pill bg-[#F4F7FA] border border-[#D7E0E8] text-[#17324D] text-xs font-mono font-semibold px-2.5 py-1 rounded-md flex items-center gap-1.5">
          <Database size={13} className="text-[#0B5EA8]" />
          <span>NWIS DATA ● {dbMode}</span>
        </div>
      </div>
    </header>
  );
}
