import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './MyAssessments.css';

const MyAssessments = () => {
    const navigate = useNavigate();
    const { myResults, setMyResults, invitations, setInvitations, badges, setBadges } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tab, setTab] = useState('results'); // results | invitations | badges

    usePageTitle('My Assessments', 'Track your assessment history, invitations, and earned badges.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [resultsRes, invitesRes, badgesRes] = await Promise.all([
                assessmentService.myResults(),
                assessmentService.myInvitations(),
                assessmentService.myBadges(),
            ]);
            setMyResults(resultsRes.data.results || resultsRes.data);
            setInvitations(invitesRes.data.results || invitesRes.data);
            setBadges(badgesRes.data.results || badgesRes.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load assessment data.'));
        } finally {
            setLoading(false);
        }
    }, [setMyResults, setInvitations, setBadges]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const passedResults = myResults.filter((r) => r.passed);
    const failedResults = myResults.filter((r) => !r.passed);
    const pendingInvites = invitations.filter((inv) => inv.status === 'pending');

    const tabs = [
        { key: 'results', label: 'Results', count: myResults.length },
        { key: 'invitations', label: 'Invitations', count: pendingInvites.length },
        { key: 'badges', label: 'Badges', count: badges.length },
    ];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'My Assessments Dashboard',
                status: 'System Status: Operational',
                info: `${myResults.length} Results`,
            }}
            pageTitleLine1="My"
            pageTitleLine2="Assessments"
            headerRightContent={
                <div className="ma-header-stats">
                    <div className="ma-stat"><span className="ma-stat__val">{passedResults.length}</span><span className="ma-stat__label">Passed</span></div>
                    <div className="ma-stat"><span className="ma-stat__val">{failedResults.length}</span><span className="ma-stat__label">Failed</span></div>
                    <div className="ma-stat"><span className="ma-stat__val">{badges.length}</span><span className="ma-stat__label">Badges</span></div>
                </div>
            }
        >
            <div className="ma-page">
                <div className="ma-tabs">
                    {tabs.map((t) => (
                        <button
                            key={t.key}
                            className={`ma-tab ${tab === t.key ? 'active' : ''}`}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label} <span className="ma-tab__count">({t.count})</span>
                        </button>
                    ))}
                </div>

                {error && <div className="ma-error">{error}</div>}

                {loading ? (
                    <div className="ma-grid">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} style={{ width: '100%', height: '120px', borderRadius: '8px' }} />
                        ))}
                    </div>
                ) : tab === 'results' ? (
                    <div className="ma-grid">
                        {myResults.length > 0 ? myResults.map((res) => (
                            <div key={res.id} className={`ma-result-card ${res.passed ? 'passed' : 'failed'}`}>
                                <div className="ma-result-card__header">
                                    <h4>{res.assessment_title || res.assessment?.title || 'Assessment'}</h4>
                                    <span className={`ma-result-badge ${res.passed ? 'pass' : 'fail'}`}>
                                        {res.passed ? '✓ Passed' : '✗ Failed'}
                                    </span>
                                </div>
                                <div className="ma-result-card__meta">
                                    <span>Score: {res.score ?? res.percentage ?? 0}%</span>
                                    <span>{new Date(res.completed_at || res.created_at).toLocaleDateString()}</span>
                                </div>
                                <Link
                                    to={`/assessments/${res.assessment_id || res.assessment?.id || res.assessment}/results/${res.id}`}
                                    className="ma-result-card__link"
                                >
                                    View Details →
                                </Link>
                            </div>
                        )) : (
                            <p className="ma-empty">No assessment results yet. <Link to="/assessments">Browse assessments</Link></p>
                        )}
                    </div>
                ) : tab === 'invitations' ? (
                    <div className="ma-grid">
                        {invitations.length > 0 ? invitations.map((inv) => (
                            <div key={inv.id} className="ma-invite-card">
                                <div className="ma-invite-card__header">
                                    <h4>{inv.assessment_title || inv.assessment?.title || 'Assessment'}</h4>
                                    <span className={`ma-invite-status ${inv.status}`}>{inv.status}</span>
                                </div>
                                <p className="ma-invite-card__from">From: {inv.company_name || inv.sender?.name || '—'}</p>
                                <p className="ma-invite-card__deadline">
                                    Deadline: {inv.deadline ? new Date(inv.deadline).toLocaleDateString() : 'None'}
                                </p>
                                {inv.status === 'pending' && (
                                    <button
                                        className="ma-invite-card__btn"
                                        onClick={() => navigate(`/assessments/${inv.assessment_id || inv.assessment?.id || inv.assessment}`)}
                                    >
                                        Take Assessment →
                                    </button>
                                )}
                            </div>
                        )) : (
                            <p className="ma-empty">No invitations received.</p>
                        )}
                    </div>
                ) : (
                    <div className="ma-grid">
                        {badges.length > 0 ? badges.map((badge) => (
                            <div key={badge.id} className="ma-badge-card">
                                <div className="ma-badge-card__icon">🏅</div>
                                <h4 className="ma-badge-card__title">{badge.name || badge.title}</h4>
                                <p className="ma-badge-card__skill">{badge.skill || badge.assessment_title || '—'}</p>
                                <p className="ma-badge-card__date">
                                    Earned: {new Date(badge.earned_at || badge.created_at).toLocaleDateString()}
                                </p>
                                <Link to={`/badges/${badge.id}`} className="ma-badge-card__link">
                                    View Badge →
                                </Link>
                            </div>
                        )) : (
                            <p className="ma-empty">No badges earned yet. Pass assessments to earn skill badges!</p>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default MyAssessments;
