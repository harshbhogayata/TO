import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { jobsService, getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './MyApplications.css';

const STATUS_ORDER = ['pending', 'reviewing', 'shortlisted', 'interviewing', 'offered', 'rejected', 'withdrawn'];
const STATUS_LABELS = {
    pending: 'Pending Review',
    reviewing: 'In Review',
    shortlisted: 'Shortlisted',
    interviewing: 'Interviewing',
    offered: 'Offered',
    rejected: 'Rejected',
    withdrawn: 'Withdrawn',
};

const MyApplications = () => {
    const { addToast } = useToast();
    usePageTitle('My Applications');
    const [applications, setApplications] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        jobsService.myApplications()
            .then(({ data }) => setApplications(data.results || data))
            .catch((err) => setError(getApiErrorMessage(err, 'Failed to load applications.')))
            .finally(() => setIsLoading(false));
    }, []);

    const handleWithdraw = async (appId) => {
        if (!window.confirm('Withdraw this application?')) return;
        try {
            await jobsService.withdrawApplication(appId);
            setApplications(prev => prev.map(a => a.id === appId ? { ...a, status: 'withdrawn' } : a));
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Withdraw failed.'), 'error');
        }
    };

    const stats = {
        total: applications.length,
        active: applications.filter(a => !['rejected', 'withdrawn'].includes(a.status)).length,
        interviews: applications.filter(a => a.status === 'interviewing').length,
        offers: applications.filter(a => a.status === 'offered').length,
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // My Applications",
                status: isLoading ? "Loading..." : `${stats.total} Total Submissions`,
                info: `Active: ${stats.active} | Interviews: ${stats.interviews}`
            }}
            pageTitleLine1="My"
            pageTitleLine2="Applications"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Total</h3><p>{stats.total}</p></div>
                    <div className="stat-block"><h3>Active</h3><p>{stats.active}</p></div>
                    <div className="stat-block"><h3>Interviews</h3><p>{stats.interviews}</p></div>
                    <div className="stat-block"><h3>Offers</h3><p>{stats.offers}</p></div>
                </div>
            }
        >
            <div className="applications-grid">
                <div className="applications-list">
                    <div className="list-header">
                        <h2>Submissions</h2>
                        <span style={{ fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>{stats.total} Records</span>
                    </div>

                    {isLoading && (
                        <div style={{ padding: '40px 32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            Loading applications...
                        </div>
                    )}

                    {error && (
                        <div style={{ padding: '40px 32px', fontSize: '11px', color: '#b00', textTransform: 'uppercase' }}>
                            ⚠ {error}
                        </div>
                    )}

                    {!isLoading && !error && applications.length === 0 && (
                        <div style={{ padding: '60px 32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            No applications yet. Head to the Job Board to find opportunities.
                        </div>
                    )}

                    {applications.map((app) => {
                        const statusIdx = STATUS_ORDER.indexOf(app.status);
                        const isTerminal = ['rejected', 'withdrawn'].includes(app.status);
                        return (
                            <div key={app.id} className="application-row">
                                <div className="app-meta">
                                    <div className="app-title-row">
                                        <span className="app-job-title">{app.job_title || app.job?.title || 'Untitled Role'}</span>
                                        <span className={`app-status-badge status-${app.status}`}>
                                            {STATUS_LABELS[app.status] || app.status}
                                        </span>
                                    </div>
                                    <span className="app-company">{app.company_name || app.job?.company_name || '—'}</span>
                                    <span className="app-date">Applied: {app.applied_at ? new Date(app.applied_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</span>
                                </div>

                                {/* Timeline Progress Bar */}
                                <div className="app-timeline">
                                    {STATUS_ORDER.slice(0, 6).map((s, i) => (
                                        <div
                                            key={s}
                                            className={`timeline-dot ${i <= statusIdx && !isTerminal ? 'reached' : ''} ${app.status === s ? 'current' : ''}`}
                                            title={STATUS_LABELS[s]}
                                        />
                                    ))}
                                </div>

                                <div className="app-actions">
                                    {!isTerminal && (
                                        <button
                                            className="btn-outline"
                                            style={{ padding: '6px 12px', fontSize: '10px', color: '#900', borderColor: '#900' }}
                                            onClick={() => handleWithdraw(app.id)}
                                        >
                                            Withdraw
                                        </button>
                                    )}
                                    {isTerminal && (
                                        <span style={{ fontSize: '10px', opacity: 0.4, textTransform: 'uppercase' }}>{app.status}</span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div style={{ display: 'flex' }}>
                    <div className="applications-sidebar">
                        <div className="list-header"><h2>Status Key</h2></div>
                        {STATUS_ORDER.map(s => (
                            <div key={s} className="status-key-row">
                                <span className={`app-status-badge status-${s}`}>{STATUS_LABELS[s]}</span>
                            </div>
                        ))}
                    </div>
                    <VerticalLabel text="Application Pipeline // Status" />
                </div>
            </div>
        </DashboardLayout>
    );
};

export default MyApplications;
