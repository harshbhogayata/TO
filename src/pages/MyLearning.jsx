import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { getEnrollmentRoute, normaliseEnrollment } from '../utils/learningContracts';
import './MyLearning.css';

const statusColors = {
    active: '#4CAF50',
    completed: '#2196F3',
    dropped: '#999',
};

const VALID_TABS = new Set(['active', 'completed', 'certificates']);

const MyLearning = () => {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const { enrollments, setEnrollments, certificates, setCertificates } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const initialTab = searchParams.get('tab');
    const [tab, setTab] = useState(VALID_TABS.has(initialTab) ? initialTab : 'active');

    usePageTitle('My Learning', 'Track your enrolled courses, progress, and certificates.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [enrollmentResponse, certificateResponse] = await Promise.all([
                courseService.listEnrollments(),
                courseService.myCertificates(),
            ]);
            setEnrollments((enrollmentResponse.data.results || enrollmentResponse.data).map(normaliseEnrollment));
            setCertificates(certificateResponse.data.results || certificateResponse.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load learning data.'));
        } finally {
            setLoading(false);
        }
    }, [setEnrollments, setCertificates]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useEffect(() => {
        const requestedTab = searchParams.get('tab');
        if (VALID_TABS.has(requestedTab) && requestedTab !== tab) {
            setTab(requestedTab);
        }
    }, [searchParams, tab]);

    const handleTabChange = (nextTab) => {
        setTab(nextTab);
        const nextParams = new URLSearchParams(searchParams);
        if (nextTab === 'active') {
            nextParams.delete('tab');
        } else {
            nextParams.set('tab', nextTab);
        }
        setSearchParams(nextParams, { replace: true });
    };

    const activeEnrollments = enrollments.filter((enrollment) => enrollment.status === 'active' || enrollment.status === 'enrolled');
    const completedEnrollments = enrollments.filter((enrollment) => enrollment.status === 'completed');

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
                <div className="ml-tabs">
                    {tabs.map((item) => (
                        <button
                            key={item.key}
                            className={`ml-tab ${tab === item.key ? 'active' : ''}`}
                            onClick={() => handleTabChange(item.key)}
                        >
                            {item.label} <span className="ml-tab__count">({item.count})</span>
                        </button>
                    ))}
                </div>

                {error && <div className="ml-error">{error}</div>}

                {loading ? (
                    <div className="ml-grid">
                        {Array.from({ length: 4 }).map((_, index) => (
                            <div key={index} className="ml-card">
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
                        {certificates.length > 0 ? certificates.map((certificate) => (
                            <div key={certificate.id} className="ml-cert-card" onClick={() => navigate(`/certificates/${certificate.id}`)}>
                                <div className="ml-cert-card__icon">T</div>
                                <h4 className="ml-cert-card__title">{certificate.course_title || certificate.course?.title}</h4>
                                <p className="ml-cert-card__date">Issued: {new Date(certificate.issued_at || certificate.created_at).toLocaleDateString()}</p>
                                <span className="ml-cert-card__id">ID: {certificate.certificate_id || certificate.id}</span>
                            </div>
                        )) : (
                            <p className="ml-empty">No certificates earned yet. Complete a course to earn one.</p>
                        )}
                    </div>
                ) : (
                    <div className="ml-grid">
                        {visibleItems.length > 0 ? visibleItems.map((enrollment) => (
                            <div
                                key={enrollment.id}
                                className="ml-card"
                                onClick={() => navigate(getEnrollmentRoute(enrollment, { preferContinue: tab === 'active' }))}
                            >
                                <img
                                    src={enrollment.course_thumbnail || enrollment.course?.thumbnail || 'https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=400'}
                                    alt={enrollment.course_title || enrollment.course?.title}
                                    className="ml-card__thumb"
                                />
                                <div className="ml-card__body">
                                    <div className="ml-card__status-badge" style={{ backgroundColor: statusColors[enrollment.status] || '#888' }}>
                                        {enrollment.status}
                                    </div>
                                    <h4 className="ml-card__title">{enrollment.course_title || enrollment.course?.title || 'Untitled Course'}</h4>
                                    <div className="ml-card__progress-bar">
                                        <div
                                            className="ml-card__progress-fill"
                                            style={{ width: `${enrollment.progress_percentage ?? 0}%` }}
                                        />
                                    </div>
                                    <span className="ml-card__pct">{enrollment.progress_percentage ?? 0}% complete</span>
                                </div>
                            </div>
                        )) : (
                            <p className="ml-empty">
                                {tab === 'active' ? 'No active enrollments. Browse the course catalog to get started.' : 'No completed courses yet.'}
                            </p>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default MyLearning;
