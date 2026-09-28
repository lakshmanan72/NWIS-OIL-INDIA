import React from 'react';
import { Compass, Navigation, Layers, ShieldAlert, ArrowRight, X, ExternalLink } from 'lucide-react';

export default function NearbyPanel({
  activeWell,
  nearbyData,
  isLoadingNearby,
  radiusKm,
  onChangeRadius,
  onClose,
  onOpenIntelligence,
}) {
  if (!activeWell) return null;

  // Authoritative Backend with Frontend Defensive Check (Section 6 & 16)
  const nearbyWells = (nearbyData?.nearby_wells || []).filter(
    (w) => w && w.distance_km != null && Number(w.distance_km) <= Number(radiusKm)
  );

  return (
    <div className="nearby-panel-overlay">
      <div className="nearby-panel-header">
        <div className="active-well-badge">
          <span className="star-icon">★</span>
          <div>
            <div className="active-well-id">
              {activeWell.well_id || 'Identity Unresolved'}
              {activeWell.source_id && activeWell.well_id && (
                <span style={{ fontSize: '0.75rem', opacity: 0.8, marginLeft: '6px', fontWeight: 'normal' }}>
                  ({activeWell.source_id})
                </span>
              )}
            </div>
            <div className="active-well-name">{activeWell.well_name}</div>
          </div>
        </div>
        <button className="close-panel-btn" onClick={onClose} title="Close Panel">
          <X size={18} />
        </button>
      </div>

      <div className="nearby-panel-body">
        {/* Active Well Metadata Summary */}
        <div className="active-meta-grid">
          <div className="meta-item">
            <span className="meta-lbl">Operator</span>
            <span className="meta-val">{activeWell.operator || 'ONGC'}</span>
          </div>
          <div className="meta-item">
            <span className="meta-lbl">Basin</span>
            <span className="meta-val">{activeWell.basin || 'Public Basin'}</span>
          </div>
          <div className="meta-item">
            <span className="meta-lbl">Field / Block</span>
            <span className="meta-val">
              {activeWell.field ? `${activeWell.field} / ${activeWell.block}` : 'Public Grid'}
            </span>
          </div>
          <div className="meta-item">
            <span className="meta-lbl">Coordinates</span>
            <span className="meta-val coord">
              {Number(activeWell.latitude).toFixed(4)}°, {Number(activeWell.longitude).toFixed(4)}°
            </span>
          </div>
        </div>

        {/* Radius Selector */}
        <div className="radius-control-section">
          <div className="radius-title-row">
            <span className="radius-title">Search Radius:</span>
            <span className="radius-value-pill">{radiusKm} km</span>
          </div>
          <div className="radius-presets">
            {[5, 10, 25, 50, 100].map((r) => (
              <button
                key={r}
                className={`radius-preset-btn ${radiusKm === r ? 'active' : ''}`}
                onClick={() => onChangeRadius(r)}
              >
                {r} km
              </button>
            ))}
          </div>
        </div>

        {/* Action Button: Open Well Intelligence Page */}
        <button
          className="open-intel-btn"
          onClick={() => {
            const wid = activeWell?.well_id;
            if (wid && activeWell?.identity_status !== 'UNRESOLVED') {
              onOpenIntelligence(wid);
            } else {
              alert('Well identity could not be resolved.');
            }
          }}
          disabled={!activeWell?.well_id || activeWell?.identity_status === 'UNRESOLVED'}
          title={!activeWell?.well_id ? 'Well identity could not be resolved.' : 'Analyze in Well Intelligence'}
        >
          <span>Analyze in Well Intelligence</span>
          <ArrowRight size={16} />
        </button>

        {/* Nearby Wells List */}
        <div className="nearby-wells-header">
          <span className="nearby-count-title">
            Nearby Offset Wells ({isLoadingNearby ? '...' : nearbyWells.length})
          </span>
          <span className="nearby-subtext">Within {radiusKm} km</span>
        </div>

        {isLoadingNearby ? (
          <div className="nearby-loading">
            <div className="loading-spinner-sm"></div>
            <span>Scanning spatial relationship graph...</span>
          </div>
        ) : nearbyWells.length === 0 ? (
          <div className="nearby-empty">
            <Navigation size={28} className="empty-icon" />
            <p>No offset wells found within {radiusKm} km.</p>
            <span>Try increasing the radius to 50 km or 100 km.</span>
          </div>
        ) : (
          <div className="nearby-wells-list">
            {nearbyWells.map((w) => (
              <div key={w.well_id} className="nearby-well-card">
                <div className="nearby-card-top">
                  <div className="nearby-id-group">
                    <span className="nearby-dot">●</span>
                    <span className="nearby-id">{w.well_id}</span>
                  </div>
                  <span className="nearby-distance-tag">{w.distance_km} km</span>
                </div>

                <div className="nearby-name">{w.well_name}</div>

                <div className="nearby-badges">
                  {w.same_field && <span className="badge badge-field">Same Field</span>}
                  {w.same_block && <span className="badge badge-block">Same Block</span>}
                  {w.same_basin && <span className="badge badge-basin">Same Basin</span>}
                  <span className="badge badge-prox">{w.proximity_class || 'Offset'}</span>
                </div>

                <div className="nearby-details-row">
                  <span>{w.operator}</span>
                  <span>•</span>
                  <span>{w.well_type || 'Well'}</span>
                  {w.total_depth && (
                    <>
                      <span>•</span>
                      <span>TD: {w.total_depth.toFixed(0)}m</span>
                    </>
                  )}
                  <button
                    className="quick-view-link"
                    onClick={() => onOpenIntelligence(w.well_id)}
                    title="View Well Intelligence Profile"
                  >
                    View <ExternalLink size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
