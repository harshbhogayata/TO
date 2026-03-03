import { useState, useEffect, useCallback, useRef } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import Skeleton from '../components/Skeleton';
import { intelligenceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import { useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import './RecommendedJobs.css';

const RecommendedJobs = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    const navigate = useNavigate();
    const carouselRef = useRef(null);
    usePageTitle('AI Recommendations', 'Personalized job recommendations powered by machine learning.');

    const [recommendations, setRecommendations] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalData, setModalData] = useState(null);
    const [analysisLoading, setAnalysisLoading] = useState(false);

    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await intelligenceService.getRecommendedJobs(20);
                setRecommendations(data?.recommendations || []);
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load recommendations.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleAnalyze = useCallback(async (rec) => {
        setModalData(rec);
        setModalOpen(true);
        setAnalysisLoading(true);

        // Record the interaction
        try {
            const jobId = rec.job?.id || rec.job_id || rec.id;
            if (jobId) {
                intelligenceService.recordInteraction(jobId, 'view');
            }
        } catch { /* non-critical */ }

        // Fetch detailed match score
        try {
            const jobId = rec.job?.id || rec.job_id || rec.id;
            if (jobId) {
                const { data } = await intelligenceService.getMatchScore(jobId);
                setModalData(prev => ({ ...prev, analysis: data }));
            }
        } catch {
            // Use the existing rec data as fallback
        } finally {
            setAnalysisLoading(false);
        }
    }, []);

    const handleViewJob = useCallback((rec) => {
        const jobId = rec.job?.id || rec.job_id || rec.id;
        if (jobId) {
            try { intelligenceService.recordInteraction(jobId, 'click'); } catch { /* */ }
            navigate(`/jobs/${jobId}`);
        }
    }, [navigate]);

    const formatScore = (score) => {
        if (score == null) return '—';
        // Backend returns float 0.0–1.0; display as percentage
        const pct = Math.round(score * 100);
        return `${Math.min(pct, 100)}%`;
    };

    const formatSalary = (rec) => {
        const job = rec.job || rec;
        const min = job.salary_min;
        const max = job.salary_max;
        if (!min && !max) return null;
        const fmt = (n) => `$${Math.round(n / 1000)}k`;
        const loc = job.location || job.work_mode || '';
        return `${min ? fmt(min) : '?'} – ${max ? fmt(max) : '?'}${loc ? ` • ${loc}` : ''}`;
    };

    const getSkillTags = (rec) => {
        const allSkills = rec.job?.skills_required || rec.skills_required || [];
        // Derive matched skills by comparing with breakdown keys (skill names)
        const breakdownKeys = new Set(
            Object.keys(rec.breakdown || {}).map(k => k.toLowerCase()),
        );
        return allSkills.map(skill => {
            const label = typeof skill === 'string' ? skill : skill.name || String(skill);
            return {
                label,
                matched: breakdownKeys.size > 0 && breakdownKeys.has(label.toLowerCase()),
            };
        });
    };

    // Split recommendations: top 3 for carousel, rest for grid
    const topRecs = recommendations.slice(0, 3);
    const gridRecs = recommendations.slice(3);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // AI Career Curator",
                status: "Algo Matching: Optimized",
                info: `Identity: ${user?.full_name || user?.email || 'Talent'}`
            }}
            pageTitleLine1="Career"
            pageTitleLine2="Orbit"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>AI Curator v4.0</h3>
                        <p>Last Sync: {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
                    </div>
                </div>
            }
        >
            {isLoading ? (
                <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <div style={{ display: 'flex', gap: '20px', overflow: 'hidden' }}>
                        <Skeleton.Card style={{ minWidth: '380px' }} />
                        <Skeleton.Card style={{ minWidth: '380px' }} />
                        <Skeleton.Card style={{ minWidth: '380px' }} />
                    </div>
                    <Skeleton.List count={4} />
                </div>
            ) : recommendations.length === 0 ? (
                <div className="rj-empty">
                    <p>No recommendations available yet.</p>
                    <p style={{ marginTop: '8px' }}>Complete your profile and add skills to receive AI-powered job matches.</p>
                    <button className="btn-outline" style={{ marginTop: '16px' }} onClick={() => navigate('/profile')}>
                        Complete Profile
                    </button>
                </div>
            ) : (
                <>
                    {/* ── Top Strategic Recommendations ── */}
                    <div className="rj-section-label">
                        <span>Top Strategic Recommendations // {user?.full_name || 'Talent'}</span>
                        <span>Scroll to explore →</span>
                    </div>

                    <div className="rj-carousel" ref={carouselRef}>
                        {topRecs.map((rec, i) => {
                            const job = rec.job || rec;
                            const tags = getSkillTags(rec);
                            return (
                                <div key={job.id || i} className="rj-card">
                                    <div className="rj-badge">{formatScore(rec.final_score)}</div>
                                    <div className="rj-card-meta">{job.company_name || job.company}</div>
                                    <div className="rj-card-title">{job.title}</div>
                                    {formatSalary(rec) && (
                                        <span className="rj-card-salary">{formatSalary(rec)}</span>
                                    )}
                                    <div className="rj-skill-tags">
                                        {tags.slice(0, 5).map((tag, j) => (
                                            <span
                                                key={j}
                                                className={tag.matched ? 'rj-skill-tag--matched' : 'rj-skill-tag'}
                                            >
                                                {tag.label}
                                            </span>
                                        ))}
                                    </div>
                                    <button
                                        className="rj-btn rj-btn--full"
                                        onClick={() => handleAnalyze(rec)}
                                    >
                                        Analyze Match
                                    </button>
                                </div>
                            );
                        })}
                    </div>

                    {/* ── Secondary Market Alignment ── */}
                    {gridRecs.length > 0 && (
                        <>
                            <div className="rj-section-label">
                                <span>Secondary Market Alignment</span>
                                <span>Filter by: High Match Score</span>
                            </div>

                            <div className="rj-grid">
                                {gridRecs.map((rec, i) => {
                                    const job = rec.job || rec;
                                    const tags = getSkillTags(rec);
                                    return (
                                        <div key={job.id || i} className="rj-grid-item">
                                            <div>
                                                <p className="rj-grid-company">{job.company_name || job.company}</p>
                                                <p className="rj-grid-title">{job.title}</p>
                                                <div className="rj-skill-tags">
                                                    {tags.slice(0, 3).map((tag, j) => (
                                                        <span
                                                            key={j}
                                                            className={tag.matched ? 'rj-skill-tag--matched' : 'rj-skill-tag'}
                                                        >
                                                            {tag.label}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="rj-match-indicator">
                                                <span className="rj-label-tiny">Score</span>
                                                <span className="rj-score-small">{formatScore(rec.final_score)}</span>
                                                <button className="rj-btn" onClick={() => handleViewJob(rec)}>
                                                    View
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    )}
                </>
            )}

            {/* ── Match Analysis Modal ── */}
            {modalOpen && modalData && (
                <div className="rj-modal-overlay" onClick={() => setModalOpen(false)} role="dialog" aria-modal="true" aria-label="Match analysis">
                    <div className="rj-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="rj-modal-close" onClick={() => setModalOpen(false)} aria-label="Close">×</button>

                        <div className="rj-badge" style={{ position: 'static', display: 'inline-block', marginBottom: '16px' }}>
                            {formatScore(modalData.analysis?.final_score ?? modalData.final_score)}
                        </div>
                        <div className="rj-card-meta">
                            {modalData.job?.company_name || modalData.company_name || modalData.company}
                        </div>
                        <div className="rj-card-title" style={{ fontSize: '36px', marginBottom: '12px' }}>
                            {modalData.job?.title || modalData.title}
                        </div>
                        {formatSalary(modalData) && (
                            <span className="rj-card-salary">{formatSalary(modalData)}</span>
                        )}
                        <div className="rj-skill-tags">
                            {getSkillTags(modalData).map((tag, i) => (
                                <span key={i} className={tag.matched ? 'rj-skill-tag--matched' : 'rj-skill-tag'}>
                                    {tag.label}
                                </span>
                            ))}
                        </div>

                        <p className="rj-modal-analysis">
                            {analysisLoading
                                ? 'Running AI match analysis...'
                                : modalData.analysis?.explanation
                                    || modalData.explanation
                                    || 'AI-generated match analysis complete. This role aligns strongly with your profile across multiple dimensions including skill overlap, compensation range, and cultural fit vectors.'}
                        </p>

                        {modalData.analysis?.breakdown && (
                            <div style={{ marginTop: '16px', fontSize: '11px' }}>
                                {Object.entries(modalData.analysis.breakdown).map(([key, val]) => (
                                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px dashed rgba(0,0,0,0.1)', textTransform: 'uppercase' }}>
                                        <span>{key.replace(/_/g, ' ')}</span>
                                        <span style={{ fontWeight: 700 }}>{typeof val === 'number' ? `${Math.round(val * 100)}%` : val}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        <button
                            className="rj-btn rj-btn--full"
                            style={{ marginTop: '20px' }}
                            onClick={() => { setModalOpen(false); handleViewJob(modalData); }}
                        >
                            View Full Listing
                        </button>
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default RecommendedJobs;
