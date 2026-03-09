import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { normaliseAssessmentResultListItem } from '../utils/learningContracts';
import './MyAssessments.css';

const asCollection = (payload) => payload?.results || payload || [];

const normaliseInvitation = (invitation = {}) => ({
    ...invitation,
    status: String(invitation.status ?? '').toLowerCase(),
    assessment_id: invitation.assessment_id ?? invitation.assessment?.id ?? invitation.assessment ?? null,
});

const normaliseBadge = (badge = {}) => ({
    ...badge,
    title: badge.title ?? badge.name ?? 'Badge',
    skill: badge.skill ?? badge.skill_name ?? badge.assessment_title ?? '-',
    earned_at: badge.earned_at ?? badge.issued_at ?? badge.created_at ?? null,
});

const MyAssessments = () => {
    const navigate = useNavigate();
    const { myResults, setMyResults, invitations, setInvitations, badges, setBadges } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tab, setTab] = useState('results');

    usePageTitle('My Assessments', 'Track your assessment history, invitations, and earned badges.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const [resultsResponse, invitationsResponse, badgesResponse] = await Promise.all([
                assessmentService.myResults(),
                assessmentService.myInvitations(),
                assessmentService.myBadges(),
            ]);

            setMyResults(asCollection(resultsResponse.data).map(normaliseAssessmentResultListItem));
            setInvitations(asCollection(invitationsResponse.data).map(normaliseInvitation));
            setBadges(asCollection(badgesResponse.data).map(normaliseBadge));
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load assessment data.'));
        } finally {
            setLoading(false);
        }
    }, [setBadges, setInvitations, setMyResults]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const passedResults = myResults.filter((result) => result.passed);
    const failedResults = myResults.filter((result) => !result.passed);
    const pendingInvites = invitations.filter((invitation) => invitation.status === 'pending');

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
                    {tabs.map((item) => (
                        <button
                            key={item.key}
                            className={`ma-tab ${tab === item.key ? 'active' : ''}`}
                            onClick={() => setTab(item.key)}
                        >
                            {item.label} <span className="ma-tab__count">({item.count})</span>
                        </button>
                    ))}
                </div>

                {error && <div className="ma-error">{error}</div>}

                {loading ? (
                    <div className="ma-grid">
                        {Array.from({ length: 4 }).map((_, index) => (
                            <Skeleton key={index} style={{ width: '100%', height: '120px', borderRadius: '8px' }} />
                        ))}
                    </div>
                ) : tab === 'results' ? (
                    <div className="ma-grid">
                        {myResults.length > 0 ? myResults.map((result) => {
                            const assessmentId = result.assessment_id ?? result.assessment?.id ?? result.assessment ?? null;
                            const attemptId = result.attempt_id ?? result.attempt?.id ?? null;
                            const detailHref = assessmentId && attemptId
                                ? `/assessments/${assessmentId}/results/${attemptId}`
                                : assessmentId
                                    ? `/assessments/${assessmentId}`
                                    : '/my-assessments';

                            return (
                                <div key={result.id} className={`ma-result-card ${result.passed ? 'passed' : 'failed'}`}>
                                    <div className="ma-result-card__header">
                                        <h4>{result.assessment_title || result.assessment?.title || 'Assessment'}</h4>
                                        <span className={`ma-result-badge ${result.passed ? 'pass' : 'fail'}`}>
                                            {result.passed ? 'Passed' : 'Failed'}
                                        </span>
                                    </div>
                                    <div className="ma-result-card__meta">
                                        <span>Score: {result.score ?? result.percentage ?? 0}%</span>
                                        <span>{new Date(result.completed_at || result.created_at).toLocaleDateString()}</span>
                                    </div>
                                    <Link to={detailHref} className="ma-result-card__link">
                                        View Details
                                    </Link>
                                </div>
                            );
                        }) : (
                            <p className="ma-empty">No assessment results yet. <Link to="/assessments">Browse assessments</Link></p>
                        )}
                    </div>
                ) : tab === 'invitations' ? (
                    <div className="ma-grid">
                        {invitations.length > 0 ? invitations.map((invitation) => (
                            <div key={invitation.id} className="ma-invite-card">
                                <div className="ma-invite-card__header">
                                    <h4>{invitation.assessment_title || invitation.assessment?.title || 'Assessment'}</h4>
                                    <span className={`ma-invite-status ${invitation.status}`}>{invitation.status || 'unknown'}</span>
                                </div>
                                <p className="ma-invite-card__from">From: {invitation.company_name || invitation.invited_by_name || 'Unknown company'}</p>
                                <p className="ma-invite-card__deadline">
                                    Deadline: {invitation.expires_at ? new Date(invitation.expires_at).toLocaleDateString() : 'None'}
                                </p>
                                {invitation.status === 'pending' && invitation.assessment_id && (
                                    <button
                                        className="ma-invite-card__btn"
                                        onClick={() => navigate(`/assessments/${invitation.assessment_id}`)}
                                    >
                                        Take Assessment
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
                                <div className="ma-badge-card__icon">Badge</div>
                                <h4 className="ma-badge-card__title">{badge.title}</h4>
                                <p className="ma-badge-card__skill">{badge.skill}</p>
                                <p className="ma-badge-card__date">
                                    Earned: {badge.earned_at ? new Date(badge.earned_at).toLocaleDateString() : 'Unknown'}
                                </p>
                                <Link to={`/badges/${badge.id}`} className="ma-badge-card__link">
                                    View Badge
                                </Link>
                            </div>
                        )) : (
                            <p className="ma-empty">No badges earned yet. Pass assessments to earn skill badges.</p>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default MyAssessments;

