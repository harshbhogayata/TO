import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { normaliseAssessmentResult } from '../utils/learningContracts';
import './AssessmentResults.css';

const AssessmentResults = () => {
    const { assessmentId, resultId: attemptId } = useParams();
    const { activeResult, setActiveResult } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [gradingPending, setGradingPending] = useState(false);

    usePageTitle('Assessment Results', 'Review your performance and answers.');

    const fetchResult = useCallback(async () => {
        setLoading(true);
        setError(null);
        setGradingPending(false);
        setActiveResult(null);

        try {
            const { data } = await assessmentService.getResult(attemptId);
            setActiveResult(normaliseAssessmentResult(data));
        } catch (err) {
            if (err?.response?.status === 404) {
                setGradingPending(true);
                return;
            }

            setError(getApiErrorMessage(err, 'Failed to load results.'));
        } finally {
            setLoading(false);
        }
    }, [attemptId, setActiveResult]);

    useEffect(() => {
        fetchResult();
    }, [fetchResult]);

    const result = activeResult;
    const passed = Boolean(result?.passed);
    const score = Math.round(result?.score ?? result?.percentage ?? 0);
    const correct = result?.correct_count ?? 0;
    const total = result?.total_questions ?? result?.question_count ?? 0;
    const timeTakenMinutes = result?.time_taken_seconds
        ? Math.max(1, Math.round(result.time_taken_seconds / 60))
        : null;
    const percentile = result?.percentile != null ? Math.round(result.percentile) : null;

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Results">
                <div className="ar-skeleton">
                    <Skeleton style={{ width: '300px', height: '300px', borderRadius: '50%', margin: '40px auto' }} />
                    <Skeleton style={{ width: '60%', height: '28px', margin: '20px auto' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Results">
                <div className="ar-error">{error}</div>
            </DashboardLayout>
        );
    }

    if (gradingPending) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Results">
                <div className="ar-page">
                    <div className="ar-stats-grid">
                        <div className="ar-stat-block">
                            <h4>Results Pending</h4>
                            <p>Your assessment was submitted successfully and is still being graded.</p>
                        </div>
                    </div>
                    <div className="ar-actions">
                        <Link to="/my-assessments" className="ar-action-btn">
                            My Assessments
                        </Link>
                        <Link to={`/assessments/${assessmentId}`} className="ar-action-btn ar-action-btn--secondary">
                            Back to Assessment
                        </Link>
                    </div>
                </div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Assessment Results',
                status: passed ? 'Passed' : 'Not passed',
                info: `Score: ${score}%`,
            }}
            pageTitleLine1="Assessment"
            pageTitleLine2="Results"
        >
            <div className="ar-page">
                <div className={`ar-score-circle ${passed ? 'passed' : 'failed'}`}>
                    <svg viewBox="0 0 120 120" className="ar-score-ring">
                        <circle cx="60" cy="60" r="54" className="ar-score-ring__bg" />
                        <circle
                            cx="60"
                            cy="60"
                            r="54"
                            className="ar-score-ring__fill"
                            strokeDasharray={`${(score / 100) * 339.3} 339.3`}
                        />
                    </svg>
                    <div className="ar-score-inner">
                        <span className="ar-score-value">{score}%</span>
                        <span className="ar-score-label">{passed ? 'PASSED' : 'FAILED'}</span>
                    </div>
                </div>

                <div className="ar-stats-grid">
                    <div className="ar-stat-block">
                        <h4>Correct</h4>
                        <p>{correct} / {total}</p>
                    </div>
                    <div className="ar-stat-block">
                        <h4>Passing Score</h4>
                        <p>{result?.passing_score ?? 70}%</p>
                    </div>
                    {timeTakenMinutes != null && (
                        <div className="ar-stat-block">
                            <h4>Time Taken</h4>
                            <p>{timeTakenMinutes} min</p>
                        </div>
                    )}
                    {percentile != null && (
                        <div className="ar-stat-block">
                            <h4>Percentile</h4>
                            <p>Top {percentile}%</p>
                        </div>
                    )}
                </div>

                {result?.skill_breakdown?.length > 0 && (
                    <section className="ar-skills">
                        <h3 className="ar-section-title">Skill Breakdown</h3>
                        <div className="ar-skill-bars">
                            {result.skill_breakdown.map((skill, index) => {
                                const skillScore = skill.score ?? skill.percentage ?? 0;
                                return (
                                    <div key={skill.name || skill.skill || index} className="ar-skill-row">
                                        <span className="ar-skill-name">{skill.name || skill.skill}</span>
                                        <div className="ar-skill-bar">
                                            <div
                                                className="ar-skill-bar__fill"
                                                style={{ width: `${skillScore}%` }}
                                            />
                                        </div>
                                        <span className="ar-skill-pct">{skillScore}%</span>
                                    </div>
                                );
                            })}
                        </div>
                    </section>
                )}

                {result?.show_answers && result?.answers?.length > 0 && (
                    <section className="ar-answers">
                        <h3 className="ar-section-title">Answer Review</h3>
                        {result.answers.map((answer, index) => (
                            <div
                                key={answer.question_id || index}
                                className={`ar-answer-card ${answer.is_correct ? 'correct' : 'incorrect'}`}
                            >
                                <div className="ar-answer-card__header">
                                    <span>Q{index + 1}</span>
                                    <span>{answer.is_correct ? 'Correct' : 'Incorrect'}</span>
                                </div>
                                <p className="ar-answer-card__question">{answer.question_text || 'Question review unavailable.'}</p>
                                <p className="ar-answer-card__your">
                                    Your answer: {answer.user_answer || 'No answer submitted'}
                                </p>
                                {!answer.is_correct && answer.correct_answer && (
                                    <p className="ar-answer-card__correct">Correct answer: {answer.correct_answer}</p>
                                )}
                                {answer.explanation && (
                                    <p className="ar-answer-card__explanation">{answer.explanation}</p>
                                )}
                            </div>
                        ))}
                    </section>
                )}

                {result?.badge && (
                    <div className="ar-badge-earned">
                        <div>
                            <h4>Badge Earned</h4>
                            <p>{result.badge.name || result.badge.title}</p>
                        </div>
                    </div>
                )}

                <div className="ar-actions">
                    <Link to="/my-assessments" className="ar-action-btn">
                        My Assessments
                    </Link>
                    <Link to={`/assessments/${assessmentId}`} className="ar-action-btn ar-action-btn--secondary">
                        Retake Assessment
                    </Link>
                    <Link to="/assessments" className="ar-action-btn ar-action-btn--secondary">
                        Browse More
                    </Link>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default AssessmentResults;
