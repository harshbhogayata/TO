import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './AssessmentDetail.css';

const difficultyColors = {
    easy: '#4CAF50',
    medium: '#FF9800',
    hard: '#F44336',
    expert: '#9C27B0',
};

const AssessmentDetail = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { activeAssessment, setActiveAssessment } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [starting, setStarting] = useState(false);

    usePageTitle('Assessment Detail', 'Review assessment details before starting.');

    const fetchAssessment = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await assessmentService.getAssessment(id);
            setActiveAssessment(data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load assessment.'));
        } finally {
            setLoading(false);
        }
    }, [id, setActiveAssessment]);

    useEffect(() => { fetchAssessment(); }, [fetchAssessment]);

    const handleStartAttempt = async () => {
        setStarting(true);
        try {
            const { data } = await assessmentService.startAttempt(id);
            navigate(`/assessments/${id}/attempt/${data.id}`);
        } catch (err) {
            alert(getApiErrorMessage(err, 'Could not start assessment. You may have reached the attempt limit.'));
        } finally {
            setStarting(false);
        }
    };

    const assessment = activeAssessment;

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Detail">
                <div className="ad-skeleton">
                    <Skeleton style={{ width: '100%', height: '200px', borderRadius: '12px', marginBottom: '20px' }} />
                    <Skeleton style={{ width: '70%', height: '28px', marginBottom: '12px' }} />
                    <Skeleton style={{ width: '100%', height: '100px' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Detail">
                <div className="ad-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Assessment Detail',
                status: assessment?.is_published ? 'Published' : 'Draft',
                info: `ID: ${id}`,
            }}
            pageTitleLine1={assessment?.title?.split(' ').slice(0, 2).join(' ') || 'Assessment'}
            pageTitleLine2={assessment?.title?.split(' ').slice(2).join(' ') || 'Detail'}
            headerRightContent={
                <button className="ad-start-btn" onClick={handleStartAttempt} disabled={starting}>
                    {starting ? 'Starting…' : 'Start Assessment'}
                </button>
            }
        >
            <div className="ad-page">
                {/* Overview Card */}
                <section className="ad-overview">
                    <div className="ad-overview__badges">
                        <span
                            className="ad-badge ad-badge--difficulty"
                            style={{ backgroundColor: difficultyColors[assessment?.difficulty] || '#888' }}
                        >
                            {assessment?.difficulty || 'Medium'}
                        </span>
                        <span className="ad-badge ad-badge--type">
                            {assessment?.assessment_type?.replace('_', ' ') || 'Skill Test'}
                        </span>
                    </div>
                    <p className="ad-description">{assessment?.description || 'No description provided.'}</p>
                </section>

                {/* Info Grid */}
                <section className="ad-info-grid">
                    <div className="ad-info-block">
                        <h4>Time Limit</h4>
                        <p>{assessment?.time_limit_minutes || assessment?.duration || '—'} min</p>
                    </div>
                    <div className="ad-info-block">
                        <h4>Questions</h4>
                        <p>{assessment?.question_count || assessment?.total_questions || '—'}</p>
                    </div>
                    <div className="ad-info-block">
                        <h4>Passing Score</h4>
                        <p>{assessment?.passing_score ?? '70'}%</p>
                    </div>
                    <div className="ad-info-block">
                        <h4>Max Attempts</h4>
                        <p>{assessment?.max_attempts ?? 'Unlimited'}</p>
                    </div>
                    <div className="ad-info-block">
                        <h4>Created By</h4>
                        <p>{assessment?.creator_name || assessment?.company?.name || 'TalentOrbit'}</p>
                    </div>
                    <div className="ad-info-block">
                        <h4>Proctored</h4>
                        <p>{assessment?.is_proctored ? 'Yes' : 'No'}</p>
                    </div>
                </section>

                {/* Skills / Topics */}
                {(assessment?.skills || assessment?.tags) && (
                    <section className="ad-skills">
                        <h3 className="ad-section-title">Skills Tested</h3>
                        <div className="ad-skill-tags">
                            {(assessment.skills || assessment.tags || []).map((skill, i) => (
                                <span key={i} className="ad-skill-tag">
                                    {typeof skill === 'string' ? skill : skill.name}
                                </span>
                            ))}
                        </div>
                    </section>
                )}

                {/* Instructions */}
                <section className="ad-instructions">
                    <h3 className="ad-section-title">Instructions</h3>
                    <ul className="ad-instructions-list">
                        <li>Ensure a stable internet connection before starting.</li>
                        <li>Once started, the timer cannot be paused.</li>
                        {assessment?.is_proctored && (
                            <li>This assessment is proctored — camera and screen recording may be active.</li>
                        )}
                        <li>You can flag questions and return to them before submission.</li>
                        <li>The assessment will auto-submit when time expires.</li>
                        {assessment?.instructions && <li>{assessment.instructions}</li>}
                    </ul>
                </section>

                {/* Previous attempts */}
                {assessment?.my_attempts && assessment.my_attempts.length > 0 && (
                    <section className="ad-attempts">
                        <h3 className="ad-section-title">Previous Attempts</h3>
                        <div className="ad-attempts-list">
                            {assessment.my_attempts.map((att) => (
                                <div key={att.id} className="ad-attempt-row">
                                    <span>Attempt #{att.attempt_number || att.id}</span>
                                    <span>Score: {att.score ?? '—'}%</span>
                                    <span>{att.passed ? '✓ Passed' : '✗ Failed'}</span>
                                    <span>{new Date(att.completed_at || att.created_at).toLocaleDateString()}</span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                <div className="ad-cta">
                    <button className="ad-start-btn ad-start-btn--large" onClick={handleStartAttempt} disabled={starting}>
                        {starting ? 'Starting…' : 'Begin Assessment →'}
                    </button>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default AssessmentDetail;
