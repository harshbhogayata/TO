import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import { jobsService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useParams, useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import './JobDetail.css';

const JobDetail = () => {
    const { addToast } = useToast();
    const { id } = useParams();
    const navigate = useNavigate();
    const { isAuthenticated, user } = useAuthStore();
    const [job, setJob] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [applying, setApplying] = useState(false);
    const [hasApplied, setHasApplied] = useState(false);

    usePageTitle(job?.title || 'Job Detail');

    useEffect(() => {
        if (!id) return;
        setIsLoading(true);
        jobsService.getJob(id)
            .then(({ data }) => {
                setJob(data);
                setHasApplied(data.has_applied || false);
            })
            .catch((err) => setError(getApiErrorMessage(err, 'Job not found or no longer available.')))
            .finally(() => setIsLoading(false));
    }, [id]);

    const handleApply = async () => {
        if (!isAuthenticated) { navigate('/auth'); return; }
        if (hasApplied || applying) return;
        setApplying(true);
        try {
            await jobsService.applyToJob(id, {});
            setHasApplied(true);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Application failed.'), 'error');
        } finally {
            setApplying(false);
        }
    };

    if (isLoading) {
        return (
            <div className="jd-wrapper">
                <div className="jd-tape-bar">
                    <span>// TalentOrbit</span>
                    <span>// Loading Job...</span>
                </div>
                <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', fontSize: '11px', textTransform: 'uppercase', opacity: 0.4 }}>
                    Loading job details...
                </div>
            </div>
        );
    }

    if (error || !job) {
        return (
            <div className="jd-wrapper">
                <div className="jd-tape-bar">
                    <span>// TalentOrbit</span>
                    <span>// Error</span>
                </div>
                <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '16px', fontSize: '11px', textTransform: 'uppercase', opacity: 0.6 }}>
                    <p>{error || 'Job not found.'}</p>
                    <button className="btn-outline" onClick={() => navigate('/jobs')}>← Back to Job Board</button>
                </div>
            </div>
        );
    }

    const salary = job.salary_min && job.salary_max
        ? `$${Number(job.salary_min).toLocaleString()} – $${Number(job.salary_max).toLocaleString()}`
        : job.salary_min
            ? `From $${Number(job.salary_min).toLocaleString()}`
            : 'Salary not disclosed';

    return (
        <div className="jd-wrapper">
            <div className="jd-tape-bar">
                <span>// TalentOrbit Job Detail</span>
                <span>// {job.status?.toUpperCase() || 'OPEN'}</span>
                <span>// {job.work_mode?.replace('_', ' ').toUpperCase() || '—'}</span>
            </div>

            <div className="jd-app-container">
                <aside className="jd-sidebar">
                    <div className="jd-brand" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>Talent<br />Orbit</div>
                    <nav>
                        <div onClick={() => navigate('/')} className="jd-nav-item"><span className="jd-nav-num">[01]</span> <span className="jd-nav-label">Home</span></div>
                        <div onClick={() => navigate('/auth')} className="jd-nav-item"><span className="jd-nav-num">[02]</span> <span className="jd-nav-label">Login</span></div>
                        <div onClick={() => navigate('/jobs')} className="jd-nav-item active" style={{ background: 'rgba(255,255,255,0.1)' }}><span className="jd-nav-num">[03]</span> <span className="jd-nav-label">Job Board</span></div>
                        <div onClick={() => navigate('/register/user')} className="jd-nav-item"><span className="jd-nav-num">[04]</span> <span className="jd-nav-label">Register</span></div>
                    </nav>
                </aside>

                <main className="jd-main-content">
                    <header className="jd-content-header">
                        <div>
                            <h1 className="jd-page-title">{job.title}</h1>
                            <p className="jd-company-meta">{job.company_name} • {job.location || 'Remote'} • {job.work_mode?.replace('_', ' ')}</p>
                        </div>
                        <div className="jd-header-actions">
                            <div style={{ textAlign: 'right', marginBottom: '16px' }}>
                                <span style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', opacity: 0.6 }}>{salary}</span>
                            </div>
                            <button
                                className={hasApplied ? 'btn-outline' : 'btn-primary'}
                                style={{ minWidth: '140px', opacity: applying ? 0.6 : 1, cursor: applying || hasApplied ? 'not-allowed' : 'pointer' }}
                                onClick={handleApply}
                                disabled={applying || hasApplied}
                            >
                                {hasApplied ? '✓ Applied' : applying ? 'Applying...' : 'Apply Now'}
                            </button>
                        </div>
                    </header>

                    <div className="jd-detail-grid">
                        <div className="jd-description-col">
                            <div className="jd-section-header"><h2>Role Description</h2></div>
                            <div className="jd-description-body">
                                {job.description
                                    ? job.description.split('\n').map((p, i) => p.trim() ? <p key={i}>{p}</p> : <br key={i} />)
                                    : <p style={{ opacity: 0.4 }}>No description provided.</p>
                                }
                            </div>

                            {job.requirements && (
                                <>
                                    <div className="jd-section-header" style={{ marginTop: '20px' }}><h2>Requirements</h2></div>
                                    <div className="jd-description-body">
                                        {job.requirements.split('\n').map((p, i) => p.trim() ? <p key={i}>{p}</p> : <br key={i} />)}
                                    </div>
                                </>
                            )}

                            <div style={{ padding: '24px 32px', borderTop: '1px solid var(--border-color)' }}>
                                <button className="btn-outline" onClick={() => navigate('/jobs')}>← Back to Job Board</button>
                            </div>
                        </div>

                        <div className="jd-sidebar-right">
                            <div className="jd-section-header"><h2>Details</h2></div>
                            <div className="jd-detail-list">
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Job Type</span>
                                    <span className="jd-detail-value">{job.job_type?.replace('_', ' ') || '—'}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Experience</span>
                                    <span className="jd-detail-value">{job.experience_level?.replace('_', ' ').toUpperCase() || 'MID'}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Work Mode</span>
                                    <span className="jd-detail-value">{job.work_mode?.replace('_', ' ') || '—'}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Location</span>
                                    <span className="jd-detail-value">{job.location || 'Not specified'}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Salary</span>
                                    <span className="jd-detail-value">{salary}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Applications</span>
                                    <span className="jd-detail-value">{job.application_count ?? '—'}</span>
                                </div>
                                <div className="jd-detail-row">
                                    <span className="jd-detail-label">Status</span>
                                    <span className="jd-detail-value">{job.status?.toUpperCase() || 'OPEN'}</span>
                                </div>
                            </div>

                            {!isAuthenticated && (
                                <div style={{ padding: '24px', margin: '24px', border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.02)' }}>
                                    <p style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', marginBottom: '12px' }}>Sign in to apply</p>
                                    <button className="btn-primary" style={{ width: '100%' }} onClick={() => navigate('/auth')}>Login / Register</button>
                                </div>
                            )}

                            {user?.role === 'COMPANY' && (
                                <div style={{ padding: '24px', margin: '24px', border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.02)' }}>
                                    <p style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', marginBottom: '12px', opacity: 0.6 }}>You are logged in as a Company</p>
                                    <button className="btn-outline" style={{ width: '100%' }} onClick={() => navigate('/company')}>← Company Dashboard</button>
                                </div>
                            )}
                        </div>
                    </div>
                </main>
            </div>
        </div>
    );
};

export default JobDetail;
