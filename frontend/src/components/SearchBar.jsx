import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Search, X, MapPin, Sparkles } from 'lucide-react';

export default function SearchBar({ markers = [], onSelectWell }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [canonicalResults, setCanonicalResults] = useState([]);
  const [isSearchingApi, setIsSearchingApi] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search against the FULL loaded legacy dataset (fast client-side)
  const localMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || q.length < 2) return [];

    const matches = [];
    for (let i = 0; i < markers.length; i++) {
      const well = markers[i];
      const nameMatch = well.well_name && well.well_name.toLowerCase().includes(q);
      const opMatch = well.operator && well.operator.toLowerCase().includes(q);
      const gidMatch = well.gid !== undefined && String(well.gid).includes(q);
      const idMatch = (well.well_id && well.well_id.toLowerCase().includes(q)) || (well.id && String(well.id).toLowerCase().includes(q));

      if (nameMatch || opMatch || gidMatch || idMatch) {
        matches.push(well);
        if (matches.length >= 25) break;
      }
    }
    return matches;
  }, [query, markers]);

  // Query canonical backend API when search starts with 'well' or has 3+ chars
  useEffect(() => {
    const q = query.trim();
    if (!q || q.length < 3) {
      setCanonicalResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsSearchingApi(true);
        const res = await fetch(`/api/wells/search?q=${encodeURIComponent(q)}&limit=15`);
        if (res.ok) {
          const data = await res.json();
          setCanonicalResults(data || []);
        }
      } catch (err) {
        console.error('Error searching canonical wells:', err);
      } finally {
        setIsSearchingApi(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = (well) => {
    setQuery(well.well_name || well.well_id);
    setIsOpen(false);
    if (onSelectWell) {
      onSelectWell(well);
    }
  };

  const handleClear = () => {
    setQuery('');
    setIsOpen(false);
    setCanonicalResults([]);
  };

  const totalResults = localMatches.length + canonicalResults.length;

  return (
    <div className="search-wrapper" ref={containerRef}>
      <div className="search-input-box !bg-slate-50 !border-slate-300 !rounded-lg overflow-hidden !pr-0 flex items-center h-9">
        <input
          type="text"
          className="search-input text-xs px-2.5 py-1.5 flex-1 bg-transparent text-slate-800 placeholder-slate-400 outline-none"
          placeholder="Search well, field..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setIsOpen(true);
          }}
        />
        {query && (
          <button
            type="button"
            className="search-clear-btn text-slate-400 hover:text-slate-600 px-1.5"
            onClick={handleClear}
            aria-label="Clear search"
          >
            <X size={14} />
          </button>
        )}
        <button
          type="button"
          className="h-full px-3 bg-[#062B49] hover:bg-slate-800 text-white flex items-center justify-center transition-colors cursor-pointer"
          title="Search"
          onClick={() => {
            if (query.trim().length >= 2) setIsOpen(true);
          }}
        >
          <Search size={15} />
        </button>
      </div>

      {isOpen && query.trim().length >= 2 && (
        <div className="search-dropdown">
          <div className="search-dropdown-header">
            {totalResults > 0
              ? `Found ${totalResults} matching wells`
              : 'No matching wells found'}
            {isSearchingApi && <span className="searching-indicator">Searching master...</span>}
          </div>

          {/* Canonical Master Wells Results */}
          {canonicalResults.length > 0 && (
            <div className="search-group">
              <div className="search-group-title">
                <Sparkles size={13} />
                <span>Canonical Master Wells</span>
              </div>
              {canonicalResults.map((well) => (
                <div
                  key={well.well_id}
                  className="search-result-item canonical-result"
                  onClick={() => handleSelect(well)}
                >
                  <div className="result-well-info">
                    <div className="result-well-name">
                      <span className="res-canonical-tag">{well.well_id}</span>
                      <span>{well.well_name}</span>
                    </div>
                    <div className="result-well-meta">
                      <span>{well.operator}</span>
                      <span>•</span>
                      <span>{well.basin}</span>
                      <span>•</span>
                      <span>{well.field}</span>
                    </div>
                  </div>
                  <div className="result-well-coords">
                    {Number(well.latitude).toFixed(4)}, {Number(well.longitude).toFixed(4)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Legacy Map Wells Results */}
          {localMatches.length > 0 && (
            <div className="search-group">
              {canonicalResults.length > 0 && (
                <div className="search-group-title">
                  <MapPin size={13} />
                  <span>Public Map Layer Wells</span>
                </div>
              )}
              {localMatches.map((well) => (
                <div
                  key={well.id || well.well_id}
                  className="search-result-item"
                  onClick={() => handleSelect(well)}
                >
                  <div className="result-well-info">
                    <div className="result-well-name flex items-center gap-1.5">
                      {well.well_id && (
                        <span className="res-canonical-tag text-[10px] px-1 py-0.5 rounded font-mono font-bold bg-[#e0f2fe] text-[#0369a1] border border-[#bae6fd]">
                          {well.well_id}
                        </span>
                      )}
                      <span>{well.well_name}</span>
                    </div>
                    <div className="result-well-meta">
                      <span>Op: {well.operator}</span>
                      <span>•</span>
                      <span>GID: {well.gid}</span>
                    </div>
                  </div>
                  <div className="result-well-coords">
                    {Number(well.latitude).toFixed(4)}, {Number(well.longitude).toFixed(4)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {totalResults === 0 && (
            <div className="search-empty">
              No wells found matching "{query}". Try another well name or operator.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
