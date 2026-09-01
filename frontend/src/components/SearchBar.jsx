/**
 * SearchBar Component
 *
 * Searches the FastAPI backend via GET /api/search.
 * On selection: flies camera to entity, selects property, opens panel.
 * Search is debounced (250ms).
 */

import { useState, useRef, useEffect } from "react";
import { search } from "../services/api";
import { useSelection } from "../hooks/useSelection";

const DEBOUNCE_MS = 250;

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);
  const { flyTo, selectProperty, flyToBuilding, selectBuilding } = useSelection();

  // Debounced search on input change
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (query.trim().length === 0) {
      setResults([]);
      setShowDropdown(false);
      setSearchError(null);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      try {
        setSearchError(null);
        const res = await search(query);
        setResults(res);
        setShowDropdown(res.length > 0);
      } catch (e) {
        setSearchError("Search unavailable");
        setResults([]);
        setShowDropdown(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (result) => {
    setShowDropdown(false);
    setQuery(result.label || result.building_id || result.ulpin);

    if (result.type === "property") {
      const ulpin = result.ulpin || result.data?.ulpin || result.id;
      flyTo(ulpin);
      selectProperty(ulpin);
    } else if (result.type === "building") {
      const buildingId = result.building_id || result.id;
      flyToBuilding(buildingId, {
        latitude: result.latitude,
        longitude: result.longitude,
        height: result.height,
      });
      selectBuilding(buildingId);
    } else if (result.type === "parcel") {
      setQuery(result.data?.parcel_id || result.label);
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case "property": return "🏠";
      case "parcel": return "📐";
      case "building": return "🏢";
      default: return "📍";
    }
  };

  return (
    <div className="search-bar" ref={dropdownRef}>
      <div className="search-input-wrapper">
        <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          placeholder="Search ULPIN, parcel ID, building ID..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="search-input"
        />
      </div>

      {searchError && (
        <div className="search-error">{searchError}</div>
      )}

      {showDropdown && (
        <div className="search-dropdown">
          {results.map((result, idx) => (
            <button
              key={`${result.type}-${result.id}-${idx}`}
              className="search-result-item"
              onClick={() => handleSelect(result)}
            >
              <span className="search-result-icon">{getTypeIcon(result.type)}</span>
              <div className="search-result-text">
                <span className="search-result-label">{result.label}</span>
                <span className="search-result-type">{result.type}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
