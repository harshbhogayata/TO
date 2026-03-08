import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { sanitizeHTML } from '../utils/sanitize';
import './LessonPlayer.css';

const LessonPlayer = () => {
    const { courseId, lessonId } = useParams();
    const navigate = useNavigate();
    const { activeLesson, setActiveLesson, activeCourse, setActiveCourse } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [sidebarLessons, setSidebarLessons] = useState([]);
    const [progressPct, setProgressPct] = useState(0);
    const [saving, setSaving] = useState(false);
    const [completed, setCompleted] = useState(false);
    const videoRef = useRef(null);

    usePageTitle('Lesson Player', 'Watch and learn - track your progress as you go.');

    // Fetch course if not loaded yet
    const ensureCourse = useCallback(async () => {
        if (activeCourse?.id === Number(courseId)) return;
        try {
            const { data } = await courseService.getCourse(courseId);
            setActiveCourse(data);
        } catch { /* will still load lesson */ }
    }, [courseId, activeCourse, setActiveCourse]);

    // Flatten all lessons from modules
    useEffect(() => {
        if (!activeCourse?.modules) return;
        const flat = activeCourse.modules.flatMap((mod) =>
            (mod.lessons || []).map((l) => ({ ...l, moduleName: mod.title }))
        );
        setSidebarLessons(flat);
    }, [activeCourse]);

    const fetchLesson = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await courseService.getLesson(courseId, lessonId);
            setActiveLesson(data);
            setCompleted(data.is_completed || false);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load lesson.'));
        } finally {
            setLoading(false);
        }
    }, [courseId, lessonId, setActiveLesson]);

    useEffect(() => {
        ensureCourse();
        fetchLesson();
    }, [ensureCourse, fetchLesson]);

    // Auto-save progress on video time update
    const handleTimeUpdate = useCallback(() => {
        if (!videoRef.current) return;
        const pct = Math.round((videoRef.current.currentTime / videoRef.current.duration) * 100) || 0;
        setProgressPct(pct);
    }, []);

    const saveProgress = async (markComplete = false) => {
        setSaving(true);
        try {
            await courseService.updateLessonProgress(courseId, lessonId, {
                progress_pct: markComplete ? 100 : progressPct,
                completed: markComplete,
            });
            if (markComplete) setCompleted(true);
        } catch { /* silent */ }
        finally { setSaving(false); }
    };

    const handleMarkComplete = () => saveProgress(true);

    // Navigation helpers
    const currentIdx = sidebarLessons.findIndex((l) => String(l.id) === String(lessonId));
    const prevLesson = currentIdx > 0 ? sidebarLessons[currentIdx - 1] : null;
    const nextLesson = currentIdx < sidebarLessons.length - 1 ? sidebarLessons[currentIdx + 1] : null;

    const goToLesson = (lid) => navigate(`/courses/${courseId}/lessons/${lid}`);

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
                info: `Course #${courseId}`,
            }}
            pageTitleLine1="Lesson"
            pageTitleLine2="Player"
        >
            <div className="lp-layout">
                {/* Sidebar: lesson list */}
                <aside className="lp-sidebar">
                    <h4 className="lp-sidebar__heading">Lessons</h4>
                    <ul className="lp-sidebar__list">
                        {sidebarLessons.map((l, i) => (
                            <li
                                key={l.id}
                                className={`lp-sidebar__item ${String(l.id) === String(lessonId) ? 'active' : ''}`}
                                onClick={() => goToLesson(l.id)}
                            >
                                <span className="lp-sidebar__num">{String(i + 1).padStart(2, '0')}</span>
                                <div className="lp-sidebar__meta">
                                    <span className="lp-sidebar__title">{l.title}</span>
                                    <span className="lp-sidebar__module">{l.moduleName}</span>
                                </div>
                            </li>
                        ))}
                    </ul>
                </aside>

                {/* Main player area */}
                <div className="lp-main">
                    <div className="lp-player-wrap">
                        {lesson?.content_type === 'video' || lesson?.video_url ? (
                            <video
                                ref={videoRef}
                                className="lp-video"
                                src={lesson?.video_url}
                                controls
                                onTimeUpdate={handleTimeUpdate}
                                onEnded={() => saveProgress(true)}
                            />
                        ) : (
                            <div className="lp-content-block">
                                <div dangerouslySetInnerHTML={{ __html: lessonHtml || '<p>No content available.</p>' }} />
                            </div>
                        )}
                    </div>

                    {/* Progress bar */}
                    <div className="lp-progress-strip">
                        <div className="lp-progress-bar">
                            <div className="lp-progress-bar__fill" style={{ width: `${progressPct}%` }} />
                        </div>
                        <span className="lp-progress-label">{progressPct}%</span>
                    </div>

                    {/* Lesson info */}
                    <div className="lp-lesson-info">
                        <h2 className="lp-lesson-title">{lesson?.title}</h2>
                        <p className="lp-lesson-desc">{lesson?.description}</p>
                    </div>

                    {/* Actions */}
                    <div className="lp-actions">
                        {prevLesson && (
                            <button className="lp-nav-btn" onClick={() => goToLesson(prevLesson.id)}>
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
                            <button className="lp-nav-btn" onClick={() => goToLesson(nextLesson.id)}>
                                Next
                            </button>
                        )}
                    </div>

                    {/* Attachments / Resources */}
                    {lesson?.attachments && lesson.attachments.length > 0 && (
                        <section className="lp-resources">
                            <h4>Resources</h4>
                            <ul>
                                {lesson.attachments.map((att, i) => (
                                    <li key={i}>
                                        <a href={att.url || att.file} target="_blank" rel="noreferrer">
                                            {att.title || att.name || `Resource ${i + 1}`}
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