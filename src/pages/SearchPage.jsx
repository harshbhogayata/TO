/**
 * src/pages/SearchPage.jsx
 * Full search experience — search bar, faceted filters, paginated results,
 * trending searches. Composes SearchBar + FacetedFilters + SearchResults.
 *
 * Route: /search?q=react&job_type=full_time&sort=relevance&page=1
 * Supports URL-driven state so search links are shareable.
 */
import { useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import SearchBar from '../components/search/SearchBar';
import FacetedFilters from '../components/search/FacetedFilters';
import SearchResults from '../components/search/SearchResults';
import { useSearchStore } from '../store/searchStore';
import usePageTitle from '../hooks/usePageTitle';
import '../components/search/Search.css';

const SearchPage = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const {
        query, entityType, filters, sort, page,
        setQuery, setEntityType, setFilters, setSort, setPage,
        executeSearch, fetchTrending, trending,
        results, totalCount, hasSearched, isLoading,
    } = useSearchStore();

    const initializedRef = useRef(false);

    usePageTitle(
        query ? `"${query}" — Search` : 'Search',
        'Search jobs, talent, and companies on TalentOrbit.'
    );

    // ─── Hydrate store from URL params on mount ──────────────────────────
    useEffect(() => {
        if (initializedRef.current) return;
        initializedRef.current = true;

        const urlQuery = searchParams.get('q') || '';
        const urlEntity = searchParams.get('entity_type') || 'jobs';
        const urlSort = searchParams.get('sort') || 'relevance';
        const urlPage = parseInt(searchParams.get('page') || '1', 10);

        // Extract filter params
        const filterKeys = [
            'job_type', 'work_mode', 'experience_level',
            'salary_min', 'salary_max', 'skills', 'location',
            'is_open_to_work', 'industry', 'is_verified',
            'posted_after', 'posted_before',
        ];
        const urlFilters = {};
        filterKeys.forEach(key => {
            const val = searchParams.get(key);
            if (val) urlFilters[key] = val;
        });

        setQuery(urlQuery);
        setEntityType(urlEntity);
        setFilters(urlFilters);
        setSort(urlSort);
        setPage(urlPage);

        // Execute search if there's a query or filters
        if (urlQuery || Object.keys(urlFilters).length > 0) {
            // Let state settle, then search
            setTimeout(() => useSearchStore.getState().executeSearch(), 0);
        }

        fetchTrending();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ─── Sync store → URL on state changes ───────────────────────────────
    useEffect(() => {
        if (!initializedRef.current) return;

        const params = {};
        if (query) params.q = query;
        if (entityType !== 'jobs') params.entity_type = entityType;
        if (sort !== 'relevance') params.sort = sort;
        if (page > 1) params.page = String(page);

        // Add active filters
        Object.entries(filters).forEach(([key, value]) => {
            if (value) params[key] = value;
        });

        setSearchParams(params, { replace: true });
    }, [query, entityType, filters, sort, page, setSearchParams]);

    // ─── Auto-execute search on filter/sort/page changes ─────────────────
    const searchTriggerRef = useRef(null);
    useEffect(() => {
        if (!initializedRef.current) return;
        if (!hasSearched && !query) return; // Don't auto-search on first load without query

        if (searchTriggerRef.current) clearTimeout(searchTriggerRef.current);
        searchTriggerRef.current = setTimeout(() => {
            executeSearch();
        }, 300);

        return () => {
            if (searchTriggerRef.current) clearTimeout(searchTriggerRef.current);
        };
    }, [filters, sort, page]); // eslint-disable-line react-hooks/exhaustive-deps

    // ─── Search handler (from SearchBar submit) ──────────────────────────
    const handleSearch = useCallback(() => {
        setPage(1);
        executeSearch();
    }, [setPage, executeSearch]);

    // ─── Trending click handler ──────────────────────────────────────────
    const handleTrendingClick = useCallback((trendQuery) => {
        setQuery(trendQuery);
        setPage(1);
        setTimeout(() => useSearchStore.getState().executeSearch(), 0);
    }, [setQuery, setPage]);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit v2.1 // Search & Discovery",
                status: hasSearched ? `Results: ${totalCount}` : 'Ready',
                info: "View: [S1] Search"
            }}
            pageTitleLine1="Search"
            pageTitleLine2="& Discovery"
            headerRightContent={
                <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase', fontSize: '14px' }}>
                        {hasSearched ? 'Results Found' : 'Search Everything'}
                    </div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(24px, 3vw, 40px)' }}>
                        {isLoading ? '...' : hasSearched ? totalCount : '∞'}
                    </div>
                </div>
            }
        >
            <div className="search-page-layout">
                {/* ─── Sidebar: Filters ─── */}
                <div className="search-sidebar">
                    <FacetedFilters entityType={entityType} />

                    {/* Trending searches */}
                    {trending.length > 0 && (
                        <div className="search-trending">
                            <h4 className="trending-title">Trending Searches</h4>
                            <div className="trending-list">
                                {trending.map((t, i) => (
                                    <button
                                        key={i}
                                        className="trending-chip"
                                        onClick={() => handleTrendingClick(t.query)}
                                        type="button"
                                    >
                                        {t.query}
                                        <span className="trending-count">({t.count})</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* ─── Main: Search Bar + Results ─── */}
                <div className="search-main">
                    <SearchBar
                        onSearch={handleSearch}
                        autoFocus
                        showTabs
                    />

                    <div style={{ marginTop: '24px' }}>
                        <SearchResults />
                    </div>

                    {/* Initial state — show prompt */}
                    {!hasSearched && !isLoading && (
                        <div style={{
                            padding: '80px 32px',
                            textAlign: 'center',
                            opacity: 0.4,
                        }}>
                            <div style={{
                                fontFamily: 'var(--font-display)',
                                fontSize: 'clamp(32px, 5vw, 64px)',
                                textTransform: 'uppercase',
                                lineHeight: 1,
                                marginBottom: '16px',
                            }}>
                                Find Your Next
                            </div>
                            <div style={{
                                fontFamily: 'var(--font-sans)',
                                fontSize: '12px',
                                textTransform: 'uppercase',
                                letterSpacing: '2px',
                            }}>
                                Search across jobs, talent, and companies
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default SearchPage;
