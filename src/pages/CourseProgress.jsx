import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { getCourseRoute, getLessonRoute, normaliseCourseDetail, normaliseCourseProgress } from '../utils/learningContracts';
import './CourseProgress.css';

const CourseProgress = () => {
    const { courseId: courseSlug } = useParams();
    const navigate = useNavigate();
    const { activeCourse, setActiveCourse, courseProgress, setCourseProgress } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    usePageTitle('Course Progress', 'Track your journey through each module and lesson.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [courseResponse, progressResponse] = await Promise.all([
                courseService.getCourse(courseSlug),
                courseService.getCourseProgress(courseSlug),
            ]);
            const course = normaliseCourseDetail(courseResponse.data);
            const progress = normaliseCourseProgress(progressResponse.data, course);
            setActiveCourse(course);
            setCourseProgress(progress);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load progress data.'));
        } finally {
            setLoading(false);
        }
    }, [courseSlug, setActiveCourse, setCourseProgress]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const course = activeCourse;
    const progress = courseProgress;
    const modules = progress?.modules || [];
    const overallPct = progress?.overall_progress ?? 0;
    const completedLessons = progress?.completed_lessons ?? 0;
    const totalLessons = progress?.total_lessons ?? 0;

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Course" pageTitleLine2="Progress">
                <div className="cp-skeleton">
                    <Skeleton style={{ width: '100%', height: '60px', borderRadius: '8px', marginBottom: '24px' }} />
                    {Array.from({ length: 4 }).map((_, index) => (
                        <Skeleton key={index} style={{ width: '100%', height: '44px', marginBottom: '12px', borderRadius: '6px' }} />
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
                info: course?.slug ? `Course: ${course.slug}` : `Course: ${courseSlug}`,
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

                <div className="cp-overall">
                    <div className="cp-overall__bar">
                        <div className="cp-overall__fill" style={{ width: `${overallPct}%` }} />
                    </div>
                    <span className="cp-overall__label">{overallPct}% complete - {completedLessons} of {totalLessons} lessons</span>
                </div>

                <div className="cp-modules">
                    {modules.map((module, moduleIndex) => (
                        <div key={module.id || moduleIndex} className="cp-module">
                            <div className="cp-module__header">
                                <span className="cp-module__num">{String(moduleIndex + 1).padStart(2, '0')}</span>
                                <h3 className="cp-module__title">{module.title}</h3>
                                <span className="cp-module__pct">{module.percentage}%</span>
                            </div>
                            <div className="cp-module__bar">
                                <div className="cp-module__bar-fill" style={{ width: `${module.percentage}%` }} />
                            </div>
                            <ul className="cp-lesson-list">
                                {module.lessons.map((lesson, lessonIndex) => {
                                    const isDone = Boolean(lesson.is_completed);
                                    return (
                                        <li key={lesson.id || lessonIndex} className={`cp-lesson ${isDone ? 'done' : ''}`}>
                                            <span className="cp-lesson__check">{isDone ? 'Done' : 'Open'}</span>
                                            <Link
                                                to={getLessonRoute(course || { slug: courseSlug }, lesson)}
                                                className="cp-lesson__link"
                                            >
                                                {lesson.title}
                                            </Link>
                                            {lesson.progress?.progress_pct != null && !isDone && (
                                                <span className="cp-lesson__partial">{lesson.progress.progress_pct}%</span>
                                            )}
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    ))}
                </div>

                <div className="cp-actions">
                    <button className="cp-back-btn" onClick={() => navigate(getCourseRoute(course || { slug: courseSlug }))}>
                        Back to Course
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
