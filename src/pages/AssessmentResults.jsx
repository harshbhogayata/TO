import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './AssessmentResults.css';

const AssessmentResults = () => {
    const { assessmentId, resultId } = useParams();
    const navigate = useNavigate();
    const { activeResult, setActiveResult } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    usePageTitle('Assessment Results', 'Review your performance and answers.');

    const fetchResult = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await assessmentService.getResult(assessmentId, resultId);
            setActiveResult(data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load results.'));
        } finally {
            setLoading(false);
        }
    }, [assessmentId, resultId, setActiveResult]);

    useEffect(() => { fetchResult(); }, [fetchResult]);

    const result = activeResult;
    const passed = result?.passed;
    const score = result?.score ?? result?.percentage ?? 0;
    const correct = result?.correct_count ?? 0;
    const total = result?.total_questions ?? result?.question_count ?? 0;
    const timeTaken = result?.time_taken_seconds ? Math.round(result.time_taken_seconds / 60) : null;

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

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Assessment Results',
                status: passed ? 'Passed ✓' : 'Failed ✗',
                info: `Score: ${score}%`,
            }}
            pageTitleLine1="Assessment"
            pageTitleLine2="Results"
        >
            <div className="ar-page">
                {/* Score circle */}
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

                {/* Stats grid */}
                <div className="ar-stats-grid">
                    <div className="ar-stat-block">
                        <h4>Correct</h4>
                        <p>{correct} / {total}</p>
                    </div>
                    <div className="ar-stat-block">
                        <h4>Passing Score</h4>
                        <p>{result?.passing_score ?? 70}%</p>
                    </div>
                    {timeTaken && (
                        <div className="ar-stat-block">
                            <h4>Time Taken</h4>
                            <p>{timeTaken} min</p>
                        </div>
                    )}
                    {result?.percentile != null && (
                        <div className="ar-stat-block">
                            <h4>Percentile</h4>
                            <p>Top {result.percentile}%</p>
                        </div>
                    )}
                </div>

                {/* Skill breakdown */}
                {result?.skill_breakdown && result.skill_breakdown.length > 0 && (
                    <section className="ar-skills">
                        <h3 className="ar-section-title">Skill Breakdown</h3>
                        <div className="ar-skill-bars">
                            {result.skill_breakdown.map((skill, i) => (
                                <div key={i} className="ar-skill-row">
                                    <span className="ar-skill-name">{skill.name || skill.skill}</span>
                                    <div className="ar-skill-bar">
                                        <div
                                            className="ar-skill-bar__fill"
                                            style={{ width: `${skill.score || skill.percentage || 0}%` }}
                                        />
                                    </div>
                                    <span className="ar-skill-pct">{skill.score || skill.percentage || 0}%</span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Answer review (if allowed) */}
                {result?.show_answers && result?.answers && (
                    <section className="ar-answers">
                        <h3 className="ar-section-title">Answer Review</h3>
                        {result.answers.map((ans, i) => (
                            <div key={i} className={`ar-answer-card ${ans.is_correct ? 'correct' : 'incorrect'}`}>
                                <div className="ar-answer-card__header">
                                    <span>Q{i + 1}</span>
                                    <span>{ans.is_correct ? '✓ Correct' : '✗ Incorrect'}</span>
                                </div>
                                <p className="ar-answer-card__question">{ans.question_text}</p>
                                <p className="ar-answer-card__your">Your answer: {ans.user_answer || '—'}</p>
                                {!ans.is_correct && ans.correct_answer && (
                                    <p className="ar-answer-card__correct">Correct answer: {ans.correct_answer}</p>
                                )}
                                {ans.explanation && (
                                    <p className="ar-answer-card__explanation">{ans.explanation}</p>
                                )}
                            </div>
                        ))}
                    </section>
                )}

                {/* Badge earned */}
                {result?.badge && (
                    <div className="ar-badge-earned">
                        <span className="ar-badge-icon">🏅</span>
                        <div>
                            <h4>Badge Earned!</h4>
                            <p>{result.badge.name || result.badge.title}</p>
                        </div>
                    </div>
                )}

                {/* Actions */}
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
