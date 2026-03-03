import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { useAuthStore } from '../store/authStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './SkillBadgeProfile.css';

const SkillBadgeProfile = () => {
    const { user } = useAuthStore();
    const { badges, setBadges, myResults, setMyResults } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    usePageTitle('Skill Badge Profile', 'Your verified skill badges and assessment achievements.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [badgesRes, resultsRes] = await Promise.all([
                assessmentService.myBadges(),
                assessmentService.myResults(),
            ]);
            setBadges(badgesRes.data.results || badgesRes.data);
            setMyResults(resultsRes.data.results || resultsRes.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load badge profile.'));
        } finally {
            setLoading(false);
        }
    }, [setBadges, setMyResults]);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Skill aggregation from badges
    const skillMap = {};
    badges.forEach((badge) => {
        const skill = badge.skill || badge.category || 'General';
        if (!skillMap[skill]) skillMap[skill] = [];
        skillMap[skill].push(badge);
    });
    const skillGroups = Object.entries(skillMap);

    const totalPassed = myResults.filter((r) => r.passed).length;
    const avgScore = myResults.length
        ? Math.round(myResults.reduce((s, r) => s + (r.score || r.percentage || 0), 0) / myResults.length)
        : 0;

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Skill Badge" pageTitleLine2="Profile">
                <div className="sbp-skeleton">
                    <Skeleton style={{ width: '200px', height: '200px', borderRadius: '50%', margin: '32px auto' }} />
                    <Skeleton style={{ width: '60%', height: '24px', margin: '16px auto' }} />
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '16px', maxWidth: '600px', margin: '24px auto' }}>
                        {Array.from({ length: 6 }).map((_, i) => (
                            <Skeleton key={i} style={{ height: '100px', borderRadius: '8px' }} />
                        ))}
                    </div>
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Skill Badge" pageTitleLine2="Profile">
                <div className="sbp-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Skill Badge Profile',
                status: `${badges.length} Badges Earned`,
                info: 'Verified Credentials',
            }}
            pageTitleLine1="Skill Badge"
            pageTitleLine2="Profile"
            headerRightContent={
                <div className="sbp-header-stats">
                    <div className="sbp-stat"><span className="sbp-stat__val">{badges.length}</span><span className="sbp-stat__label">Badges</span></div>
                    <div className="sbp-stat"><span className="sbp-stat__val">{totalPassed}</span><span className="sbp-stat__label">Passed</span></div>
                    <div className="sbp-stat"><span className="sbp-stat__val">{avgScore}%</span><span className="sbp-stat__label">Avg Score</span></div>
                </div>
            }
        >
            <div className="sbp-page">
                {/* Profile header */}
                <section className="sbp-profile-header">
                    <div className="sbp-avatar">
                        {user?.avatar ? (
                            <img src={user.avatar} alt={user.name} />
                        ) : (
                            <span className="sbp-avatar__initial">{user?.name?.charAt(0) || '?'}</span>
                        )}
                    </div>
                    <h2 className="sbp-name">{user?.name || 'Talent'}</h2>
                    <p className="sbp-subtitle">{user?.title || user?.headline || 'Verified Skills Profile'}</p>
                </section>

                {/* Badge grid */}
                {badges.length > 0 ? (
                    <>
                        {skillGroups.map(([skill, groupBadges]) => (
                            <section key={skill} className="sbp-skill-group">
                                <h3 className="sbp-skill-group__title">{skill}</h3>
                                <div className="sbp-badges-grid">
                                    {groupBadges.map((badge) => (
                                        <div key={badge.id} className="sbp-badge-card">
                                            <div className="sbp-badge-card__icon">
                                                {badge.icon || '🏅'}
                                            </div>
                                            <h4 className="sbp-badge-card__title">{badge.name || badge.title}</h4>
                                            <p className="sbp-badge-card__level">{badge.level || 'Verified'}</p>
                                            <p className="sbp-badge-card__date">
                                                {new Date(badge.earned_at || badge.created_at).toLocaleDateString()}
                                            </p>
                                            <div className="sbp-badge-card__actions">
                                                <Link
                                                    to={`/badges/verify/${badge.verification_id || badge.id}`}
                                                    className="sbp-badge-link"
                                                >
                                                    Verify
                                                </Link>
                                                <button
                                                    className="sbp-badge-share"
                                                    onClick={() => {
                                                        const url = `${window.location.origin}/badges/verify/${badge.verification_id || badge.id}`;
                                                        navigator.clipboard.writeText(url);
                                                        alert('Badge link copied!');
                                                    }}
                                                >
                                                    Share
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        ))}
                    </>
                ) : (
                    <div className="sbp-empty">
                        <p>No badges earned yet.</p>
                        <Link to="/assessments" className="sbp-cta-btn">Browse Assessments →</Link>
                    </div>
                )}

                {/* Recent results */}
                {myResults.length > 0 && (
                    <section className="sbp-recent-results">
                        <h3 className="sbp-section-title">Recent Assessment Results</h3>
                        <div className="sbp-results-list">
                            {myResults.slice(0, 5).map((res) => (
                                <div key={res.id} className={`sbp-result-row ${res.passed ? 'passed' : 'failed'}`}>
                                    <span className="sbp-result-row__title">{res.assessment_title || res.assessment?.title}</span>
                                    <span className="sbp-result-row__score">{res.score || res.percentage || 0}%</span>
                                    <span className={`sbp-result-row__badge ${res.passed ? 'pass' : 'fail'}`}>
                                        {res.passed ? 'Passed' : 'Failed'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}
            </div>
        </DashboardLayout>
    );
};

export default SkillBadgeProfile;
