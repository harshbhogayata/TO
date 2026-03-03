/**
 * src/components/search/SearchBar.jsx
 * Autocomplete search bar with debounced suggestions, keyboard navigation,
 * and entity type tabs. Brutalist design matching TalentOrbit's editorial style.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchStore } from '../../store/searchStore';
import './Search.css';

const ENTITY_TABS = [
    { key: 'jobs', label: 'Jobs' },
    { key: 'talent', label: 'Talent' },
    { key: 'companies', label: 'Companies' },
    { key: 'all', label: 'All' },
];

const SearchBar = ({ onSearch, autoFocus = false, showTabs = true }) => {
    const {
        query, setQuery, entityType, setEntityType,
        suggestions, showSuggestions, fetchSuggestions, hideSuggestions,
    } = useSearchStore();

    const [localQuery, setLocalQuery] = useState(query);
    const [activeIndex, setActiveIndex] = useState(-1);
    const inputRef = useRef(null);
    const suggestionsRef = useRef(null);
    const debounceRef = useRef(null);

    // Sync store query → local
    useEffect(() => {
        setLocalQuery(query);
    }, [query]);

    // Debounced autocomplete
    const handleInputChange = useCallback((value) => {
        setLocalQuery(value);
        setActiveIndex(-1);

        // Clear previous debounce
        if (debounceRef.current) clearTimeout(debounceRef.current);

        debounceRef.current = setTimeout(() => {
            fetchSuggestions(value);
        }, 200);
    }, [fetchSuggestions]);

    // Cleanup debounce on unmount
    useEffect(() => {
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
    }, []);

    const submitSearch = useCallback((searchQuery) => {
        const q = (searchQuery || localQuery).trim();
        setQuery(q);
        hideSuggestions();
        if (onSearch) onSearch(q);
    }, [localQuery, setQuery, hideSuggestions, onSearch]);

    const handleKeyDown = (e) => {
        if (!showSuggestions || suggestions.length === 0) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitSearch();
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setActiveIndex((prev) => Math.min(prev + 1, suggestions.length - 1));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setActiveIndex((prev) => Math.max(prev - 1, -1));
                break;
            case 'Enter':
                e.preventDefault();
                if (activeIndex >= 0 && suggestions[activeIndex]) {
                    const selected = suggestions[activeIndex].text;
                    setLocalQuery(selected);
                    submitSearch(selected);
                } else {
                    submitSearch();
                }
                break;
            case 'Escape':
                hideSuggestions();
                setActiveIndex(-1);
                break;
            default:
                break;
        }
    };

    const handleSuggestionClick = (suggestion) => {
        setLocalQuery(suggestion.text);
        submitSearch(suggestion.text);
    };

    // Click outside to close suggestions
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (
                suggestionsRef.current &&
                !suggestionsRef.current.contains(e.target) &&
                inputRef.current &&
                !inputRef.current.contains(e.target)
            ) {
                hideSuggestions();
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [hideSuggestions]);

    return (
        <div className="search-bar-container">
            {showTabs && (
                <div className="search-entity-tabs">
                    {ENTITY_TABS.map(tab => (
                        <button
                            key={tab.key}
                            className={`search-tab ${entityType === tab.key ? 'active' : ''}`}
                            onClick={() => setEntityType(tab.key)}
                            type="button"
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>
            )}

            <div className="search-input-wrapper">
                <input
                    ref={inputRef}
                    type="text"
                    className="search-input"
                    placeholder={`SEARCH ${entityType.toUpperCase()}...`}
                    value={localQuery}
                    onChange={(e) => handleInputChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={() => { if (localQuery.length >= 2) fetchSuggestions(localQuery); }}
                    autoFocus={autoFocus}
                    autoComplete="off"
                    spellCheck="false"
                    aria-label="Search"
                    aria-expanded={showSuggestions}
                    aria-autocomplete="list"
                    aria-controls="search-suggestions-list"
                    role="combobox"
                />
                <button
                    className="search-submit-btn"
                    onClick={() => submitSearch()}
                    type="button"
                    aria-label="Submit search"
                >
                    SEARCH
                </button>
                {localQuery && (
                    <button
                        className="search-clear-btn"
                        onClick={() => {
                            setLocalQuery('');
                            setQuery('');
                            hideSuggestions();
                            inputRef.current?.focus();
                        }}
                        type="button"
                        aria-label="Clear search"
                    >
                        ×
                    </button>
                )}
            </div>

            {/* Autocomplete Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
                <ul
                    ref={suggestionsRef}
                    id="search-suggestions-list"
                    className="search-suggestions"
                    role="listbox"
                >
                    {suggestions.map((s, i) => (
                        <li
                            key={`${s.entity_type}-${s.text}-${i}`}
                            className={`suggestion-item ${i === activeIndex ? 'active' : ''}`}
                            onClick={() => handleSuggestionClick(s)}
                            onMouseEnter={() => setActiveIndex(i)}
                            role="option"
                            aria-selected={i === activeIndex}
                        >
                            <span className="suggestion-type-badge">{s.entity_type}</span>
                            <span className="suggestion-text">{s.text}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default SearchBar;
