import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import WellMap from './components/WellMap';
import DashboardPage from './pages/DashboardPage';
import WellIntelligencePage from './pages/WellIntelligencePage';
import DocumentsPage from './pages/DocumentsPage';
import DocumentUploadPage from './pages/DocumentUploadPage';
import DocumentReviewPage from './pages/DocumentReviewPage';
import InstitutionalMemoryPage from './pages/InstitutionalMemoryPage';
import LiveDashboardPage from './pages/LiveDashboardPage';
import AboutUsPage from './pages/AboutUsPage';
import WcrUploadPage from './pages/WcrUploadPage';

export default function App() {
  const [markers, setMarkers] = useState([]);
  const [count, setCount] = useState(null);
  const [dataSource, setDataSource] = useState('REAL_PUBLIC');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedWell, setSelectedWell] = useState(null);
  const [error, setError] = useState(null);

  // Navigation state: 'live' | 'map' | 'dashboard' | 'intelligence' | 'documents' | 'upload-document' | 'wcr-upload' | 'review-document' | 'institutional-memory'
  const [currentTab, setCurrentTab] = useState(() => {
    if (typeof window !== 'undefined') {
      const p = window.location.pathname;
      if (p === '/about-us') return 'about-us';
      if (p === '/dashboard') return 'dashboard';
      if (p === '/map') return 'map';
      if (p === '/wcr-upload') return 'wcr-upload';
      if (p === '/documents') return 'documents';
      if (p === '/upload' || p === '/documents/upload') return 'wcr-upload';
      if (p === '/institutional-memory') return 'institutional-memory';
      if (p.startsWith('/well/')) return 'intelligence';
      if (p === '/live') return 'live';
      if (p === '/' || p === '/map') return 'map';
    }
    return 'map'; // Default to interactive map on root URL
  });
  const [activeWellId, setActiveWellId] = useState(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const wid = params.get('well_id');
      if (wid) return wid;
    }
    return 'WELL-000001';
  });
  const [activeDocumentId, setActiveDocumentId] = useState(null);

  // Handle URL path on mount & popstate
  useEffect(() => {
    function parseRoute() {
      const path = window.location.pathname;

      if (path === '/about-us') {
        setCurrentTab('about-us');
        return;
      }
      if (path === '/live') {
        const params = new URLSearchParams(window.location.search);
        const qWell = params.get('well_id');
        if (qWell) {
          setActiveWellId(qWell);
        }
        setCurrentTab('live');
        return;
      }
      if (path === '/wcr-upload') {
        setCurrentTab('wcr-upload');
        return;
      }
      if (path === '/documents/upload' || path === '/upload') {
        setCurrentTab('wcr-upload');
        return;
      }
      if (path.startsWith('/documents/') && path.endsWith('/review')) {
        const parts = path.split('/');
        const docId = parts[2];
        if (docId) {
          setActiveDocumentId(docId);
          setCurrentTab('review-document');
          return;
        }
      }
      if (path === '/documents') {
        setCurrentTab('documents');
        return;
      }
      if (path === '/intelligence' || path === '/institutional-memory') {
        setCurrentTab('institutional-memory');
        return;
      }
      if (path.startsWith('/well/')) {
        const wid = path.replace('/well/', '').trim();
        if (wid) {
          setActiveWellId(wid);
          setCurrentTab('intelligence');
          return;
        }
      }
      if (path === '/dashboard') {
        setCurrentTab('dashboard');
        return;
      }
      setCurrentTab('map');
    }

    parseRoute();
    window.addEventListener('popstate', parseRoute);
    return () => window.removeEventListener('popstate', parseRoute);
  }, []);

  // Fetch authoritative dynamic well count from backend
  const fetchWellCount = async () => {
    try {
      let res;
      try {
        res = await fetch('/api/wells/count');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      } catch (err) {
        res = await fetch('http://127.0.0.1:8000/api/wells/count');
      }
      if (res.ok) {
        const cData = await res.json();
        if (cData && typeof cData.count === 'number') {
          setCount(cData.count);
        }
      }
    } catch (e) {
      console.warn('Could not fetch authoritative well count:', e);
    }
  };

  // Fetch well markers for map
  const fetchWellMarkers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Clear any potential stale marker caches
      try {
        if (typeof window !== 'undefined') {
          if (window.sessionStorage) {
            window.sessionStorage.removeItem('nwis_markers_cache');
            window.sessionStorage.removeItem('well_markers');
          }
          if (window.localStorage) {
            window.localStorage.removeItem('nwis_markers_cache');
            window.localStorage.removeItem('well_markers');
          }
        }
      } catch (_) {}

      let response;
      const cacheBustUrl = `/api/wells/map-markers?include_new=true&_t=${Date.now()}`;
      const fetchOpts = {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
        },
      };

      try {
        response = await fetch(cacheBustUrl, fetchOpts);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
      } catch (fetchErr) {
        response = await fetch(`http://127.0.0.1:8000${cacheBustUrl}`, fetchOpts);
      }

      if (!response.ok) {
        throw new Error(`Failed to fetch well markers (Status ${response.status})`);
      }

      const data = await response.json();
      setCount(data.count);
      setDataSource(data.data_source || 'REAL_PUBLIC');
      setMarkers(data.markers ? [...data.markers] : []);
    } catch (err) {
      console.error('Error fetching well markers:', err);
      setError(err.message || 'Unable to load well locations');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWellCount();
    fetchWellMarkers();
  }, []);

  const handleNavigate = (tab, param) => {
    setCurrentTab(tab);
    if (tab === 'live') {
      const wid = param || activeWellId || 'WELL-000001';
      setActiveWellId(wid);
      const targetUrl = wid && wid !== 'WELL-000001' ? `/live?well_id=${encodeURIComponent(wid)}` : '/live';
      window.history.pushState({}, '', targetUrl);
    } else if (tab === 'map') {
      window.history.pushState({}, '', '/');
    } else if (tab === 'wcr-upload') {
      window.history.pushState({}, '', '/wcr-upload');
    } else if (tab === 'dashboard') {
      window.history.pushState({}, '', '/dashboard');
    } else if (tab === 'intelligence') {
      const wid = param || activeWellId || 'WELL-000001';
      setActiveWellId(wid);
      window.history.pushState({}, '', `/well/${wid}`);
    } else if (tab === 'documents') {
      window.history.pushState({}, '', '/documents');
    } else if (tab === 'upload-document') {
      window.history.pushState({}, '', '/wcr-upload');
    } else if (tab === 'review-document') {
      const docId = param || activeDocumentId;
      if (docId) {
        setActiveDocumentId(docId);
        window.history.pushState({}, '', `/documents/${docId}/review`);
      }
    } else if (tab === 'institutional-memory') {
      window.history.pushState({}, '', '/institutional-memory');
    } else if (tab === 'about-us') {
      window.history.pushState({}, '', '/about-us');
    }
  };

  const handleSelectWell = (well) => {
    setSelectedWell(well);
    const wid = well?.well_id || (well?.id && well.id.startsWith('WELL-') ? well.id : null);
    if (wid) {
      setActiveWellId(wid);
    }
  };

  const handleWellCreated = async (createdData) => {
    try {
      await Promise.all([fetchWellMarkers(), fetchWellCount()]);
    } catch (e) {
      console.error('Failed to reload markers or count:', e);
    }
    const wellObj = {
      id: createdData.well_id,
      well_id: createdData.well_id,
      well_name: createdData.well_name,
      latitude: createdData.latitude,
      longitude: createdData.longitude,
      operator: createdData.operator,
      field: createdData.field,
      basin: createdData.basin,
      total_depth: createdData.total_depth,
      formation: createdData.formation,
      coordinate_source: createdData.coordinate_source,
      source_document: createdData.source_document,
      is_new_well: true,
    };
    setSelectedWell(wellObj);
    setActiveWellId(createdData.well_id);
    handleNavigate('map');
  };

  const handleOpenIntelligence = (wellId) => {
    handleNavigate('intelligence', wellId);
  };

  return (
    <div className="app-container">
      <Header
        count={count}
        markers={markers}
        onSelectWell={handleSelectWell}
        dataSource={dataSource}
        currentTab={currentTab}
        onNavigate={handleNavigate}
        activeWellId={activeWellId}
      />

      <main className="main-content-viewport">
        {currentTab === 'live' && (
          <LiveDashboardPage
            initialWellId={activeWellId || 'WELL-000001'}
            onNavigate={handleNavigate}
            onSelectWell={(w) => {
              const wid = typeof w === 'string' ? w : w?.well_id;
              if (wid) {
                setActiveWellId(wid);
                const targetUrl = wid !== 'WELL-000001' ? `/live?well_id=${encodeURIComponent(wid)}` : '/live';
                window.history.replaceState({}, '', targetUrl);
              }
            }}
          />
        )}

        {currentTab === 'map' && (
          <WellMap
            markers={markers}
            selectedWell={selectedWell}
            isLoading={isLoading}
            error={error}
            onRetry={fetchWellMarkers}
            onOpenIntelligence={handleOpenIntelligence}
            onOpenLive={(wid) => handleNavigate('live', wid)}
            onViewWcr={(docId) => handleNavigate('review-document', docId)}
          />
        )}

        {currentTab === 'dashboard' && (
          <DashboardPage onNavigate={handleNavigate} />
        )}

        {currentTab === 'intelligence' && (
          <WellIntelligencePage
            wellId={activeWellId}
            onNavigate={handleNavigate}
          />
        )}

        {currentTab === 'documents' && (
          <DocumentsPage onNavigate={handleNavigate} />
        )}

        {(currentTab === 'wcr-upload' || currentTab === 'upload-document') && (
          <WcrUploadPage
            onNavigate={handleNavigate}
            onWellCreated={handleWellCreated}
          />
        )}

          {currentTab === 'review-document' && (
            <DocumentReviewPage
              documentId={activeDocumentId}
              onNavigate={handleNavigate}
            />
          )}

          {currentTab === 'institutional-memory' && (
            <InstitutionalMemoryPage onNavigate={handleNavigate} />
          )}

          {currentTab === 'about-us' && (
            <AboutUsPage onNavigate={handleNavigate} />
          )}
        </main>
    </div>
  );
}
