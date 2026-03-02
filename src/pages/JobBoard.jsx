import { useState, useEffect, useCallback } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { jobsService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './JobBoard.css';

const JobBoard = () => {
    const { addToast } = useToast();
    const [jobs, setJobs] = useState([]);
    const [selectedJob, setSelectedJob] = useState(null);
    const [search, setSearch] = useState('');
    const [workMode, setWorkMode] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [applyLoading, setApplyLoading] = useState(false);
    const [applySuccess, setApplySuccess] = useState(false);
    const [error, setError] = useState('');
    const [resetKey, setResetKey] = useState(0);
    const { user } = useAuthStore();
    usePageTitle('Job Board', 'Browse open positions from verified companies. Filter by skills, work mode, and experience level.');

    const renderMatchBadge = (score) => {
        let badgeClass = 'high-match';
        if (score < 75) badgeClass = 'low-match';
        else if (score < 85) badgeClass = 'medium-match';

        return (
            <div className={`match-badge ${badgeClass}`}>
                <span className="match-value">{score}%</span>
                <span className="match-label">Match</span>
            </div>
        );
    };

    const fetchJobs = useCallback(async () => {
        setIsLoading(true);
        setError('');
        try {
            const params = {};
            if (search) params.search = search;
            if (workMode) params.work_mode = workMode;
            const { data } = await jobsService.listJobs(params);
            setJobs(data.results || data);
            if (data.results?.length > 0 || data.length > 0) {
                setSelectedJob((data.results || data)[0]);
            }
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load jobs. Please try again.'));
        } finally {
            setIsLoading(false);
        }
    }, [search, workMode, resetKey]);

    useEffect(() => {
        const debounce = setTimeout(fetchJobs, 300);
        return () => clearTimeout(debounce);
    }, [fetchJobs]);

    const handleApply = async () => {
        if (!selectedJob || user?.role !== 'TALENT') return;
        setApplyLoading(true);
        try {
            await jobsService.applyToJob(selectedJob.id, {});
            setApplySuccess(true);
            setJobs(prev => prev.map(j =>
                j.id === selectedJob.id ? { ...j, has_applied: true } : j
            ));
            setSelectedJob(prev => ({ ...prev, has_applied: true }));
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Application failed.'), 'error');
        } finally {
            setApplyLoading(false);
        }
    };

    const handleSave = async (job) => {
        try {
            if (job.is_saved) {
                // Use saved_record_id (bookmark ID) for deletion, not job.id
                const recordId = job.saved_record_id || job.id;
                await jobsService.unsaveJob(recordId);
                setJobs(prev => prev.map(j =>
                    j.id === job.id ? { ...j, is_saved: false, saved_record_id: null } : j
                ));
                if (selectedJob?.id === job.id) {
                    setSelectedJob(prev => ({ ...prev, is_saved: false, saved_record_id: null }));
                }
            } else {
                const { data } = await jobsService.saveJob(job.id);
                // Store the returned saved-record ID for future unsave
                const savedRecordId = data?.id || null;
                setJobs(prev => prev.map(j =>
                    j.id === job.id ? { ...j, is_saved: true, saved_record_id: savedRecordId } : j
                ));
                if (selectedJob?.id === job.id) {
                    setSelectedJob(prev => ({ ...prev, is_saved: true, saved_record_id: savedRecordId }));
                }
            }
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Save action failed. Please try again.'), 'error');
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit v2.1 // Job Board",
                status: `Live Listings: ${jobs.length}`,
                info: "View: [04] Job Board"
            }}
            pageTitleLine1="Job"
            pageTitleLine2="Board"
            headerRightContent={
                <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase', fontSize: '14px' }}>Live Positions</div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(24px, 3vw, 40px)' }}>
                        {isLoading ? '...' : jobs.length}
                    </div>
                </div>
            }
        >
            {!isLoading && !error && jobs.length === 0 ? (
                <div className="empty-state-container">
                    <div className="empty-main">
                        <div className="illustration-placeholder"></div>
                        <h2 className="empty-title">No matches found</h2>
                        <p className="empty-desc">We couldn't find any job openings matching your current selection. Adjust your filters to widen your search.</p>
                        <button className="btn-primary" onClick={() => { setSearch(''); setWorkMode(''); setResetKey(k => k + 1); }}>Reset All Filters</button>
                    </div>

                    <div className="empty-sidebar">
                        <div>
                            <h3 className="sidebar-section-title">Suggested</h3>
                            <div className="pill-list">
                                <button className="filter-pill" onClick={() => setWorkMode('remote')}>Remote Only</button>
                                <button className="filter-pill" onClick={() => setSearch('Design')}>Design</button>
                                <button className="filter-pill" onClick={() => setSearch('Engineering')}>Engineering</button>
                                <button className="filter-pill" onClick={() => setSearch('Product')}>Product</button>
                            </div>
                        </div>

                        <div className="link-group">
                            <h3 className="sidebar-section-title">Quick Actions</h3>
                            <a className="text-link" style={{ cursor: 'pointer' }} onClick={() => { setSearch(''); setWorkMode(''); setResetKey(k => k + 1); }}>Browse all jobs</a>
                        </div>
                    </div>

                    <div className="vertical-label" style={{ display: 'flex', alignItems: 'center' }}>
                        Filter Results // 00
                    </div>
                </div>
            ) : (
                <div className="job-interface">
                    {/* ── Left: Filters + List ── */}
                    <div className="filter-panel">
                        <input
                            type="text"
                            className="search-bar"
                            placeholder="SEARCH KEYWORDS..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />

                        <div className="filter-group">
                            <h4>Work Mode</h4>
                            {['', 'remote', 'on_site', 'hybrid'].map(mode => (
                                <label key={mode} className="filter-option">
                                    <input
                                        type="radio"
                                        name="workmode"
                                        checked={workMode === mode}
                                        onChange={() => setWorkMode(mode)}
                                    />
                                    {mode === '' ? 'All' : mode.replace('_', '-').toUpperCase()}
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* ── Middle: Job Cards ── */}
                    <div className="jobs-list">
                        {isLoading && (
                            <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '0' }}>
                                <Skeleton.List count={5} />
                            </div>
                        )}
                        {!isLoading && error && (
                            <div style={{ padding: '32px', color: '#b00', fontFamily: 'var(--font-sans)', fontSize: '11px' }}>{error}</div>
                        )}
                        {jobs.map(job => (
                            <div
                                key={job.id}
                                className={`job-card ${selectedJob?.id === job.id ? 'active' : ''}`}
                                onClick={() => { setSelectedJob(job); setApplySuccess(false); }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <div>
                                        <span className="company">{job.company_name}</span>
                                        <h3 className="title">{job.title}</h3>
                                        <div className="meta">
                                            <span>{job.location || job.work_mode?.replace('_', '-').toUpperCase()}</span>
                                            <span>{job.salary_display}</span>
                                        </div>
                                    </div>
                                    {job.match_score > 0 && renderMatchBadge(job.match_score)}
                                </div>
                                {job.has_applied && (
                                    <span style={{ fontSize: '9px', fontWeight: 700, color: '#006400', textTransform: 'uppercase', marginTop: '12px', display: 'block' }}>✓ Applied</span>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* ── Right: Job Detail ── */}
                    <div className="job-detail">
                        {selectedJob ? (
                            <>
                                <div className="detail-header">
                                    <span className="company" style={{ fontSize: '14px', textTransform: 'uppercase', marginBottom: '8px', display: 'block' }}>
                                        {selectedJob.company_name}
                                    </span>
                                    <h2>{selectedJob.title}</h2>
                                    <div style={{ marginTop: '16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                        {selectedJob.job_type && <span className="tag">{selectedJob.job_type.replace('_', '-')}</span>}
                                        {selectedJob.work_mode && <span className="tag">{selectedJob.work_mode.replace('_', '-')}</span>}
                                        {selectedJob.location && <span className="tag">{selectedJob.location}</span>}
                                        {selectedJob.salary_display && <span className="tag">{selectedJob.salary_display}</span>}
                                    </div>
                                </div>

                                <div className="description-text">
                                    <p style={{ marginBottom: '20px', whiteSpace: 'pre-wrap' }}>
                                        {selectedJob.description}
                                    </p>
                                    {selectedJob.requirements && (
                                        <>
                                            <h4 style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase', marginBottom: '12px' }}>Requirements:</h4>
                                            <p style={{ marginBottom: '20px', whiteSpace: 'pre-wrap' }}>{selectedJob.requirements}</p>
                                        </>
                                    )}
                                    {selectedJob.skills_required?.length > 0 && (
                                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
                                            {selectedJob.skills_required.map(skill => (
                                                <span key={skill} style={{ padding: '4px 10px', border: '1px solid var(--border-color)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase' }}>
                                                    {skill}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <div style={{ display: 'flex', gap: '12px', padding: '24px 32px', borderTop: '1px solid var(--border-color)' }}>
                                    {user?.role === 'TALENT' && (
                                        <>
                                            <button
                                                className="apply-btn"
                                                onClick={handleApply}
                                                disabled={applyLoading || selectedJob.has_applied || applySuccess}
                                                style={{
                                                    flex: 1,
                                                    opacity: (selectedJob.has_applied || applySuccess) ? 0.6 : 1,
                                                    cursor: (selectedJob.has_applied || applySuccess) ? 'default' : 'pointer'
                                                }}
                                            >
                                                {applyLoading ? 'Submitting...'
                                                    : (selectedJob.has_applied || applySuccess) ? '✓ Application Submitted'
                                                        : 'Submit Application'}
                                            </button>
                                            <button
                                                className={selectedJob.is_saved ? 'btn-outline' : 'btn-outline'}
                                                onClick={() => handleSave(selectedJob)}
                                                style={{ padding: '12px 20px', fontSize: '11px', fontWeight: 700 }}
                                            >
                                                {selectedJob.is_saved ? '★ Saved' : '☆ Save'}
                                            </button>
                                        </>
                                    )}
                                </div>
                            </>
                        ) : (
                            <div style={{ padding: '40px', fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>
                                Select a position to view details.
                            </div>
                        )}
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default JobBoard;
