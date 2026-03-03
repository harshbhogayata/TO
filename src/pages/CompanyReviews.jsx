import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import reviewService from '../services/reviewService';
import { useReviewStore } from '../store/reviewStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CompanyReviews.css';

/* ── helpers ────────────────────────────────────────────────── */
const renderStars = (rating) => {
    const full = Math.floor(rating);
    const half = rating - full >= 0.5;
    return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(5 - full - (half ? 1 : 0));
};

const formatDate = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
};

/* ── ReviewCard ─────────────────────────────────────────────── */
const ReviewCard = ({ review, onHelpful }) => {
    const author = review.author_display || {};
    const initials = (author.name || 'A').slice(0, 2).toUpperCase();
    const overall = review.overall_rating ?? (
        ((review.rating_culture || 0) + (review.rating_growth || 0) +
            (review.rating_compensation || 0) + (review.rating_management || 0) +
            (review.rating_worklife || 0)) / 5
    ).toFixed(1);

    return (
        <div className="cr-review-card">
            <div className="cr-review-header">
                <div className="cr-review-author-wrap">
                    <div className="cr-review-avatar">{initials}</div>
                    <div className="cr-review-author-info">
                        <h4>{author.name || 'Anonymous Employee'}</h4>
                        <p>{author.role}{author.department ? ` · ${author.department}` : ''}</p>
                    </div>
                </div>
                <div className="cr-review-meta">
                    <div className="cr-review-rating">{renderStars(overall)}</div>
                    <span>{formatDate(review.created_at)}</span>
                </div>
            </div>

            {review.headline && <h3 className="cr-review-headline">{review.headline}</h3>}

            <div className="cr-review-body">
                <div className="cr-review-section">
                    <h5>Pros</h5>
                    <p>{review.pros || '—'}</p>
                </div>
                <div className="cr-review-section">
                    <h5>Cons</h5>
                    <p>{review.cons || '—'}</p>
                </div>
            </div>

            <div className="cr-review-footer">
                <div className="cr-review-tags">
                    {review.employment_status && (
                        <span className="cr-review-tag">{review.employment_status}</span>
                    )}
                    {review.is_verified && (
                        <span className="cr-review-tag cr-review-tag--verified">Verified</span>
                    )}
                    {review.tenure_months > 0 && (
                        <span className="cr-review-tag">
                            {review.tenure_months >= 12
                                ? `${Math.floor(review.tenure_months / 12)}y ${review.tenure_months % 12}m`
                                : `${review.tenure_months}m`}
                        </span>
                    )}
                </div>
                <button
                    className={`cr-helpful-btn ${review.has_voted_helpful ? 'cr-helpful-btn--voted' : ''}`}
                    onClick={() => onHelpful(review.id)}
                >
                    Helpful ({review.helpful_count || 0})
                </button>
            </div>

            {review.company_response && (
                <div className="cr-company-response">
                    <h5>Company Response — {review.company_response.author_name}</h5>
                    <p>{review.company_response.body}</p>
                </div>
            )}
        </div>
    );
};

/* ── Main Component ─────────────────────────────────────────── */
const CompanyReviews = () => {
    const navigate = useNavigate();
    const { companyId } = useParams();
    const {
        reviews, reviewsLoading, reviewsError, totalCount,
        stats, statsLoading, filters,
        setReviews, setReviewsLoading, setReviewsError, setTotalCount,
        setStats, setStatsLoading, setFilter,
    } = useReviewStore();

    usePageTitle('Company Reviews', 'Read verified employee reviews. Transparent workplace insights.');

    /* fetch reviews */
    const fetchReviews = useCallback(async () => {
        if (!companyId) return;
        setReviewsLoading(true);
        setReviewsError(null);
        try {
            const params = {};
            if (filters.department) params.department = filters.department;
            if (filters.min_rating) params.min_rating = filters.min_rating;
            if (filters.role) params.role = filters.role;
            if (filters.ordering) params.ordering = filters.ordering;
            const { data } = await reviewService.listReviews(companyId, params);
            const list = data.results || data;
            setReviews(list);
            setTotalCount(data.count ?? list.length);
        } catch (err) {
            setReviewsError(getApiErrorMessage(err, 'Failed to load reviews.'));
        } finally {
            setReviewsLoading(false);
        }
    }, [companyId, filters, setReviews, setReviewsLoading, setReviewsError, setTotalCount]);

    /* fetch stats */
    const fetchStats = useCallback(async () => {
        if (!companyId) return;
        setStatsLoading(true);
        try {
            const { data } = await reviewService.getReviewStats(companyId);
            setStats(data);
        } catch { /* silent */ } finally {
            setStatsLoading(false);
        }
    }, [companyId, setStats, setStatsLoading]);

    useEffect(() => { fetchStats(); }, [fetchStats]);
    useEffect(() => {
        const t = setTimeout(fetchReviews, 300);
        return () => clearTimeout(t);
    }, [fetchReviews]);

    /* helpful toggle */
    const handleHelpful = async (reviewId) => {
        try {
            const { data } = await reviewService.toggleHelpful(reviewId);
            setReviews(reviews.map((r) =>
                r.id === reviewId
                    ? { ...r, helpful_count: data.helpful_count, has_voted_helpful: data.voted }
                    : r,
            ));
        } catch { /* silent */ }
    };

    /* derived */
    const categories = [
        { key: 'avg_culture', label: 'Culture' },
        { key: 'avg_growth', label: 'Growth' },
        { key: 'avg_compensation', label: 'Compensation' },
        { key: 'avg_management', label: 'Management' },
        { key: 'avg_worklife', label: 'Work-Life' },
    ];

    const sortOptions = [
        { value: '-created_at', label: 'Newest' },
        { value: 'created_at', label: 'Oldest' },
        { value: '-helpful_count', label: 'Most Helpful' },
    ];

    const ratingOptions = [
        { value: '', label: 'All Ratings' },
        { value: '4', label: '4+ Stars' },
        { value: '3', label: '3+ Stars' },
        { value: '2', label: '2+ Stars' },
    ];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Workplace Intel',
                status: 'System Status: Operational',
                info: 'Reviews: Live',
            }}
            pageTitleLine1="Company"
            pageTitleLine2="Reviews"
            headerRightContent={
                <div className="cr-header-stats">
                    <div className="cr-stat-block">
                        <h3>Total Reviews</h3>
                        <p>{stats?.total_reviews ?? '—'}</p>
                    </div>
                    <div className="cr-stat-block">
                        <h3>Avg Rating</h3>
                        <p>{stats?.overall_rating ? `${stats.overall_rating}/5` : '—'}</p>
                    </div>
                </div>
            }
        >
            <div className="cr-layout">
                {/* ── Score Panel ────────────────────────────── */}
                <aside className="cr-score-panel">
                    {/* Overall score */}
                    <div className="cr-score-overall">
                        {statsLoading ? (
                            <>
                                <Skeleton style={{ width: 80, height: 56, margin: '0 auto 8px' }} />
                                <Skeleton style={{ width: 120, height: 14, margin: '0 auto' }} />
                            </>
                        ) : (
                            <>
                                <div className="cr-score-number">{stats?.overall_rating ?? '—'}</div>
                                <div className="cr-score-stars">{renderStars(stats?.overall_rating || 0)}</div>
                                <div className="cr-score-count">{stats?.total_reviews ?? 0} Reviews</div>
                            </>
                        )}
                    </div>

                    {/* Category breakdown */}
                    <div className="cr-category-scores">
                        <h4>Score Breakdown</h4>
                        {categories.map((cat) => {
                            const val = stats?.[cat.key] ?? 0;
                            return (
                                <div key={cat.key} className="cr-category-row">
                                    <span className="cr-category-label">{cat.label}</span>
                                    <div className="cr-category-bar-wrap">
                                        <div className="cr-category-bar" style={{ width: `${(val / 5) * 100}%` }} />
                                    </div>
                                    <span className="cr-category-value">{val.toFixed ? val.toFixed(1) : val}</span>
                                </div>
                            );
                        })}
                    </div>

                    {/* Distribution */}
                    <div className="cr-distribution">
                        <h4>Distribution</h4>
                        {[5, 4, 3, 2, 1].map((star) => {
                            const count = stats?.distribution?.[String(star)] ?? 0;
                            const total = stats?.total_reviews || 1;
                            return (
                                <div key={star} className="cr-dist-row">
                                    <span className="cr-dist-label">{star}</span>
                                    <div className="cr-dist-bar-wrap">
                                        <div className="cr-dist-bar" style={{ width: `${(count / total) * 100}%` }} />
                                    </div>
                                    <span className="cr-dist-count">{count}</span>
                                </div>
                            );
                        })}
                    </div>

                    {/* Filters */}
                    <div className="cr-filters">
                        <div className="cr-filter-group">
                            <h4 className="cr-filter-title">Sort By</h4>
                            {sortOptions.map((opt) => (
                                <label key={opt.value} className="cr-filter-option">
                                    <input
                                        type="radio"
                                        name="cr-sort"
                                        checked={filters.ordering === opt.value}
                                        onChange={() => setFilter('ordering', opt.value)}
                                    />
                                    {opt.label}
                                </label>
                            ))}
                        </div>

                        <div className="cr-filter-group">
                            <h4 className="cr-filter-title">Min Rating</h4>
                            {ratingOptions.map((opt) => (
                                <label key={opt.value} className="cr-filter-option">
                                    <input
                                        type="radio"
                                        name="cr-rating"
                                        checked={filters.min_rating === opt.value}
                                        onChange={() => setFilter('min_rating', opt.value)}
                                    />
                                    {opt.label}
                                </label>
                            ))}
                        </div>
                    </div>
                </aside>

                {/* ── Reviews Content ────────────────────────── */}
                <div className="cr-content">
                    <div className="cr-search-strip">
                        <span className="cr-results-count">
                            {totalCount} Review{totalCount !== 1 ? 's' : ''}
                        </span>
                        <button
                            className="cr-write-btn"
                            onClick={() => navigate(`/reviews/${companyId}/write`)}
                        >
                            Write a Review
                        </button>
                    </div>

                    {reviewsError && <div className="cr-error-banner">{reviewsError}</div>}

                    {reviewsLoading ? (
                        <div className="cr-reviews-list">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <div key={i} className="cr-review-card">
                                    <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                                        <Skeleton style={{ width: 40, height: 40, borderRadius: '50%' }} />
                                        <div>
                                            <Skeleton style={{ width: 140, height: 16, marginBottom: 6 }} />
                                            <Skeleton style={{ width: 100, height: 12 }} />
                                        </div>
                                    </div>
                                    <Skeleton style={{ width: '60%', height: 20, marginBottom: 12 }} />
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                                        <Skeleton style={{ height: 60 }} />
                                        <Skeleton style={{ height: 60 }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="cr-reviews-list">
                            {reviews.map((review) => (
                                <ReviewCard
                                    key={review.id}
                                    review={review}
                                    onHelpful={handleHelpful}
                                />
                            ))}
                            {reviews.length === 0 && !reviewsError && (
                                <p className="cr-empty">
                                    No reviews yet. Be the first to share your experience.
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CompanyReviews;
