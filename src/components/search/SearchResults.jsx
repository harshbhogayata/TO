/**
 * src/components/search/SearchResults.jsx
 * Renders search results with entity-type labels, relevance rank indicators,
 * highlighted text, and click tracking. Supports all entity types.
 */
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchStore } from '../../store/searchStore';
import Skeleton from '../Skeleton';
import './Search.css';

const SearchResults = () => {
    const {
        results, totalCount, isLoading, error, searchMeta, hasSearched,
        entityType, page, setPage, trackClick,
    } = useSearchStore();
    const navigate = useNavigate();

    const handleResultClick = useCallback((result, index) => {
        trackClick(result.id, index + 1);

        // Navigate based on entity type
        if (entityType === 'all') {
            // Unified results have a url field
            if (result.url) navigate(result.url);
        } else if (entityType === 'jobs') {
            navigate(`/jobs/${result.id}`);
        } else if (entityType === 'talent') {
            // No dedicated talent profile page for now — could be added
        } else if (entityType === 'companies') {
            // No dedicated company page for now — could be added
        }
    }, [entityType, navigate, trackClick]);

    // Loading state
    if (isLoading) {
        return (
            <div className="search-results">
                <div className="results-loading">
                    <Skeleton.List count={6} />
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="search-results">
                <div className="results-error">
                    <span className="error-icon">!</span>
                    <p>{error}</p>
                </div>
            </div>
        );
    }

    // Empty state — never searched
    if (!hasSearched) {
        return null;
    }

    // No results
    if (hasSearched && results.length === 0) {
        return (
            <div className="search-results">
                <div className="results-empty">
                    <h3>No Results Found</h3>
                    <p>Try different keywords, adjust your filters, or check for typos.</p>
                </div>
            </div>
        );
    }

    const responseTime = searchMeta?.response_time_ms;
    const pageSize = 20;
    const totalPages = Math.ceil(totalCount / pageSize);

    return (
        <div className="search-results">
            {/* Results header */}
            <div className="results-header">
                <span className="results-count">
                    {totalCount} result{totalCount !== 1 ? 's' : ''}
                </span>
                {responseTime != null && (
                    <span className="results-time">
                        {responseTime < 100 ? `${responseTime.toFixed(0)}ms` : `${(responseTime / 1000).toFixed(2)}s`}
                    </span>
                )}
            </div>

            {/* Result cards */}
            <div className="results-list">
                {results.map((result, index) => (
                    <ResultCard
                        key={`${result.entity_type || entityType}-${result.id}`}
                        result={result}
                        index={index}
                        entityType={entityType}
                        onClick={() => handleResultClick(result, index)}
                    />
                ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="results-pagination">
                    <button
                        className="pagination-btn"
                        disabled={page <= 1}
                        onClick={() => setPage(page - 1)}
                    >
                        ← PREV
                    </button>
                    <span className="pagination-info">
                        Page {page} of {totalPages}
                    </span>
                    <button
                        className="pagination-btn"
                        disabled={page >= totalPages}
                        onClick={() => setPage(page + 1)}
                    >
                        NEXT →
                    </button>
                </div>
            )}
        </div>
    );
};


/**
 * Individual result card — adapts display based on entity type.
 */
const ResultCard = ({ result, index, entityType, onClick }) => {
    // For unified search, result has entity_type field
    const type = result.entity_type || entityType;

    return (
        <article
            className="result-card"
            onClick={onClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter') onClick(); }}
        >
            <div className="result-card-inner">
                {/* Left: type badge + rank */}
                <div className="result-meta-left">
                    <span className={`entity-badge entity-${type}`}>
                        {type.toUpperCase()}
                    </span>
                    {result.rank > 0 && result.rank < 1 && (
                        <span className="rank-indicator" title={`Relevance: ${(result.rank * 100).toFixed(0)}%`}>
                            <span
                                className="rank-bar"
                                style={{ width: `${Math.min(result.rank * 100, 100)}%` }}
                            />
                        </span>
                    )}
                </div>

                {/* Center: content */}
                <div className="result-content">
                    <div className="result-title-row">
                        {result.image_url && (
                            <img
                                src={result.image_url}
                                alt=""
                                className="result-avatar"
                                loading="lazy"
                            />
                        )}
                        <div>
                            <h3 className="result-title">
                                {result.title || result.headline}
                            </h3>
                            {(result.subtitle || result.company_name) && (
                                <span className="result-subtitle">
                                    {result.subtitle || result.company_name}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Description / snippet */}
                    {(result.description || result.bio || result.mission_statement) && (
                        <p className="result-description">
                            {(result.description || result.bio || result.mission_statement || '').slice(0, 200)}
                        </p>
                    )}

                    {/* Tags / meta */}
                    <div className="result-tags">
                        {/* Jobs-specific */}
                        {type === 'jobs' || type === 'job' ? (
                            <>
                                {result.location && <span className="result-tag">{result.location}</span>}
                                {(result.job_type || result.meta?.job_type) && (
                                    <span className="result-tag">
                                        {(result.job_type || result.meta?.job_type || '').replace('_', '-')}
                                    </span>
                                )}
                                {(result.work_mode || result.meta?.work_mode) && (
                                    <span className="result-tag">
                                        {(result.work_mode || result.meta?.work_mode || '').replace('_', '-')}
                                    </span>
                                )}
                                {(result.salary_display || result.meta?.salary_display) && (
                                    <span className="result-tag salary-tag">
                                        {result.salary_display || result.meta?.salary_display}
                                    </span>
                                )}
                                {result.match_score > 0 && (
                                    <span className={`result-tag match-tag ${result.match_score >= 75 ? 'high' : result.match_score >= 50 ? 'mid' : 'low'}`}>
                                        {result.match_score}% Match
                                    </span>
                                )}
                            </>
                        ) : null}

                        {/* Talent-specific */}
                        {type === 'talent' && (
                            <>
                                {result.location && <span className="result-tag">{result.location}</span>}
                                {result.is_open_to_work && <span className="result-tag open-tag">Open to Work</span>}
                                {(result.skills || result.meta?.skills || []).slice(0, 4).map(skill => (
                                    <span key={skill} className="result-tag skill-tag">{skill}</span>
                                ))}
                            </>
                        )}

                        {/* Company-specific */}
                        {type === 'company' || type === 'companies' ? (
                            <>
                                {(result.industry || result.meta?.industry) && (
                                    <span className="result-tag">{result.industry || result.meta?.industry}</span>
                                )}
                                {(result.headquarters || result.meta?.headquarters) && (
                                    <span className="result-tag">{result.headquarters || result.meta?.headquarters}</span>
                                )}
                                {(result.is_verified || result.meta?.is_verified) && (
                                    <span className="result-tag verified-tag">✓ Verified</span>
                                )}
                            </>
                        ) : null}
                    </div>
                </div>

                {/* Right: position number */}
                <div className="result-position">
                    {String(index + 1).padStart(2, '0')}
                </div>
            </div>
        </article>
    );
};

export default SearchResults;
