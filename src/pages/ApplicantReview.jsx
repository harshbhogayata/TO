import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { jobsService, getApiErrorMessage } from '../services/api';
import { useParams } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import './ApplicantReview.css';

const STATUS_OPTIONS = ['pending', 'reviewing', 'shortlisted', 'interviewing', 'offered', 'rejected'];
const STATUS_LABELS = { pending: 'Pending', reviewing: 'Reviewing', shortlisted: 'Shortlisted', interviewing: 'Interviewing', offered: 'Offered', rejected: 'Rejected' };

const ApplicantReview = () => {
    const { addToast } = useToast();
    const { jobId } = useParams();
    usePageTitle('Applicant Review');
    const [applicants, setApplicants] = useState([]);
    const [selectedApplicant, setSelectedApplicant] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [updatingId, setUpdatingId] = useState(null);

    useEffect(() => {
        if (!jobId) return;
        jobsService.jobApplications(jobId)
            .then(({ data }) => {
                const list = data.results || data;
                setApplicants(list);
                if (list.length > 0) setSelectedApplicant(list[0]);
            })
            .catch((err) => setError(getApiErrorMessage(err, 'Failed to load applicants.')))
            .finally(() => setIsLoading(false));
    }, [jobId]);

    const handleStatusChange = async (appId, newStatus) => {
        setUpdatingId(appId);
        try {
            await jobsService.updateApplicationStatus(appId, newStatus);
            setApplicants(prev => prev.map(a => a.id === appId ? { ...a, status: newStatus } : a));
            if (selectedApplicant?.id === appId) setSelectedApplicant(prev => ({ ...prev, status: newStatus }));
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Status update failed.'), 'error');
        } finally {
            setUpdatingId(null);
        }
    };

    const stats = {
        total: applicants.length,
        shortlisted: applicants.filter(a => a.status === 'shortlisted').length,
        interviewing: applicants.filter(a => a.status === 'interviewing').length,
        pending: applicants.filter(a => a.status === 'pending').length,
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Applicant Review",
                status: isLoading ? "Loading..." : `${stats.total} Applicants`,
                info: `Shortlisted: ${stats.shortlisted} | Interviews: ${stats.interviewing}`
            }}
            pageTitleLine1="Applicant"
            pageTitleLine2="Review"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Total</h3><p>{stats.total}</p></div>
                    <div className="stat-block"><h3>Pending</h3><p>{stats.pending}</p></div>
                    <div className="stat-block"><h3>Shortlisted</h3><p>{stats.shortlisted}</p></div>
                    <div className="stat-block"><h3>Interviewing</h3><p>{stats.interviewing}</p></div>
                </div>
            }
        >
            <div className="ar-layout">
                {/* Applicant List */}
                <div className="ar-list-panel">
                    <div className="list-header">
                        <h2>Candidates</h2>
                        <span style={{ fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>{stats.total} total</span>
                    </div>

                    {isLoading && (
                        <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>Loading...</div>
                    )}

                    {error && (
                        <div style={{ padding: '32px', fontSize: '11px', color: '#b00', textTransform: 'uppercase' }}>⚠ {error}</div>
                    )}

                    {!isLoading && !error && applicants.length === 0 && (
                        <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            No applications yet for this job.
                        </div>
                    )}

                    {applicants.map(app => (
                        <div
                            key={app.id}
                            className={`ar-applicant-row ${selectedApplicant?.id === app.id ? 'active' : ''}`}
                            onClick={() => setSelectedApplicant(app)}
                            style={{ cursor: 'pointer' }}
                        >
                            <div className="ar-applicant-avatar">
                                {(app.applicant_name || app.full_name || 'A').charAt(0).toUpperCase()}
                            </div>
                            <div className="ar-applicant-info">
                                <span className="ar-applicant-name">{app.applicant_name || app.full_name || app.applicant_email || 'Unknown'}</span>
                                <span className="ar-applicant-meta">{app.applicant_email || '—'}</span>
                                <span className={`app-status-badge status-${app.status || 'pending'}`} style={{ marginTop: '4px', display: 'inline-block' }}>
                                    {STATUS_LABELS[app.status] || app.status || 'Pending'}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Applicant Detail Panel */}
                <div className="ar-detail-panel">
                    {selectedApplicant ? (
                        <>
                            <div className="list-header">
                                <div>
                                    <h2>{selectedApplicant.applicant_name || selectedApplicant.full_name || 'Applicant'}</h2>
                                    <span style={{ fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>{selectedApplicant.applicant_email || '—'}</span>
                                </div>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                    {STATUS_OPTIONS.map(s => (
                                        <button
                                            key={s}
                                            className="btn-outline"
                                            style={{
                                                padding: '6px 10px',
                                                fontSize: '9px',
                                                fontWeight: 700,
                                                opacity: updatingId === selectedApplicant.id ? 0.5 : 1,
                                                ...(selectedApplicant.status === s ? { background: '#000', color: '#fff' } : {}),
                                            }}
                                            onClick={() => handleStatusChange(selectedApplicant.id, s)}
                                            disabled={updatingId === selectedApplicant.id}
                                        >
                                            {STATUS_LABELS[s]}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="ar-detail-body">
                                <div className="ar-detail-section">
                                    <h3>Application Info</h3>
                                    <div className="ar-detail-row"><span>Status</span><span className={`app-status-badge status-${selectedApplicant.status || 'pending'}`}>{STATUS_LABELS[selectedApplicant.status] || 'Pending'}</span></div>
                                    <div className="ar-detail-row"><span>Applied</span><span>{selectedApplicant.applied_at ? new Date(selectedApplicant.applied_at).toLocaleDateString() : '—'}</span></div>
                                    {selectedApplicant.cover_letter && (
                                        <div className="ar-detail-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px' }}>
                                            <span>Cover Letter</span>
                                            <p style={{ fontSize: '13px', lineHeight: 1.6, opacity: 0.8 }}>{selectedApplicant.cover_letter}</p>
                                        </div>
                                    )}
                                    {selectedApplicant.resume_url && (
                                        <div className="ar-detail-row">
                                            <span>Resume</span>
                                            <a href={selectedApplicant.resume_url} target="_blank" rel="noreferrer" className="btn-outline" style={{ padding: '6px 12px', fontSize: '10px' }}>View PDF</a>
                                        </div>
                                    )}
                                </div>

                                {selectedApplicant.applicant_bio && (
                                    <div className="ar-detail-section">
                                        <h3>Bio</h3>
                                        <p style={{ fontSize: '14px', lineHeight: 1.6, opacity: 0.8 }}>{selectedApplicant.applicant_bio}</p>
                                    </div>
                                )}

                                {selectedApplicant.applicant_skills?.length > 0 && (
                                    <div className="ar-detail-section">
                                        <h3>Skills</h3>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                                            {selectedApplicant.applicant_skills.map(s => (
                                                <span key={s} style={{ padding: '4px 8px', border: '1px solid var(--border-color)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase' }}>{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            Select an applicant to view details
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default ApplicantReview;
