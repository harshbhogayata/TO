import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { jobsService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './DashboardShared.css';

const CompanyDashboard = () => {
    const { addToast } = useToast();
    const { user } = useAuthStore();
    const navigate = useNavigate();
    usePageTitle('Company Dashboard', 'Manage job postings, review applicants, and grow your team with TalentOrbit.');
    const [jobs, setJobs] = useState([]);
    const [applications, setApplications] = useState({});
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        jobsService.companyJobs()
            .then(({ data }) => {
                const list = data.results || data;
                setJobs(list);
                // Load applications for ALL jobs in parallel
                if (list.length > 0) {
                    Promise.allSettled(
                        list.map(job =>
                            jobsService.jobApplications(job.id)
                                .then(r => ({ jobId: job.id, apps: r.data.results || r.data }))
                        )
                    ).then(results => {
                        const appMap = {};
                        results.forEach(r => {
                            if (r.status === 'fulfilled') {
                                appMap[r.value.jobId] = r.value.apps;
                            }
                        });
                        setApplications(appMap);
                    });
                }
            })
            .catch((err) => addToast(getApiErrorMessage(err, 'Failed to load jobs.'), 'error'))
            .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleDeleteJob = async (id) => {
        if (!window.confirm('Delete this job listing?')) return;
        try {
            await jobsService.deleteJob(id);
            setJobs(prev => prev.filter(j => j.id !== id));
        } catch (err) { addToast(getApiErrorMessage(err, 'Delete failed.'), 'error'); }
    };

    const handleUpdateStatus = async (appId, status) => {
        try {
            await jobsService.updateApplicationStatus(appId, status);
            setApplications(prev => {
                const updated = {};
                Object.entries(prev).forEach(([jobId, apps]) => {
                    updated[jobId] = apps.map(a => a.id === appId ? { ...a, status } : a);
                });
                return updated;
            });
        } catch (err) { addToast(getApiErrorMessage(err, 'Status update failed.'), 'error'); }
    };

    const allApplications = Object.values(applications).flat();

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Company Portal",
                status: `Listings: ${jobs.length} Active`,
                info: `Applicants: ${allApplications.length} Total`
            }}
            pageTitleLine1="Entity"
            pageTitleLine2="Console"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Open Roles</h3>
                        <p>{isLoading ? '—' : `${jobs.filter(j => j.status === 'open').length} Active`}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Applications</h3>
                        <p>{allApplications.length} Total</p>
                    </div>
                    <div className="stat-block">
                        <h3>Account</h3>
                        <p>{user?.email?.split('@')[0] || '—'}</p>
                    </div>
                </div>
            }
        >
            <div className="dashboard-grid company-grid">
                <div className="section-column border-right">
                    <div className="list-header">
                        <h2>Job Listings</h2>
                        <button className="btn-text" onClick={() => navigate('/company/post-job')}>
                            + Post New Role
                        </button>
                    </div>

                    {isLoading && <Skeleton.List count={4} />}
                    {!isLoading && jobs.length === 0 && (
                        <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            No job listings yet. Post your first role.
                        </div>
                    )}
                    {jobs.map(job => (
                        <div key={job.id} className="data-row">
                            <div className="row-info">
                                <span className="row-title">
                                    {job.title}
                                    <span className="badge" style={{ marginLeft: '8px', fontSize: '9px' }}>{(job.status || 'draft').toUpperCase()}</span>
                                </span>
                                <span className="row-meta">
                                    {job.application_count} Applications • {job.work_mode?.replace('_', '-').toUpperCase()} {job.location && `• ${job.location}`}
                                </span>
                                <span className="row-meta" style={{ marginTop: '4px' }}>{job.salary_display}</span>
                            </div>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px' }} onClick={() => navigate(`/company/applicants/${job.id}`)}>View Applicants ({job.application_count})</button>
                                <button className="btn-outline" style={{ color: '#900', borderColor: '#900' }} onClick={() => handleDeleteJob(job.id)}>Delete</button>
                            </div>
                        </div>
                    ))}
                </div>

                <div className="section-column" style={{ display: 'flex', flexDirection: 'row' }}>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <div className="list-header"><h2>Recent Applications</h2></div>
                        {allApplications.length === 0 ? (
                            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>No applications yet.</div>
                        ) : (
                            allApplications.slice(0, 6).map(app => (
                                <div key={app.id} className="data-row">
                                    <div className="row-info">
                                        <span className="row-title">{app.applicant_name}</span>
                                        <span className="row-meta">For: {app.job_title} • Status: {app.status}</span>
                                    </div>
                                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                        {app.status === 'pending' && (
                                            <>
                                                <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px' }} onClick={() => handleUpdateStatus(app.id, 'shortlisted')}>Shortlist</button>
                                                <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px', color: '#900', borderColor: '#900' }} onClick={() => handleUpdateStatus(app.id, 'rejected')}>Reject</button>
                                            </>
                                        )}
                                        {app.status === 'shortlisted' && (
                                            <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px' }} onClick={() => handleUpdateStatus(app.id, 'interviewing')}>→ Interview</button>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                    <VerticalLabel text="Corporate // Operations" />
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CompanyDashboard;
