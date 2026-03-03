import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CourseProgress.css';

const CourseProgress = () => {
    const { courseId } = useParams();
    const navigate = useNavigate();
    const { activeCourse, setActiveCourse, courseProgress, setCourseProgress } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    usePageTitle('Course Progress', 'Track your journey through each module and lesson.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [courseRes, progressRes] = await Promise.all([
                courseService.getCourse(courseId),
                courseService.getCourseProgress(courseId),
            ]);
            setActiveCourse(courseRes.data);
            setCourseProgress(progressRes.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load progress data.'));
        } finally {
            setLoading(false);
        }
    }, [courseId, setActiveCourse, setCourseProgress]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const course = activeCourse;
    const progress = courseProgress;
    const modules = course?.modules || course?.curriculum || [];
    const overallPct = progress?.overall_progress ?? progress?.progress_pct ?? 0;
    const completedLessons = progress?.completed_lessons ?? 0;
    const totalLessons = progress?.total_lessons ?? modules.reduce((s, m) => s + (m.lessons?.length || 0), 0);
    const lessonStatusMap = progress?.lesson_statuses || {};

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Course" pageTitleLine2="Progress">
                <div className="cp-skeleton">
                    <Skeleton style={{ width: '100%', height: '60px', borderRadius: '8px', marginBottom: '24px' }} />
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} style={{ width: '100%', height: '44px', marginBottom: '12px', borderRadius: '6px' }} />
                    ))}
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Course" pageTitleLine2="Progress">
                <div className="cp-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Course Progress',
                status: `${overallPct}% Complete`,
                info: `Course #${courseId}`,
            }}
            pageTitleLine1="Course"
            pageTitleLine2="Progress"
            headerRightContent={
                <div className="cp-header-stats">
                    <div className="cp-stat"><span className="cp-stat__val">{overallPct}%</span><span className="cp-stat__label">Overall</span></div>
                    <div className="cp-stat"><span className="cp-stat__val">{completedLessons}/{totalLessons}</span><span className="cp-stat__label">Lessons</span></div>
                </div>
            }
        >
            <div className="cp-page">
                <h2 className="cp-course-title">{course?.title}</h2>

                {/* Overall progress bar */}
                <div className="cp-overall">
                    <div className="cp-overall__bar">
                        <div className="cp-overall__fill" style={{ width: `${overallPct}%` }} />
                    </div>
                    <span className="cp-overall__label">{overallPct}% complete — {completedLessons} of {totalLessons} lessons</span>
                </div>

                {/* Module breakdowns */}
                <div className="cp-modules">
                    {modules.map((mod, mi) => {
                        const lessons = mod.lessons || [];
                        const modCompleted = lessons.filter((l) => lessonStatusMap[l.id]?.completed).length;
                        const modPct = lessons.length ? Math.round((modCompleted / lessons.length) * 100) : 0;

                        return (
                            <div key={mod.id || mi} className="cp-module">
                                <div className="cp-module__header">
                                    <span className="cp-module__num">{String(mi + 1).padStart(2, '0')}</span>
                                    <h3 className="cp-module__title">{mod.title}</h3>
                                    <span className="cp-module__pct">{modPct}%</span>
                                </div>
                                <div className="cp-module__bar">
                                    <div className="cp-module__bar-fill" style={{ width: `${modPct}%` }} />
                                </div>
                                <ul className="cp-lesson-list">
                                    {lessons.map((lesson, li) => {
                                        const status = lessonStatusMap[lesson.id] || {};
                                        const isDone = status.completed;
                                        return (
                                            <li key={lesson.id || li} className={`cp-lesson ${isDone ? 'done' : ''}`}>
                                                <span className="cp-lesson__check">{isDone ? '✓' : '○'}</span>
                                                <Link
                                                    to={`/courses/${courseId}/lessons/${lesson.id}`}
                                                    className="cp-lesson__link"
                                                >
                                                    {lesson.title}
                                                </Link>
                                                {status.progress_pct != null && !isDone && (
                                                    <span className="cp-lesson__partial">{status.progress_pct}%</span>
                                                )}
                                            </li>
                                        );
                                    })}
                                </ul>
                            </div>
                        );
                    })}
                </div>

                {/* Actions */}
                <div className="cp-actions">
                    <button className="cp-back-btn" onClick={() => navigate(`/courses/${courseId}`)}>
                        ← Back to Course
                    </button>
                    {overallPct === 100 && (
                        <button className="cp-cert-btn" onClick={() => navigate('/my-learning?tab=certificates')}>
                            View Certificate
                        </button>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CourseProgress;
