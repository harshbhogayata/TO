import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './AssessmentPlayer.css';

const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
};

const AssessmentPlayer = () => {
    const { assessmentId, attemptId } = useParams();
    const navigate = useNavigate();
    const {
        attempt, setAttempt, setAnswer, toggleFlag, setTimeRemaining,
    } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentIdx, setCurrentIdx] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [savingAnswer, setSavingAnswer] = useState(false);
    const timerRef = useRef(null);

    usePageTitle('Assessment Player', 'Answer questions within the time limit.');

    // Fetch attempt data
    const fetchAttempt = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await assessmentService.getAttempt(assessmentId, attemptId);
            setAttempt({
                id: data.id,
                questions: data.questions || [],
                answers: data.answers || {},
                flagged: data.flagged || [],
                timeRemaining: data.time_remaining ?? (data.time_limit_minutes || 30) * 60,
                status: data.status || 'in_progress',
            });
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load assessment attempt.'));
        } finally {
            setLoading(false);
        }
    }, [assessmentId, attemptId, setAttempt]);

    useEffect(() => { fetchAttempt(); }, [fetchAttempt]);

    // Countdown timer
    useEffect(() => {
        if (!attempt || attempt.status !== 'in_progress') return;
        timerRef.current = setInterval(() => {
            setTimeRemaining((prev) => {
                if (prev <= 1) {
                    clearInterval(timerRef.current);
                    handleFinalSubmit();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(timerRef.current);
    }, [attempt?.status]); // eslint-disable-line react-hooks/exhaustive-deps

    const questions = attempt?.questions || [];
    const currentQ = questions[currentIdx];
    const answers = attempt?.answers || {};
    const flagged = attempt?.flagged || [];
    const timeRemaining = attempt?.timeRemaining ?? 0;

    // Save answer to backend
    const handleSelectAnswer = async (questionId, value) => {
        setAnswer(questionId, value);
        setSavingAnswer(true);
        try {
            await assessmentService.submitAnswer(assessmentId, attemptId, {
                question_id: questionId,
                answer: value,
            });
        } catch { /* silent – answers synced on submit */ }
        finally { setSavingAnswer(false); }
    };

    const handleToggleFlag = (questionId) => {
        toggleFlag(questionId);
    };

    const handleFinalSubmit = async () => {
        if (!window.confirm('Submit this assessment? You cannot change your answers after submission.')) return;
        setSubmitting(true);
        try {
            const { data } = await assessmentService.finalSubmit(assessmentId, attemptId, { answers });
            clearInterval(timerRef.current);
            navigate(`/assessments/${assessmentId}/results/${data.id || attemptId}`);
        } catch (err) {
            alert(getApiErrorMessage(err, 'Submission failed. Please try again.'));
        } finally {
            setSubmitting(false);
        }
    };

    // Proctoring – report tab visibility changes
    useEffect(() => {
        const handleVisibility = () => {
            if (document.hidden) {
                assessmentService.reportProctorEvent(assessmentId, attemptId, {
                    event_type: 'tab_switch',
                    timestamp: new Date().toISOString(),
                }).catch(() => {});
            }
        };
        document.addEventListener('visibilitychange', handleVisibility);
        return () => document.removeEventListener('visibilitychange', handleVisibility);
    }, [assessmentId, attemptId]);

    const answeredCount = Object.keys(answers).length;
    const flaggedCount = flagged.length;
    const isUrgent = timeRemaining < 120;

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Player">
                <div className="ap-skeleton">
                    <Skeleton style={{ width: '100%', height: '400px', borderRadius: '12px' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Assessment" pageTitleLine2="Player">
                <div className="ap-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Assessment In Progress',
                status: `Time: ${formatTime(timeRemaining)}`,
                info: `${answeredCount}/${questions.length} answered`,
            }}
            pageTitleLine1="Assessment"
            pageTitleLine2="Player"
        >
            <div className="ap-layout">
                {/* Question navigator sidebar */}
                <aside className="ap-navigator">
                    <div className={`ap-timer ${isUrgent ? 'urgent' : ''}`}>
                        <span className="ap-timer__label">Time Remaining</span>
                        <span className="ap-timer__value">{formatTime(timeRemaining)}</span>
                    </div>
                    <div className="ap-nav-grid">
                        {questions.map((q, i) => {
                            const isAnswered = answers[q.id] !== undefined;
                            const isFlagged = flagged.includes(q.id);
                            const isCurrent = i === currentIdx;
                            let cls = 'ap-nav-cell';
                            if (isCurrent) cls += ' current';
                            if (isAnswered) cls += ' answered';
                            if (isFlagged) cls += ' flagged';
                            return (
                                <button key={q.id} className={cls} onClick={() => setCurrentIdx(i)}>
                                    {i + 1}
                                    {isFlagged && <span className="ap-flag-dot" />}
                                </button>
                            );
                        })}
                    </div>
                    <div className="ap-nav-legend">
                        <span><span className="ap-legend-box answered" /> Answered ({answeredCount})</span>
                        <span><span className="ap-legend-box flagged" /> Flagged ({flaggedCount})</span>
                        <span><span className="ap-legend-box" /> Unanswered ({questions.length - answeredCount})</span>
                    </div>
                    <button
                        className="ap-submit-btn"
                        onClick={handleFinalSubmit}
                        disabled={submitting}
                    >
                        {submitting ? 'Submitting…' : 'Submit Assessment'}
                    </button>
                </aside>

                {/* Question area */}
                <div className="ap-question-area">
                    {currentQ ? (
                        <>
                            <div className="ap-question-header">
                                <span className="ap-question-num">Question {currentIdx + 1} of {questions.length}</span>
                                <button
                                    className={`ap-flag-btn ${flagged.includes(currentQ.id) ? 'active' : ''}`}
                                    onClick={() => handleToggleFlag(currentQ.id)}
                                >
                                    {flagged.includes(currentQ.id) ? '🚩 Flagged' : '⚑ Flag'}
                                </button>
                            </div>

                            <div className="ap-question-body">
                                <p className="ap-question-text">{currentQ.text || currentQ.question_text}</p>

                                {/* Multiple choice */}
                                {(currentQ.question_type === 'mcq' || currentQ.choices || currentQ.options) && (
                                    <div className="ap-choices">
                                        {(currentQ.choices || currentQ.options || []).map((opt, oi) => {
                                            const optValue = typeof opt === 'string' ? opt : opt.id || opt.value;
                                            const optLabel = typeof opt === 'string' ? opt : opt.text || opt.label;
                                            const isSelected = answers[currentQ.id] === optValue;
                                            return (
                                                <label
                                                    key={oi}
                                                    className={`ap-choice ${isSelected ? 'selected' : ''}`}
                                                >
                                                    <input
                                                        type="radio"
                                                        name={`q-${currentQ.id}`}
                                                        checked={isSelected}
                                                        onChange={() => handleSelectAnswer(currentQ.id, optValue)}
                                                    />
                                                    <span className="ap-choice__letter">{String.fromCharCode(65 + oi)}</span>
                                                    <span className="ap-choice__text">{optLabel}</span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                )}

                                {/* True/False */}
                                {currentQ.question_type === 'true_false' && (
                                    <div className="ap-choices">
                                        {['True', 'False'].map((val) => (
                                            <label
                                                key={val}
                                                className={`ap-choice ${answers[currentQ.id] === val.toLowerCase() ? 'selected' : ''}`}
                                            >
                                                <input
                                                    type="radio"
                                                    name={`q-${currentQ.id}`}
                                                    checked={answers[currentQ.id] === val.toLowerCase()}
                                                    onChange={() => handleSelectAnswer(currentQ.id, val.toLowerCase())}
                                                />
                                                <span className="ap-choice__text">{val}</span>
                                            </label>
                                        ))}
                                    </div>
                                )}

                                {/* Short answer / essay */}
                                {(currentQ.question_type === 'short_answer' || currentQ.question_type === 'essay') && (
                                    <textarea
                                        className="ap-text-answer"
                                        rows={currentQ.question_type === 'essay' ? 8 : 3}
                                        placeholder="Type your answer here..."
                                        value={answers[currentQ.id] || ''}
                                        onChange={(e) => handleSelectAnswer(currentQ.id, e.target.value)}
                                    />
                                )}

                                {/* Code */}
                                {currentQ.question_type === 'code' && (
                                    <textarea
                                        className="ap-code-answer"
                                        rows={12}
                                        placeholder="Write your code here..."
                                        value={answers[currentQ.id] || ''}
                                        onChange={(e) => handleSelectAnswer(currentQ.id, e.target.value)}
                                        spellCheck={false}
                                    />
                                )}
                            </div>

                            {/* Nav buttons */}
                            <div className="ap-question-nav">
                                <button
                                    className="ap-nav-btn"
                                    onClick={() => setCurrentIdx((p) => Math.max(0, p - 1))}
                                    disabled={currentIdx === 0}
                                >
                                    ← Previous
                                </button>
                                {savingAnswer && <span className="ap-saving">Saving…</span>}
                                <button
                                    className="ap-nav-btn"
                                    onClick={() => setCurrentIdx((p) => Math.min(questions.length - 1, p + 1))}
                                    disabled={currentIdx === questions.length - 1}
                                >
                                    Next →
                                </button>
                            </div>
                        </>
                    ) : (
                        <p className="ap-no-questions">No questions available.</p>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default AssessmentPlayer;
