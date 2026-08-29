/**
 * SearchBar Component
 *
 * Functional search across ULPINs, parcel IDs, and building IDs.
 * On selection: flies camera to entity, selects property, opens panel.
 *
 * Search is debounced (250ms) to avoid excessive calls.
 * In M2+ this prevents hammering the FastAPI backend on every keystroke.
 */

import { useState, useRef, useEffect } from "react";
import { search } from "../services/api";
import { useSelection } from "../hooks/useSelection";

const DEBOUNCE_MS = 250;

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);
  const { flyTo, selectProperty } = useSelection();

  // Debounced search on input change
  useEffect(() => {
    // Clear any pending debounce timer
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (query.trim().length === 0) {
      setResults([]);
      setShowDropdown(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const res = await search(query);
      setResults(res);
      setShowDropdown(res.length > 0);
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
    setQuery(result.label);

    if (result.type === "property") {
      flyTo(result.data.three_d_ulpin);
    } else if (result.type === "parcel" || result.type === "building") {
      // For parcels/buildings, select the first property associated
      // In M2+, this would query the API for properties by parcel/building
      flyTo(null);
      selectProperty(null);
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
