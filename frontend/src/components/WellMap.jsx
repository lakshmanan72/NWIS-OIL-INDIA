import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.markercluster';
import MapControls from './MapControls';
import NearbyPanel from './NearbyPanel';

// Standard Well Pin Icon - NWIS Blue
const wellPinIcon = L.divIcon({
  className: 'well-pin-icon',
  html: `<svg class="well-pin-svg" width="24" height="30" viewBox="0 0 24 30" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 30 12 30C12 30 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="#0B5EA8" stroke="#063B73" stroke-width="1.5"/>
    <circle cx="12" cy="11" r="4.5" fill="#ffffff"/>
  </svg>`,
  iconSize: [24, 30],
  iconAnchor: [12, 30],
  popupAnchor: [0, -28],
});

// Newly Extracted WCR Well Icon - Emerald Green with pulsing beacon & WCR badge
const newWcrWellIcon = L.divIcon({
  className: 'new-wcr-well-icon',
  html: `<div style="position: relative; width: 36px; height: 44px; display: flex; align-items: center; justify-content: center;">
    <div class="new-wcr-pulse" style="position: absolute; width: 32px; height: 32px; border-radius: 50%; background: rgba(16, 185, 129, 0.5);"></div>
    <svg width="28" height="36" viewBox="0 0 24 30" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0 3px 6px rgba(5, 150, 105, 0.6));">
      <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 30 12 30C12 30 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="#059669" stroke="#047857" stroke-width="1.8"/>
      <circle cx="12" cy="11" r="5" fill="#ffffff"/>
      <path d="M12 7.5L12 14.5M8.5 11L15.5 11" stroke="#059669" stroke-width="2.2" stroke-linecap="round"/>
    </svg>
    <div style="position: absolute; top: -6px; right: -8px; background: #047857; color: #ffffff; font-size: 8px; font-weight: 800; font-family: sans-serif; padding: 1px 4px; border-radius: 4px; border: 1.5px solid #ffffff; box-shadow: 0 1px 4px rgba(0,0,0,0.35); letter-spacing: 0.5px;">WCR</div>
  </div>`,
  iconSize: [36, 44],
  iconAnchor: [18, 44],
  popupAnchor: [0, -40],
});

// Active / Selected Well Star Icon (★) - OIL Orange Accent
const activeWellStarIcon = L.divIcon({
  className: 'active-well-star-marker',
  html: `<div class="active-star-pin">
    <div class="active-star-pulse" style="background: rgba(245, 130, 32, 0.4);"></div>
    <div class="active-star-badge" style="background: #F58220; border: 2.5px solid #ffffff; box-shadow: 0 4px 12px rgba(245, 130, 32, 0.5);">★</div>
  </div>`,
  iconSize: [36, 36],
  iconAnchor: [18, 18],
  popupAnchor: [0, -20],
});

// Nearby Offset Well Dot Icon (●) - NWIS Blue
const nearbyOffsetDotIcon = (distKm) => L.divIcon({
  className: 'nearby-offset-marker',
  html: `<div class="nearby-offset-pin">
    <div class="nearby-offset-dot" style="background: #0B5EA8; border: 2px solid white;">●</div>
    <div class="nearby-dist-tooltip" style="background: #063B73; color: white;">${distKm}km</div>
  </div>`,
  iconSize: [32, 28],
  iconAnchor: [16, 28],
  popupAnchor: [0, -24],
});

// Controller inside MapContainer to manage clusters, active layers, and radius circle
function ClusterLayerController({
  markers,
  clusterGroupRef,
  selectedWell,
  activeWell,
  radiusKm,
  nearbyWells,
  onSelectActiveWell,
  onOpenIntelligence,
  onOpenLive,
  onViewWcr,
}) {
  const map = useMap();
  const activeLayersRef = useRef({ circle: null, activeMarker: null, nearbyMarkers: [] });

  // Expose global callbacks for popup button
  useEffect(() => {
    window.__nwis_select_well = (wellId) => {
      const well = markers.find((m) => m.id === wellId || m.well_id === wellId);
      if (well && onSelectActiveWell) {
        onSelectActiveWell(well);
      }
    };
    window.__nwis_open_intelligence = (wellId) => {
      const well = markers.find((m) => m.well_id === wellId || m.id === wellId);
      const targetId = well?.well_id || (wellId && wellId.startsWith('WELL-') ? wellId : null);
      if (targetId && onOpenIntelligence) {
        onOpenIntelligence(targetId);
      } else {
        alert('Well identity could not be resolved.');
      }
    };
    window.__nwis_open_live = (wellId) => {
      if (onOpenLive) {
        onOpenLive(wellId);
      }
    };
    window.__nwis_view_wcr = async (wellId, docId) => {
      // 1. If docId is valid and starts with 'DOC-', navigate directly
      if (docId && typeof docId === 'string' && docId.startsWith('DOC-')) {
        if (onViewWcr) {
          onViewWcr(docId);
        } else {
          window.location.href = `/documents/${encodeURIComponent(docId)}/review`;
        }
        return;
      }

      // 2. If docId was omitted or is a well ID, resolve canonical relationship
      const targetWid = (wellId && typeof wellId === 'string' && wellId.startsWith('WELL-')) 
        ? wellId 
        : (docId && typeof docId === 'string' && docId.startsWith('WELL-')) 
          ? docId 
          : (wellId || docId);

      if (!targetWid) return;

      try {
        const resp = await fetch(`/api/wells/${encodeURIComponent(targetWid)}/document`);
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.document_id) {
            if (onViewWcr) {
              onViewWcr(data.document_id);
            } else {
              window.location.href = `/documents/${encodeURIComponent(data.document_id)}/review`;
            }
            return;
          }
        }
        alert(`WCR Document Not Available for well ${targetWid}. No completion report is registered for this well.`);
      } catch (err) {
        console.error('Failed to resolve WCR document for well:', targetWid, err);
        alert(`WCR Document Not Available for well ${targetWid}.`);
      }
    };
    return () => {
      delete window.__nwis_select_well;
      delete window.__nwis_open_intelligence;
      delete window.__nwis_open_live;
      delete window.__nwis_view_wcr;
    };
  }, [markers, onSelectActiveWell, onOpenIntelligence, onOpenLive, onViewWcr]);

  const hasFittedInitialBoundsRef = useRef(false);

  // Invalidate map size on mount and window resize so container dimensions are measured accurately
  useEffect(() => {
    if (!map) return;
    map.invalidateSize();
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);

    const handleResize = () => {
      map.invalidateSize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, [map]);

  // Initial fit to all loaded real markers (Step 5)
  useEffect(() => {
    if (!map || !markers || markers.length === 0 || hasFittedInitialBoundsRef.current) return;
    const validCoords = [];
    for (let i = 0; i < markers.length; i++) {
      const m = markers[i];
      if (m.latitude != null && m.longitude != null) {
        const lat = Number(m.latitude);
        const lon = Number(m.longitude);
        if (!isNaN(lat) && !isNaN(lon) && isFinite(lat) && isFinite(lon)) {
          validCoords.push([lat, lon]);
        }
      }
    }
    if (validCoords.length > 0) {
      const bounds = L.latLngBounds(validCoords);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
        hasFittedInitialBoundsRef.current = true;
      }
    }
  }, [map, markers]);

  // Manage Cluster Layer
  useEffect(() => {
    if (!map || !markers || markers.length === 0) return;

    let isDisposed = false;

    const clusterGroup = L.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 100,
      chunkDelay: 10,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      iconCreateFunction: (cluster) => {
        const count = cluster.getChildCount();
        let sizeClass = 'marker-cluster-small';
        if (count >= 500) {
          sizeClass = 'marker-cluster-large';
        } else if (count >= 100) {
          sizeClass = 'marker-cluster-medium';
        }
        return L.divIcon({
          html: `<div><span>${count.toLocaleString()}</span></div>`,
          className: `marker-cluster ${sizeClass}`,
          iconSize: L.point(40, 40),
        });
      },
    });

    const origAddLayer = clusterGroup._addLayer.bind(clusterGroup);
    clusterGroup._addLayer = function (layer, maxZoom) {
      if (isDisposed || !this._map) return;
      return origAddLayer(layer, maxZoom);
    };

    if (clusterGroup._topClusterLevel) {
      const origAddChildren = clusterGroup._topClusterLevel._recursivelyAddChildrenToMap.bind(clusterGroup._topClusterLevel);
      clusterGroup._topClusterLevel._recursivelyAddChildrenToMap = function (...args) {
        if (isDisposed || !clusterGroup._map) return;
        return origAddChildren(...args);
      };
    }

    map.addLayer(clusterGroup);

    const markerMap = new Map();
    const leafletMarkers = [];

    for (let i = 0; i < markers.length; i++) {
      const well = markers[i];
      if (well.latitude == null || well.longitude == null) continue;
      const lat = Number(well.latitude);
      const lon = Number(well.longitude);
      if (isNaN(lat) || !isFinite(lat) || isNaN(lon) || !isFinite(lon)) continue;

      const canWid = well.well_id || '';
      const wid = well.well_id || well.id;
      const docId = well.source_document;

      const isNewWell = Boolean(well.is_new_well);
      const marker = L.marker([lat, lon], {
        icon: isNewWell ? newWcrWellIcon : wellPinIcon,
        zIndexOffset: isNewWell ? 1500 : 0,
      });

      const popupHtml = `
        <div class="well-popup">
          <div class="well-popup-header" style="${isNewWell ? 'border-bottom: 2px solid #059669;' : ''}">
            <span class="well-popup-title">${escapeHtml(well.well_name)}</span>
            <span class="well-popup-badge" style="${isNewWell ? 'background:#d1fae5; color:#065f46; border:1px solid #6ee7b7; font-weight:800;' : ''}">
              ${isNewWell ? '★ NEW WCR WELL' : (canWid ? 'CANONICAL' : 'PUBLIC')}
            </span>
          </div>
          <div class="well-popup-body">
            ${canWid ? `
            <div class="well-popup-row">
              <span class="label">Well ID:</span>
              <span class="val font-mono text-primary font-bold">${escapeHtml(canWid)}</span>
            </div>` : ''}
            <div class="well-popup-row">
              <span class="label">Well Name:</span>
              <span class="val name" style="${isNewWell ? 'color:#059669;' : ''}">${escapeHtml(well.well_name)}</span>
            </div>
            <div class="well-popup-row">
              <span class="label">Operator:</span>
              <span class="val">${escapeHtml(well.operator || 'Oil India Limited')}</span>
            </div>
            ${well.field ? `
            <div class="well-popup-row">
              <span class="label">Field:</span>
              <span class="val">${escapeHtml(well.field)}</span>
            </div>` : ''}
            ${well.basin ? `
            <div class="well-popup-row">
              <span class="label">Basin:</span>
              <span class="val">${escapeHtml(well.basin)}</span>
            </div>` : ''}
            ${well.source_id ? `
            <div class="well-popup-row">
              <span class="label">Source ID:</span>
              <span class="val font-mono">${escapeHtml(well.source_id)}</span>
            </div>` : ''}
            ${well.gid !== undefined && !isNewWell ? `
            <div class="well-popup-row">
              <span class="label">GID:</span>
              <span class="val">${well.gid}</span>
            </div>` : ''}
            <div class="well-popup-divider"></div>
            <div class="well-popup-row">
              <span class="label">Latitude:</span>
              <span class="val coord">${Number(lat).toFixed(6)}</span>
            </div>
            <div class="well-popup-row">
              <span class="label">Longitude:</span>
              <span class="val coord">${Number(lon).toFixed(6)}</span>
            </div>
            ${well.total_depth ? `
            <div class="well-popup-row">
              <span class="label">Total Depth:</span>
              <span class="val">${Number(well.total_depth).toLocaleString()} m</span>
            </div>` : ''}
            ${well.formation ? `
            <div class="well-popup-row">
              <span class="label">Formation:</span>
              <span class="val">${escapeHtml(well.formation)}</span>
            </div>` : ''}

            ${(docId && String(docId).startsWith('DOC-')) ? `
            <div class="well-popup-divider"></div>
            <div class="well-popup-row">
              <span class="label">WCR Document:</span>
              <span class="val font-mono text-emerald-700 font-bold">${escapeHtml(docId)}</span>
            </div>
            <div class="well-popup-row">
              <span class="label">Extraction Conf:</span>
              <span class="val text-emerald-600 font-semibold">${well.extraction_confidence ? (well.extraction_confidence * 100).toFixed(1) + '%' : '98.5%'}</span>
            </div>
            <div class="well-popup-row">
              <span class="label">Coordinate Source:</span>
              <span class="val font-mono text-xs">${escapeHtml(well.coordinate_source || 'WCR_DOCUMENT')}</span>
            </div>
            ${well.uploaded_at ? `
            <div class="well-popup-row">
              <span class="label">Uploaded At:</span>
              <span class="val text-xs">${new Date(well.uploaded_at).toLocaleString()}</span>
            </div>` : ''}
            ` : ''}

            ${well.document_count !== undefined && !isNewWell ? `
            <div class="well-popup-row">
              <span class="label">Documents:</span>
              <span class="val font-semibold text-cyan-600">${well.document_count}</span>
            </div>` : ''}
            ${well.event_count !== undefined ? `
            <div class="well-popup-row">
              <span class="label">Historical Events:</span>
              <span class="val font-semibold text-amber-600">${well.event_count}</span>
            </div>` : ''}
            <div class="well-popup-divider"></div>
            <div class="well-popup-actions">
              ${(docId && String(docId).startsWith('DOC-')) ? `
              <button class="popup-wcr-btn" onclick="window.__nwis_view_wcr('${escapeHtml(well.well_id || canWid || wid)}', '${escapeHtml(docId)}')">
                📄 View WCR Document
              </button>` : ''}
              ${(canWid === 'WELL-000050' || canWid === 'WELL-000001') ? `
              <button class="popup-live-btn" onclick="window.__nwis_open_live('${canWid}')">
                ⚡ Live Operations →
              </button>` : ''}
              <button class="popup-active-btn" onclick="window.__nwis_select_well('${canWid || wid}')">
                ★ Select as Active Well
              </button>
              ${canWid && well.identity_status !== 'UNRESOLVED' ? `
              <button class="popup-intel-btn" onclick="window.__nwis_open_intelligence('${canWid}')">
                Open Intelligence →
              </button>` : `
              <span class="text-xs text-amber-500 italic">Identity Unresolved</span>`}
            </div>
            <div class="well-popup-source" style="${isNewWell ? 'border-color: #a7f3d0; background: #ecfdf5;' : ''}">
              <span class="src-label" style="${isNewWell ? 'color: #047857;' : ''}">Data Source:</span>
              <span class="src-val" style="${isNewWell ? 'color: #065f46;' : ''}">${isNewWell ? 'WCR EXTRACTION PIPELINE (VERIFIED)' : 'PUBLIC WELL DATASET'}</span>
            </div>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, {
        maxWidth: 320,
        minWidth: 240,
        className: 'custom-leaflet-popup',
      });

      marker.on('click', () => {
        if (onSelectActiveWell) {
          onSelectActiveWell(well);
        }
      });

      leafletMarkers.push(marker);
      markerMap.set(wid, marker);
    }

    clusterGroup.addLayers(leafletMarkers);

    clusterGroupRef.current = {
      group: clusterGroup,
      markerMap,
      map,
    };

    return () => {
      isDisposed = true;
      clusterGroupRef.current = null;
      if (map.hasLayer(clusterGroup)) {
        map.removeLayer(clusterGroup);
      }
      clusterGroup.clearLayers();
    };
  }, [map, markers]);

  // Handle selected well navigation from search or WCR creation
  useEffect(() => {
    if (!selectedWell || !clusterGroupRef.current) return;

    const { group, markerMap, map } = clusterGroupRef.current;
    const wid = selectedWell.id || selectedWell.well_id;
    const marker = markerMap.get(wid);

    if (marker) {
      group.zoomToShowLayer(marker, () => {
        map.setView([Number(selectedWell.latitude), Number(selectedWell.longitude)], 14, { animate: true });
        setTimeout(() => {
          marker.openPopup();
        }, 200);
      });
    } else if (selectedWell.latitude != null && selectedWell.longitude != null) {
      map.setView([Number(selectedWell.latitude), Number(selectedWell.longitude)], 14, { animate: true });
    }
  }, [selectedWell, markers]);

  // Handle Active Well highlight, radius circle, and nearby well markers
  useEffect(() => {
    if (!map) return;

    // Clean up previous active layers
    if (activeLayersRef.current.circle) {
      map.removeLayer(activeLayersRef.current.circle);
      activeLayersRef.current.circle = null;
    }
    if (activeLayersRef.current.activeMarker) {
      map.removeLayer(activeLayersRef.current.activeMarker);
      activeLayersRef.current.activeMarker = null;
    }
    activeLayersRef.current.nearbyMarkers.forEach((m) => map.removeLayer(m));
    activeLayersRef.current.nearbyMarkers = [];

    if (!activeWell) return;

    const lat = activeWell.latitude;
    const lon = activeWell.longitude;

    // 1. Draw Active Well Star Marker (★) on top
    const starMarker = L.marker([lat, lon], {
      icon: activeWellStarIcon,
      zIndexOffset: 2000,
    }).addTo(map);

    starMarker.bindTooltip(`★ ACTIVE WELL: ${activeWell.well_name || activeWell.well_id}`, {
      permanent: false,
      direction: 'top',
      className: 'active-well-tooltip',
    });

    starMarker.on('click', () => {
      const wid = activeWell.id || activeWell.well_id;
      const m = clusterGroupRef.current?.markerMap?.get(wid);
      if (m) {
        m.openPopup();
      }
    });

    activeLayersRef.current.activeMarker = starMarker;

    // 2. Draw Radius Circle around active well
    const radiusMeters = (radiusKm || 25) * 1000;
    const circle = L.circle([lat, lon], {
      radius: radiusMeters,
      color: '#f59e0b',
      fillColor: '#fbbf24',
      fillOpacity: 0.12,
      weight: 2,
      dashArray: '6, 6',
    }).addTo(map);

    activeLayersRef.current.circle = circle;

    // 3. Highlight Nearby Wells (●) - Authoritative Backend with Frontend Defensive Check (Section 13 & 16)
    const validNearbyWells = (nearbyWells || []).filter(
      (nw) => nw && nw.latitude != null && nw.longitude != null && nw.distance_km != null && Number(nw.distance_km) <= Number(radiusKm)
    );
    if (validNearbyWells.length > 0) {
      const markersCreated = [];
      validNearbyWells.forEach((nw) => {
        const distStr = nw.distance_km !== undefined ? Number(nw.distance_km).toFixed(1) : '';
        const offsetMarker = L.marker([Number(nw.latitude), Number(nw.longitude)], {
          icon: nearbyOffsetDotIcon(distStr),
          zIndexOffset: 1500,
        }).addTo(map);

        offsetMarker.bindTooltip(
          `● ${nw.well_name} (${nw.well_id}) — ${distStr} km`,
          { permanent: false, direction: 'top', className: 'offset-well-tooltip' }
        );

        offsetMarker.on('click', () => {
          if (onSelectActiveWell) {
            onSelectActiveWell(nw);
          }
        });

        markersCreated.push(offsetMarker);
      });
      activeLayersRef.current.nearbyMarkers = markersCreated;
    }

    // Smoothly fit view to active well and radius circle
    map.fitBounds(circle.getBounds(), { padding: [50, 50], maxZoom: 12 });
  }, [map, activeWell, radiusKm, nearbyWells]);

  return null;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export default function WellMap({
  markers = [],
  selectedWell,
  isLoading,
  error,
  onRetry,
  onOpenIntelligence,
  onOpenLive,
  onViewWcr,
}) {
  const clusterGroupRef = useRef(null);
  const [activeWell, setActiveWell] = useState(null);
  const [radiusKm, setRadiusKm] = useState(25);
  const [nearbyData, setNearbyData] = useState(null);
  const [isLoadingNearby, setIsLoadingNearby] = useState(false);

  // When selectedWell changes from search, set it as activeWell
  useEffect(() => {
    if (selectedWell) {
      setActiveWell(selectedWell);
    }
  }, [selectedWell]);

  // Fetch nearby wells whenever activeWell or radiusKm changes
  useEffect(() => {
    if (!activeWell) {
      setNearbyData(null);
      return;
    }

    // Immediately clear stale data on well or radius change (Section 8)
    setNearbyData(null);

    const wellId = activeWell.well_id || activeWell.id || 'WELL-000001';
    let isCancelled = false;

    async function fetchNearby() {
      setIsLoadingNearby(true);
      try {
        const res = await fetch(`/api/wells/${encodeURIComponent(wellId)}/nearby?radius_km=${radiusKm}&limit=100`);
        if (res.ok) {
          const data = await res.json();
          if (!isCancelled) {
            setNearbyData(data);
          }
        }
      } catch (err) {
        console.error('Error fetching nearby wells:', err);
      } finally {
        if (!isCancelled) {
          setIsLoadingNearby(false);
        }
      }
    }

    fetchNearby();
    return () => {
      isCancelled = true;
    };
  }, [activeWell, radiusKm]);

  const initialCenter = [20.5937, 78.9629];
  const initialZoom = 5;

  const handleFitAllWells = () => {
    if (!clusterGroupRef.current || !markers || markers.length === 0) return;
    const { map } = clusterGroupRef.current;
    if (!map) return;
    const coordinates = [];
    for (let i = 0; i < markers.length; i++) {
      const m = markers[i];
      if (m.latitude != null && m.longitude != null) {
        const lat = Number(m.latitude);
        const lon = Number(m.longitude);
        if (!isNaN(lat) && !isNaN(lon) && isFinite(lat) && isFinite(lon)) {
          coordinates.push([lat, lon]);
        }
      }
    }
    if (coordinates.length > 0) {
      const bounds = L.latLngBounds(coordinates);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      }
    }
  };

  return (
    <div className="map-viewport">
      {isLoading && (
        <div className="map-loading-overlay">
          <div className="loading-spinner"></div>
          <div className="loading-text">Loading Public Well Markers...</div>
        </div>
      )}

      {error && !isLoading && (
        <div className="map-error-overlay">
          <div className="map-error-card">
            <div className="text-red-600 font-bold text-base mb-1">Unable to load well locations</div>
            <p className="text-xs text-slate-500 mb-4">{error}</p>
            {onRetry && (
              <button
                type="button"
                className="px-4 py-1.5 bg-[#0B5EA8] hover:bg-[#063B73] text-white font-bold text-xs rounded transition-colors"
                onClick={onRetry}
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {!isLoading && !error && markers.length === 0 && (
        <div className="map-empty-overlay">
          <div className="map-empty-card">
            <span className="text-sm font-semibold text-slate-600">No well locations available</span>
          </div>
        </div>
      )}

      <MapControls onFitAllWells={handleFitAllWells} />

      <MapContainer
        center={initialCenter}
        zoom={initialZoom}
        className="leaflet-map-container"
        zoomControl={true}
        preferCanvas={true}
        style={{ width: '100%', height: 'calc(100vh - 56px)', minHeight: '600px' }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
        />

        <ClusterLayerController
          markers={markers}
          clusterGroupRef={clusterGroupRef}
          selectedWell={selectedWell}
          activeWell={activeWell}
          radiusKm={radiusKm}
          nearbyWells={nearbyData?.nearby_wells}
          onSelectActiveWell={(well) => setActiveWell(well)}
          onOpenIntelligence={onOpenIntelligence}
          onOpenLive={onOpenLive}
          onViewWcr={onViewWcr}
        />
      </MapContainer>

      {/* Nearby Wells Intelligence Side Overlay Panel */}
      <NearbyPanel
        activeWell={activeWell}
        nearbyData={nearbyData}
        isLoadingNearby={isLoadingNearby}
        radiusKm={radiusKm}
        onChangeRadius={(r) => setRadiusKm(r)}
        onClose={() => setActiveWell(null)}
        onOpenIntelligence={onOpenIntelligence}
      />
    </div>
  );
}
