import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { jobsService, authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import { useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './DashboardShared.css';

const UserDashboard = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    const navigate = useNavigate();
    usePageTitle('Dashboard', 'Your TalentOrbit dashboard — track applications, messages, and career progress.');
    const [applications, setApplications] = useState([]);
    const [saved, setSaved] = useState([]);
    const [profile, setProfile] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [appsRes, savedRes, meRes] = await Promise.all([
                    jobsService.myApplications(),
                    jobsService.savedJobs(),
                    authService.getMe(),
                ]);
                setApplications(appsRes.data.results || appsRes.data || []);
                setSaved(savedRes.data.results || savedRes.data || []);
                setProfile(meRes.data.profile);
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load dashboard data.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleWithdraw = async (id) => {
        try {
            await jobsService.withdrawApplication(id);
            setApplications(prev => prev.map(a => a.id === id ? { ...a, status: 'withdrawn' } : a));
        } catch (err) { addToast(getApiErrorMessage(err, 'Withdraw failed.'), 'error'); }
    };

    const handleUnsave = async (savedId) => {
        try {
            await jobsService.unsaveJob(savedId);
            setSaved(prev => prev.filter(s => s.id !== savedId));
        } catch (err) { addToast(getApiErrorMessage(err, 'Remove failed.'), 'error'); }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit v2.1 // User Terminal",
                status: `Welcome, ${user?.full_name || user?.email || 'Talent'}`,
                info: isLoading ? 'Loading...' : `${applications.length} Applications Active`
            }}
            pageTitleLine1="Career"
            pageTitleLine2="Portal"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Applications</h3>
                        <p>{isLoading ? '—' : `${applications.length} Total`}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Saved</h3>
                        <p>{isLoading ? '—' : `${saved.length} Listings`}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Plan</h3>
                        <p>{profile?.subscription_tier || 'Free'}</p>
                    </div>
                </div>
            }
        >
            {!isLoading && applications.length === 0 && saved.length === 0 ? (
                <div className="dashboard-empty">
                    <div className="empty-main">
                        <h2 className="empty-title">Welcome to TalentOrbit, {user?.full_name?.split(' ')[0] || 'there'}!</h2>
                        <p className="empty-desc">
                            {profile?.resume || profile?.skills?.length
                                ? 'Your profile is set up. Start exploring jobs and your applications will appear here.'
                                : 'Complete your profile and start applying to positions to track them here.'}
                        </p>
                        <div style={{ display: 'flex', gap: '16px', marginTop: '16px' }}>
                            <button className="btn-primary" onClick={() => navigate('/jobs')}>Browse Jobs</button>
                            <button className="btn-outline" onClick={() => navigate('/profile')}>
                                {profile?.resume ? 'View Profile' : 'Complete Profile'}
                            </button>
                        </div>
                    </div>

                    <div className="empty-sidebar">
                        <div>
                            <h3 className="sidebar-section-title">
                                {profile?.resume || profile?.skills?.length ? 'Quick Links' : 'Getting Started'}
                            </h3>
                            <div className="link-group">
                                {!profile?.resume && <a className="text-link" onClick={() => navigate('/profile')}>1. Upload Resume</a>}
                                {(!profile?.skills || profile.skills.length === 0) && <a className="text-link" onClick={() => navigate('/skills')}>2. Verify Skills</a>}
                                <a className="text-link" onClick={() => navigate('/jobs')}>
                                    {profile?.resume || profile?.skills?.length ? 'Browse Jobs' : '3. Find Your First Job'}
                                </a>
                                {(profile?.resume || profile?.skills?.length > 0) && (
                                    <>
                                        <a className="text-link" onClick={() => navigate('/skills')}>Skill Hub</a>
                                        <a className="text-link" onClick={() => navigate('/inbox')}>Messages</a>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="vertical-label" style={{ display: 'flex', alignItems: 'center' }}>
                        Onboarding // 01
                    </div>
                </div>
            ) : (
                <div className="dashboard-grid user-grid">
                    <div className="section-column border-right">
                        <div className="list-header">
                            <h2>Application Tracking</h2>
                            <button className="btn-text" onClick={() => navigate('/jobs')}>Browse Jobs</button>
                        </div>

                        {isLoading && <Skeleton.List count={4} />}

                        {!isLoading && applications.length === 0 && (
                            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                                No applications yet. <span style={{ textDecoration: 'underline', cursor: 'pointer' }} onClick={() => navigate('/jobs')}>Browse jobs →</span>
                            </div>
                        )}

                        {applications.map(app => (
                            <div key={app.id} className="data-row">
                                <div className="row-info">
                                    <span className="row-title">{app.job_title || app.job?.title}</span>
                                    <span className="row-meta">{app.company_name || app.job?.company_name} • Applied {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : '—'}</span>
                                    <div><span className="tag">{app.status}</span></div>
                                </div>
                                {!['rejected', 'withdrawn', 'offered'].includes(app.status) && (
                                    <button className="btn-outline" onClick={() => handleWithdraw(app.id)}>Withdraw</button>
                                )}
                            </div>
                        ))}

                        <div className="list-header" style={{ marginTop: '20px' }}>
                            <h2>Saved Listings</h2>
                            <button className="btn-text" onClick={() => navigate('/saved')}>View All</button>
                        </div>

                        {!isLoading && saved.length === 0 && (
                            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>No saved jobs.</div>
                        )}

                        {saved.map(s => (
                            <div key={s.id} className="data-row">
                                <div className="row-info">
                                    <span className="row-title">{s.job?.title}</span>
                                    <span className="row-meta">{s.job?.company_name} • {s.job?.work_mode}</span>
                                </div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <button className="btn-outline" onClick={() => navigate(`/jobs/${s.job?.id}`)}>View Job</button>
                                    <button className="btn-outline" onClick={() => handleUnsave(s.id)}>Remove</button>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div style={{ display: 'flex', flex: 1, flexDirection: 'row' }}>
                        <div className="right-pane" style={{ flex: 1 }}>
                            <div className="pane-section">
                                <span className="section-label">Resume Management</span>
                                <div className="resume-card">
                                    <div className="row-info">
                                        <span className="row-title" style={{ fontSize: '14px' }}>
                                            {profile?.resume ? 'Resume on file' : 'No resume uploaded'}
                                        </span>
                                        <span className="row-meta">{profile?.resume ? 'Click to view / update' : 'Go to Profile to upload'}</span>
                                    </div>
                                    <button className="btn-text" onClick={() => navigate('/profile')}>
                                        {profile?.resume ? 'Update' : 'Upload'}
                                    </button>
                                </div>
                            </div>

                            <div className="pane-section">
                                <span className="section-label">Quick Navigation</span>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '16px 0' }}>
                                    <button className="btn-outline" onClick={() => navigate('/jobs')}>Browse Job Board</button>
                                    <button className="btn-outline" onClick={() => navigate('/skills')}>Skill Hub</button>
                                    <button className="btn-outline" onClick={() => navigate('/profile')}>Edit Profile</button>
                                    <button className="btn-outline" onClick={() => navigate('/inbox')}>Messages</button>
                                </div>
                            </div>
                        </div>
                        <VerticalLabel text={`Network // Growth // ${new Date().getFullYear()}`} />
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default UserDashboard;
