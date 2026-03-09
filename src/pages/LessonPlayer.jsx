import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { sanitizeHTML } from '../utils/sanitize';
import { getLessonRoute, normaliseCourseDetail } from '../utils/learningContracts';
import './LessonPlayer.css';

const LessonPlayer = () => {
    const { courseId: courseSlug, lessonId: lessonSlug } = useParams();
    const navigate = useNavigate();
    const { activeLesson, setActiveLesson, activeCourse, setActiveCourse } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [sidebarLessons, setSidebarLessons] = useState([]);
    const [progressPct, setProgressPct] = useState(0);
    const [saving, setSaving] = useState(false);
    const [completed, setCompleted] = useState(false);
    const videoRef = useRef(null);
    const lastSavedPositionRef = useRef(0);

    usePageTitle('Lesson Player', 'Watch and learn - track your progress as you go.');

    const ensureCourse = useCallback(async () => {
        if (activeCourse?.slug === courseSlug) {
            return;
        }

        try {
            const { data } = await courseService.getCourse(courseSlug);
            setActiveCourse(normaliseCourseDetail(data));
        } catch {
            // lesson fetch will surface the user-visible error if this fails too
        }
    }, [courseSlug, activeCourse, setActiveCourse]);

    useEffect(() => {
        if (!activeCourse?.modules) {
            return;
        }

        const flatLessons = activeCourse.modules.flatMap((module) =>
            (module.lessons || []).map((lesson) => ({ ...lesson, moduleName: module.title })),
        );
        setSidebarLessons(flatLessons);
    }, [activeCourse]);

    const fetchLesson = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await courseService.getLesson(courseSlug, lessonSlug);
            const savedPosition = Number(data.progress?.video_position_seconds ?? 0);
            const duration = Number(data.video_duration_seconds ?? 0);
            setActiveLesson(data);
            setCompleted(Boolean(data.is_completed));
            setProgressPct(data.is_completed ? 100 : duration > 0 ? Math.round((savedPosition / duration) * 100) : Number(data.progress?.progress_pct ?? 0));
            lastSavedPositionRef.current = savedPosition;
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load lesson.'));
        } finally {
            setLoading(false);
        }
    }, [courseSlug, lessonSlug, setActiveLesson]);

    useEffect(() => {
        ensureCourse();
        fetchLesson();
    }, [ensureCourse, fetchLesson]);

    useEffect(() => {
        if (!videoRef.current || !activeLesson?.video_duration_seconds) {
            return undefined;
        }

        const element = videoRef.current;
        const savedPosition = Number(activeLesson.progress?.video_position_seconds ?? 0);

        const syncPosition = () => {
            if (savedPosition > 0 && savedPosition < element.duration) {
                element.currentTime = savedPosition;
            }
            if (!completed && element.duration > 0) {
                setProgressPct(Math.round((savedPosition / element.duration) * 100));
            }
        };

        element.addEventListener('loadedmetadata', syncPosition);
        return () => element.removeEventListener('loadedmetadata', syncPosition);
    }, [activeLesson, completed]);

    const persistProgress = useCallback(async ({ markComplete = false, force = false } = {}) => {
        const currentPosition = Math.round(videoRef.current?.currentTime ?? activeLesson?.progress?.video_position_seconds ?? 0);
        const previousPosition = lastSavedPositionRef.current;
        const additionalTime = Math.max(currentPosition - previousPosition, 0);

        if (!markComplete && !force && additionalTime <= 0) {
            return;
        }

        setSaving(true);
        try {
            const payload = {
                video_position_seconds: currentPosition,
            };
            if (additionalTime > 0) {
                payload.time_spent_seconds = additionalTime;
            }
            if (markComplete) {
                payload.mark_completed = true;
            }

            const { data } = await courseService.updateLessonProgress(courseSlug, lessonSlug, payload);
            lastSavedPositionRef.current = currentPosition;
            setCompleted(Boolean(markComplete || data?.is_completed));
            setActiveLesson(activeLesson ? {
                ...activeLesson,
                progress: data,
                is_completed: Boolean(markComplete || data?.is_completed),
            } : activeLesson);
        } catch {
            // keep the player usable if persistence fails
        } finally {
            setSaving(false);
        }
    }, [activeLesson, courseSlug, lessonSlug, setActiveLesson]);

    useEffect(() => () => {
        void persistProgress({ force: true });
    }, [persistProgress]);

    const handleTimeUpdate = useCallback(() => {
        if (!videoRef.current || !videoRef.current.duration) {
            return;
        }
        const pct = Math.round((videoRef.current.currentTime / videoRef.current.duration) * 100) || 0;
        setProgressPct(pct);
    }, []);

    const handleMarkComplete = () => {
        void persistProgress({ markComplete: true, force: true });
    };

    const currentIdx = sidebarLessons.findIndex((lesson) => String(lesson.slug || lesson.id) === String(lessonSlug));
    const prevLesson = currentIdx > 0 ? sidebarLessons[currentIdx - 1] : null;
    const nextLesson = currentIdx < sidebarLessons.length - 1 ? sidebarLessons[currentIdx + 1] : null;

    const goToLesson = (lesson) => navigate(getLessonRoute(activeCourse || { slug: courseSlug }, lesson));

    const lesson = activeLesson;
    const lessonHtml = sanitizeHTML(lesson?.text_content || '');

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Lesson" pageTitleLine2="Player">
                <div className="lp-skeleton">
                    <Skeleton style={{ width: '100%', height: '400px', borderRadius: '12px' }} />
                    <Skeleton style={{ width: '50%', height: '28px', marginTop: '20px' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Lesson" pageTitleLine2="Player">
                <div className="lp-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Lesson Player',
                status: completed ? 'Completed' : `${progressPct}% watched`,
                info: activeCourse?.slug ? `Course: ${activeCourse.slug}` : `Course: ${courseSlug}`,
            }}
            pageTitleLine1="Lesson"
            pageTitleLine2="Player"
        >
            <div className="lp-layout">
                <aside className="lp-sidebar">
                    <h4 className="lp-sidebar__heading">Lessons</h4>
                    <ul className="lp-sidebar__list">
                        {sidebarLessons.map((lessonItem, index) => (
                            <li
                                key={lessonItem.slug || lessonItem.id}
                                className={`lp-sidebar__item ${String(lessonItem.slug || lessonItem.id) === String(lessonSlug) ? 'active' : ''}`}
                                onClick={() => goToLesson(lessonItem)}
                            >
                                <span className="lp-sidebar__num">{String(index + 1).padStart(2, '0')}</span>
                                <div className="lp-sidebar__meta">
                                    <span className="lp-sidebar__title">{lessonItem.title}</span>
                                    <span className="lp-sidebar__module">{lessonItem.moduleName}</span>
                                </div>
                            </li>
                        ))}
                    </ul>
                </aside>

                <div className="lp-main">
                    <div className="lp-player-wrap">
                        {lesson?.content_type === 'video' || lesson?.video_url ? (
                            <video
                                ref={videoRef}
                                className="lp-video"
                                src={lesson?.video_url}
                                controls
                                onTimeUpdate={handleTimeUpdate}
                                onPause={() => void persistProgress({ force: true })}
                                onEnded={() => void persistProgress({ markComplete: true, force: true })}
                            />
                        ) : (
                            <div className="lp-content-block">
                                <div dangerouslySetInnerHTML={{ __html: lessonHtml || '<p>No content available.</p>' }} />
                            </div>
                        )}
                    </div>

                    <div className="lp-progress-strip">
                        <div className="lp-progress-bar">
                            <div className="lp-progress-bar__fill" style={{ width: `${progressPct}%` }} />
                        </div>
                        <span className="lp-progress-label">{progressPct}%</span>
                    </div>

                    <div className="lp-lesson-info">
                        <h2 className="lp-lesson-title">{lesson?.title}</h2>
                        <p className="lp-lesson-desc">{lesson?.description}</p>
                    </div>

                    <div className="lp-actions">
                        {prevLesson && (
                            <button className="lp-nav-btn" onClick={() => goToLesson(prevLesson)}>
                                Previous
                            </button>
                        )}
                        {!completed && (
                            <button className="lp-complete-btn" onClick={handleMarkComplete} disabled={saving}>
                                {saving ? 'Saving...' : 'Mark Complete'}
                            </button>
                        )}
                        {completed && <span className="lp-completed-badge">Completed</span>}
                        {nextLesson && (
                            <button className="lp-nav-btn" onClick={() => goToLesson(nextLesson)}>
                                Next
                            </button>
                        )}
                    </div>

                    {lesson?.attachments && lesson.attachments.length > 0 && (
                        <section className="lp-resources">
                            <h4>Resources</h4>
                            <ul>
                                {lesson.attachments.map((attachment, index) => (
                                    <li key={attachment.id || index}>
                                        <a href={attachment.file_url || attachment.url || attachment.file} target="_blank" rel="noreferrer">
                                            {attachment.title || attachment.name || `Resource ${index + 1}`}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default LessonPlayer;
