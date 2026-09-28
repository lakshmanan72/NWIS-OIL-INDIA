import React from 'react';
import { Maximize2 } from 'lucide-react';

export default function MapControls({ onFitAllWells }) {
  return (
    <div className="floating-map-controls">
      <button
        type="button"
        className="control-btn"
        onClick={onFitAllWells}
        title="Calculate bounds from all valid well coordinates and fit map view"
      >
        <Maximize2 size={16} />
        <span>Fit All Wells</span>
      </button>
    </div>
  );
}
