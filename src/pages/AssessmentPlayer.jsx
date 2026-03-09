import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { buildAssessmentAnswerPayload, normaliseAssessmentAttempt } from '../utils/learningContracts';
import './AssessmentPlayer.css';

const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
};

const hasAnswer = (value) => (Array.isArray(value) ? value.length > 0 : value !== '' && value != null);

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

    const fetchAttempt = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await assessmentService.getAttempt(attemptId);
            setAttempt(normaliseAssessmentAttempt(data));
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load assessment attempt.'));
        } finally {
            setLoading(false);
        }
    }, [attemptId, setAttempt]);

    useEffect(() => {
        fetchAttempt();
    }, [fetchAttempt]);

    const handleFinalSubmit = useCallback(async () => {
        if (!window.confirm('Submit this assessment? You cannot change your answers after submission.')) {
            return;
        }

        setSubmitting(true);
        try {
            const { data } = await assessmentService.finalSubmit(attemptId);
            clearInterval(timerRef.current);
            navigate(`/assessments/${assessmentId}/results/${data.attempt_id || attemptId}`);
        } catch (err) {
            window.alert(getApiErrorMessage(err, 'Submission failed. Please try again.'));
        } finally {
            setSubmitting(false);
        }
    }, [assessmentId, attemptId, navigate]);

    useEffect(() => {
        if (!attempt || attempt.status !== 'in_progress') {
            return undefined;
        }

        timerRef.current = setInterval(() => {
            setTimeRemaining((previous) => {
                if (previous <= 1) {
                    clearInterval(timerRef.current);
                    void handleFinalSubmit();
                    return 0;
                }
                return previous - 1;
            });
        }, 1000);

        return () => clearInterval(timerRef.current);
    }, [attempt, handleFinalSubmit, setTimeRemaining]);

    const questions = attempt?.questions || [];
    const currentQuestion = questions[currentIdx];
    const answers = attempt?.answers || {};
    const flagged = attempt?.flagged || [];
    const timeRemaining = attempt?.timeRemaining ?? 0;

    const submitQuestionAnswer = async (question, value, options = {}) => {
        setAnswer(question.id, value);
        setSavingAnswer(true);
        try {
            await assessmentService.submitAnswer(attemptId, buildAssessmentAnswerPayload(question, value, {
                isBookmarked: flagged.includes(String(question.id)),
                ...options,
            }));
        } catch {
            // final submit is the last protection if incremental saves fail
        } finally {
            setSavingAnswer(false);
        }
    };

    const handleSelectAnswer = async (question, value) => {
        await submitQuestionAnswer(question, value);
    };

    const handleToggleMultiSelect = async (question, optionId) => {
        const currentValue = Array.isArray(answers[String(question.id)]) ? answers[String(question.id)] : [];
        const nextValue = currentValue.includes(optionId)
            ? currentValue.filter((value) => value !== optionId)
            : [...currentValue, optionId];
        await submitQuestionAnswer(question, nextValue);
    };

    const handleToggleFlag = async (question) => {
        toggleFlag(question.id);
        const nextIsBookmarked = !flagged.includes(String(question.id));
        try {
            await assessmentService.submitAnswer(attemptId, buildAssessmentAnswerPayload(
                question,
                answers[String(question.id)],
                { isBookmarked: nextIsBookmarked },
            ));
        } catch {
            // keep local bookmark state even if sync fails
        }
    };

    useEffect(() => {
        const handleVisibility = () => {
            if (document.hidden) {
                assessmentService.reportProctorEvent(attemptId, {
                    event_type: 'tab_switch',
                    timestamp: new Date().toISOString(),
                }).catch(() => {});
            }
        };
        document.addEventListener('visibilitychange', handleVisibility);
        return () => document.removeEventListener('visibilitychange', handleVisibility);
    }, [attemptId]);

    const answeredCount = Object.keys(answers).filter((questionId) => hasAnswer(answers[questionId])).length;
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
                <aside className="ap-navigator">
                    <div className={`ap-timer ${isUrgent ? 'urgent' : ''}`}>
                        <span className="ap-timer__label">Time Remaining</span>
                        <span className="ap-timer__value">{formatTime(timeRemaining)}</span>
                    </div>
                    <div className="ap-nav-grid">
                        {questions.map((question, index) => {
                            const isAnswered = hasAnswer(answers[String(question.id)]);
                            const isFlagged = flagged.includes(String(question.id));
                            const isCurrent = index === currentIdx;
                            let className = 'ap-nav-cell';
                            if (isCurrent) className += ' current';
                            if (isAnswered) className += ' answered';
                            if (isFlagged) className += ' flagged';
                            return (
                                <button key={question.id} className={className} onClick={() => setCurrentIdx(index)}>
                                    {index + 1}
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
                        onClick={() => void handleFinalSubmit()}
                        disabled={submitting}
                    >
                        {submitting ? 'Submitting...' : 'Submit Assessment'}
                    </button>
                </aside>

                <div className="ap-question-area">
                    {currentQuestion ? (
                        <>
                            <div className="ap-question-header">
                                <span className="ap-question-num">Question {currentIdx + 1} of {questions.length}</span>
                                <button
                                    className={`ap-flag-btn ${flagged.includes(String(currentQuestion.id)) ? 'active' : ''}`}
                                    onClick={() => void handleToggleFlag(currentQuestion)}
                                >
                                    {flagged.includes(String(currentQuestion.id)) ? 'Flagged' : 'Flag'}
                                </button>
                            </div>

                            <div className="ap-question-body">
                                <p className="ap-question-text">{currentQuestion.text || currentQuestion.question_text}</p>

                                {(currentQuestion.question_type === 'mcq') && (
                                    <div className="ap-choices">
                                        {currentQuestion.options.map((option, optionIndex) => {
                                            const optionValue = option.id ?? option.value;
                                            const isSelected = answers[String(currentQuestion.id)] === optionValue;
                                            return (
                                                <label key={optionValue || optionIndex} className={`ap-choice ${isSelected ? 'selected' : ''}`}>
                                                    <input
                                                        type="radio"
                                                        name={`q-${currentQuestion.id}`}
                                                        checked={isSelected}
                                                        onChange={() => void handleSelectAnswer(currentQuestion, optionValue)}
                                                    />
                                                    <span className="ap-choice__letter">{String.fromCharCode(65 + optionIndex)}</span>
                                                    <span className="ap-choice__text">{option.text}</span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                )}

                                {currentQuestion.question_type === 'multi_select' && (
                                    <div className="ap-choices">
                                        {currentQuestion.options.map((option, optionIndex) => {
                                            const optionValue = option.id ?? option.value;
                                            const selectedValues = Array.isArray(answers[String(currentQuestion.id)]) ? answers[String(currentQuestion.id)] : [];
                                            const isSelected = selectedValues.includes(optionValue);
                                            return (
                                                <label key={optionValue || optionIndex} className={`ap-choice ${isSelected ? 'selected' : ''}`}>
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => void handleToggleMultiSelect(currentQuestion, optionValue)}
                                                    />
                                                    <span className="ap-choice__letter">{String.fromCharCode(65 + optionIndex)}</span>
                                                    <span className="ap-choice__text">{option.text}</span>
                                                </label>
                                            );
                                        })}
                                    </div>
                                )}

                                {currentQuestion.question_type === 'true_false' && (
                                    <div className="ap-choices">
                                        {[true, false].map((value) => (
                                            <label
                                                key={String(value)}
                                                className={`ap-choice ${answers[String(currentQuestion.id)] === value ? 'selected' : ''}`}
                                            >
                                                <input
                                                    type="radio"
                                                    name={`q-${currentQuestion.id}`}
                                                    checked={answers[String(currentQuestion.id)] === value}
                                                    onChange={() => void handleSelectAnswer(currentQuestion, value)}
                                                />
                                                <span className="ap-choice__text">{value ? 'True' : 'False'}</span>
                                            </label>
                                        ))}
                                    </div>
                                )}

                                {(currentQuestion.question_type === 'short_answer' || currentQuestion.question_type === 'essay') && (
                                    <textarea
                                        className="ap-text-answer"
                                        rows={currentQuestion.question_type === 'essay' ? 8 : 3}
                                        placeholder="Type your answer here..."
                                        value={answers[String(currentQuestion.id)] || ''}
                                        onChange={(event) => void handleSelectAnswer(currentQuestion, event.target.value)}
                                    />
                                )}

                                {currentQuestion.question_type === 'code' && (
                                    <textarea
                                        className="ap-code-answer"
                                        rows={12}
                                        placeholder="Write your code here..."
                                        value={answers[String(currentQuestion.id)] || ''}
                                        onChange={(event) => void handleSelectAnswer(currentQuestion, event.target.value)}
                                        spellCheck={false}
                                    />
                                )}
                            </div>

                            <div className="ap-question-nav">
                                <button
                                    className="ap-nav-btn"
                                    onClick={() => setCurrentIdx((previous) => Math.max(0, previous - 1))}
                                    disabled={currentIdx === 0}
                                >
                                    Previous
                                </button>
                                {savingAnswer && <span className="ap-saving">Saving...</span>}
                                <button
                                    className="ap-nav-btn"
                                    onClick={() => setCurrentIdx((previous) => Math.min(questions.length - 1, previous + 1))}
                                    disabled={currentIdx === questions.length - 1}
                                >
                                    Next
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



