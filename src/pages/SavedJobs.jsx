import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { jobsService, getApiErrorMessage } from '../services/api';
import { useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './SavedJobs.css';

const SavedJobs = () => {
    const { addToast } = useToast();
    const navigate = useNavigate();
    usePageTitle('Saved Jobs', 'Your bookmarked job listings — revisit and apply when ready.');
    const [savedJobs, setSavedJobs] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [applying, setApplying] = useState(null);

    useEffect(() => {
        jobsService.savedJobs()
            .then(({ data }) => setSavedJobs(data.results || data))
            .catch((err) => setError(getApiErrorMessage(err, 'Failed to load saved jobs.')))
            .finally(() => setIsLoading(false));
    }, []);

    const handleUnsave = async (savedId) => {
        try {
            // savedId is the saved-record ID (not the job ID)
            await jobsService.unsaveJob(savedId);
            setSavedJobs(prev => prev.filter(s => s.id !== savedId));
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Could not remove bookmark.'), 'error');
        }
    };

    const handleQuickApply = async (savedRecord) => {
        const jobId = savedRecord.job?.id || savedRecord.job_id;
        if (!jobId || applying === jobId) return;
        setApplying(jobId);
        try {
            await jobsService.applyToJob(jobId, {});
            setSavedJobs(prev => prev.map(s =>
                (s.job?.id || s.job_id) === jobId ? { ...s, has_applied: true, job: { ...s.job, has_applied: true } } : s
            ));
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Application failed.'), 'error');
        } finally {
            setApplying(null);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Saved Jobs",
                status: isLoading ? "Loading..." : `${savedJobs.length} Bookmarked Roles`,
                info: "Quick Apply Eligible"
            }}
            pageTitleLine1="Saved"
            pageTitleLine2="Jobs"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Saved</h3><p>{savedJobs.length} Roles</p></div>
                    <div className="stat-block"><h3>Applied</h3><p>{savedJobs.filter(s => s.job?.has_applied || s.has_applied).length} Submitted</p></div>
                </div>
            }
        >
            <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    <div className="list-header">
                        <h2>Bookmarks</h2>
                        <span style={{ fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>{savedJobs.length} Saved</span>
                    </div>

                    {isLoading && <Skeleton.List count={4} />}

                    {error && (
                        <div style={{ padding: '40px 32px', fontSize: '11px', color: '#b00', textTransform: 'uppercase' }}>
                            ⚠ {error}
                        </div>
                    )}

                    {!isLoading && !error && savedJobs.length === 0 && (
                        <div style={{ padding: '60px 32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            No saved jobs yet. Bookmark roles on the{' '}
                            <span
                                style={{ textDecoration: 'underline', cursor: 'pointer' }}
                                onClick={() => navigate('/jobs')}
                            >
                                Job Board
                            </span>
                            .
                        </div>
                    )}

                    {savedJobs.map((saved) => {
                        const job = saved.job || saved;
                        const savedId = saved.id; // The saved-record ID used for unsave
                        const hasApplied = saved.job?.has_applied || saved.has_applied || false;
                        const isApplying = applying === (job.id || saved.job_id);

                        return (
                            <div key={savedId} className="data-row">
                                <div style={{ flex: 1 }}>
                                    <div className="row-info">
                                        <span
                                            className="row-title"
                                            style={{ cursor: 'pointer' }}
                                            onClick={() => navigate(`/jobs/${job.id}`)}
                                        >
                                            {job.title || 'Untitled Role'}
                                        </span>
                                        <span className="row-meta">
                                            {job.company_name || '—'} • {job.work_mode || '—'} • {job.location || '—'}
                                        </span>
                                        {saved.saved_at && (
                                            <span style={{ fontSize: '10px', opacity: 0.4, textTransform: 'uppercase' }}>
                                                Saved: {new Date(saved.saved_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
                                    {hasApplied ? (
                                        <span style={{ fontSize: '10px', fontFamily: 'var(--font-sans)', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 }}>
                                            ✓ Applied
                                        </span>
                                    ) : (
                                        <button
                                            className="btn-primary"
                                            style={{ padding: '8px 16px', opacity: isApplying ? 0.6 : 1, cursor: isApplying ? 'not-allowed' : 'pointer' }}
                                            onClick={() => handleQuickApply(saved)}
                                            disabled={isApplying}
                                        >
                                            {isApplying ? 'Applying...' : 'Quick Apply'}
                                        </button>
                                    )}
                                    <button
                                        className="btn-outline"
                                        style={{ padding: '8px 12px', color: '#900', borderColor: '#900' }}
                                        onClick={() => handleUnsave(savedId)}
                                    >
                                        Remove
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
                <VerticalLabel text="Bookmarked Roles // Queue" />
            </div>
        </DashboardLayout>
    );
};

export default SavedJobs;
