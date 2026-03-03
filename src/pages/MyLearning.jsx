import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './MyLearning.css';

const statusColors = {
    active: '#4CAF50',
    completed: '#2196F3',
    dropped: '#999',
};

const MyLearning = () => {
    const navigate = useNavigate();
    const { enrollments, setEnrollments, certificates, setCertificates } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tab, setTab] = useState('active'); // active | completed | certificates

    usePageTitle('My Learning', 'Track your enrolled courses, progress, and certificates.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [enrollRes, certRes] = await Promise.all([
                courseService.listEnrollments(),
                courseService.myCertificates(),
            ]);
            setEnrollments(enrollRes.data.results || enrollRes.data);
            setCertificates(certRes.data.results || certRes.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load learning data.'));
        } finally {
            setLoading(false);
        }
    }, [setEnrollments, setCertificates]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const activeEnrollments = enrollments.filter((e) => e.status === 'active' || e.status === 'enrolled');
    const completedEnrollments = enrollments.filter((e) => e.status === 'completed');

    const tabs = [
        { key: 'active', label: 'In Progress', count: activeEnrollments.length },
        { key: 'completed', label: 'Completed', count: completedEnrollments.length },
        { key: 'certificates', label: 'Certificates', count: certificates.length },
    ];

    const visibleItems =
        tab === 'active' ? activeEnrollments :
        tab === 'completed' ? completedEnrollments :
        certificates;

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'My Learning Dashboard',
                status: 'System Status: Operational',
                info: `${enrollments.length} Enrollments`,
            }}
            pageTitleLine1="My"
            pageTitleLine2="Learning"
            headerRightContent={
                <div className="ml-header-stats">
                    <div className="ml-stat"><span className="ml-stat__val">{activeEnrollments.length}</span><span className="ml-stat__label">Active</span></div>
                    <div className="ml-stat"><span className="ml-stat__val">{completedEnrollments.length}</span><span className="ml-stat__label">Completed</span></div>
                    <div className="ml-stat"><span className="ml-stat__val">{certificates.length}</span><span className="ml-stat__label">Certificates</span></div>
                </div>
            }
        >
            <div className="ml-page">
                {/* Tabs */}
                <div className="ml-tabs">
                    {tabs.map((t) => (
                        <button
                            key={t.key}
                            className={`ml-tab ${tab === t.key ? 'active' : ''}`}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label} <span className="ml-tab__count">({t.count})</span>
                        </button>
                    ))}
                </div>

                {error && <div className="ml-error">{error}</div>}

                {loading ? (
                    <div className="ml-grid">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="ml-card">
                                <Skeleton style={{ width: '100%', height: '140px', borderRadius: '8px 8px 0 0' }} />
                                <div style={{ padding: '16px' }}>
                                    <Skeleton style={{ width: '80%', height: '18px', marginBottom: '8px' }} />
                                    <Skeleton style={{ width: '60%', height: '14px' }} />
                                </div>
                            </div>
                        ))}
                    </div>
                ) : tab === 'certificates' ? (
                    <div className="ml-grid">
                        {certificates.length > 0 ? certificates.map((cert) => (
                            <div key={cert.id} className="ml-cert-card" onClick={() => navigate(`/certificates/${cert.id}`)}>
                                <div className="ml-cert-card__icon">🏆</div>
                                <h4 className="ml-cert-card__title">{cert.course_title || cert.course?.title}</h4>
                                <p className="ml-cert-card__date">Issued: {new Date(cert.issued_at || cert.created_at).toLocaleDateString()}</p>
                                <span className="ml-cert-card__id">ID: {cert.certificate_id || cert.id}</span>
                            </div>
                        )) : (
                            <p className="ml-empty">No certificates earned yet. Complete a course to earn one!</p>
                        )}
                    </div>
                ) : (
                    <div className="ml-grid">
                        {visibleItems.length > 0 ? visibleItems.map((enr) => (
                            <div key={enr.id} className="ml-card" onClick={() => navigate(`/courses/${enr.course_id || enr.course?.id || enr.course}`)}>
                                <img
                                    src={enr.course_thumbnail || enr.course?.thumbnail || 'https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=400'}
                                    alt={enr.course_title || enr.course?.title}
                                    className="ml-card__thumb"
                                />
                                <div className="ml-card__body">
                                    <div className="ml-card__status-badge" style={{ backgroundColor: statusColors[enr.status] || '#888' }}>
                                        {enr.status}
                                    </div>
                                    <h4 className="ml-card__title">{enr.course_title || enr.course?.title || 'Untitled Course'}</h4>
                                    <div className="ml-card__progress-bar">
                                        <div
                                            className="ml-card__progress-fill"
                                            style={{ width: `${enr.progress_pct || enr.progress || 0}%` }}
                                        />
                                    </div>
                                    <span className="ml-card__pct">{enr.progress_pct || enr.progress || 0}% complete</span>
                                </div>
                            </div>
                        )) : (
                            <p className="ml-empty">
                                {tab === 'active' ? 'No active enrollments. Browse the course catalog to get started!' : 'No completed courses yet.'}
                            </p>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default MyLearning;
