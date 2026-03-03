import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { useAuthStore } from '../store/authStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CourseDetail.css';

const StarRating = ({ value = 0, size = 18 }) => (
    <span className="cd-star-row">
        {[1, 2, 3, 4, 5].map((star) => (
            <span
                key={star}
                style={{ fontSize: size, color: star <= Math.round(value) ? '#FFD700' : '#555' }}
            >
                ★
            </span>
        ))}
    </span>
);

const CourseDetail = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useAuthStore();
    const { activeCourse, setActiveCourse, reviews, setReviews } = useCourseStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [enrolling, setEnrolling] = useState(false);
    const [isEnrolled, setIsEnrolled] = useState(false);
    const [enrollmentId, setEnrollmentId] = useState(null);
    const [expandedModule, setExpandedModule] = useState(null);
    const [reviewText, setReviewText] = useState('');
    const [reviewRating, setReviewRating] = useState(5);
    const [submittingReview, setSubmittingReview] = useState(false);

    usePageTitle('Course Detail', 'Explore course content, enroll, and start learning.');

    const fetchCourse = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await courseService.getCourse(id);
            setActiveCourse(data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load course details.'));
        } finally {
            setLoading(false);
        }
    }, [id, setActiveCourse]);

    const fetchEnrollmentStatus = useCallback(async () => {
        try {
            const { data } = await courseService.listEnrollments({ course: id });
            const list = data.results || data;
            if (list.length > 0) {
                setIsEnrolled(true);
                setEnrollmentId(list[0].id);
            }
        } catch { /* not enrolled */ }
    }, [id]);

    const fetchReviews = useCallback(async () => {
        try {
            const { data } = await courseService.listReviews(id);
            setReviews(data.results || data);
        } catch { /* silent */ }
    }, [id, setReviews]);

    useEffect(() => {
        fetchCourse();
        fetchEnrollmentStatus();
        fetchReviews();
    }, [fetchCourse, fetchEnrollmentStatus, fetchReviews]);

    const handleEnroll = async () => {
        setEnrolling(true);
        try {
            await courseService.createEnrollment({ course: id });
            setIsEnrolled(true);
            fetchEnrollmentStatus();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Enrollment failed.'));
        } finally {
            setEnrolling(false);
        }
    };

    const handleDrop = async () => {
        if (!enrollmentId || !window.confirm('Drop this course?')) return;
        try {
            await courseService.dropEnrollment(enrollmentId);
            setIsEnrolled(false);
            setEnrollmentId(null);
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to drop course.'));
        }
    };

    const handleSubmitReview = async (e) => {
        e.preventDefault();
        if (!reviewText.trim()) return;
        setSubmittingReview(true);
        try {
            await courseService.createReview(id, { rating: reviewRating, comment: reviewText });
            setReviewText('');
            setReviewRating(5);
            fetchReviews();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Could not submit review.'));
        } finally {
            setSubmittingReview(false);
        }
    };

    const course = activeCourse;
    const modules = course?.modules || course?.curriculum || [];

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Course" pageTitleLine2="Detail">
                <div className="cd-skeleton-wrap">
                    <Skeleton style={{ width: '100%', height: '260px', borderRadius: '12px', marginBottom: '24px' }} />
                    <Skeleton style={{ width: '60%', height: '32px', marginBottom: '12px' }} />
                    <Skeleton style={{ width: '100%', height: '120px' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Course" pageTitleLine2="Detail">
                <div className="cd-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Course Detail',
                status: isEnrolled ? 'Enrolled' : 'Not Enrolled',
                info: `Course #${id}`,
            }}
            pageTitleLine1={course?.title?.split(' ').slice(0, 2).join(' ') || 'Course'}
            pageTitleLine2={course?.title?.split(' ').slice(2).join(' ') || 'Detail'}
            headerRightContent={
                <div className="cd-header-actions">
                    {!isEnrolled ? (
                        <button className="cd-enroll-btn" onClick={handleEnroll} disabled={enrolling}>
                            {enrolling ? 'Enrolling…' : 'Enroll Now'}
                        </button>
                    ) : (
                        <div className="cd-enrolled-actions">
                            <button className="cd-continue-btn" onClick={() => navigate(`/courses/${id}/progress`)}>
                                Continue Learning
                            </button>
                            <button className="cd-drop-btn" onClick={handleDrop}>
                                Drop Course
                            </button>
                        </div>
                    )}
                </div>
            }
        >
            <div className="cd-layout">
                {/* Hero / Overview */}
                <section className="cd-hero">
                    <img
                        src={course?.thumbnail || 'https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=800'}
                        alt={course?.title}
                        className="cd-hero__img"
                    />
                    <div className="cd-hero__overlay">
                        <span className="cd-hero__level">{course?.level || 'Beginner'}</span>
                        <span className="cd-hero__access">{course?.access_level === 'free' ? 'Free' : 'Premium'}</span>
                    </div>
                </section>

                <section className="cd-info-grid">
                    <div className="cd-info-block">
                        <h4>Instructor</h4>
                        <p>{course?.instructor_name || course?.instructor?.name || 'TBA'}</p>
                    </div>
                    <div className="cd-info-block">
                        <h4>Duration</h4>
                        <p>{course?.estimated_duration || '—'}</p>
                    </div>
                    <div className="cd-info-block">
                        <h4>Enrolled</h4>
                        <p>{course?.enrollment_count ?? 0}</p>
                    </div>
                    <div className="cd-info-block">
                        <h4>Rating</h4>
                        <p><StarRating value={course?.average_rating || 0} /> ({course?.review_count ?? 0})</p>
                    </div>
                </section>

                <section className="cd-description">
                    <h3 className="cd-section-title">About this Course</h3>
                    <p>{course?.description || 'No description provided.'}</p>
                    {course?.learning_outcomes && (
                        <div className="cd-outcomes">
                            <h4>Learning Outcomes</h4>
                            <ul>
                                {(Array.isArray(course.learning_outcomes) ? course.learning_outcomes : []).map((item, i) => (
                                    <li key={i}>{item}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {course?.prerequisites && (
                        <div className="cd-prereqs">
                            <h4>Prerequisites</h4>
                            <p>{course.prerequisites}</p>
                        </div>
                    )}
                </section>

                {/* Curriculum */}
                <section className="cd-curriculum">
                    <h3 className="cd-section-title">Curriculum</h3>
                    {modules.length > 0 ? modules.map((mod, mi) => (
                        <div key={mod.id || mi} className="cd-module">
                            <button
                                className="cd-module__header"
                                onClick={() => setExpandedModule(expandedModule === mi ? null : mi)}
                            >
                                <span className="cd-module__num">{String(mi + 1).padStart(2, '0')}</span>
                                <span className="cd-module__title">{mod.title}</span>
                                <span className="cd-module__toggle">
                                    {expandedModule === mi ? '−' : '+'}
                                </span>
                            </button>
                            {expandedModule === mi && (
                                <ul className="cd-lessons-list">
                                    {(mod.lessons || []).map((lesson, li) => (
                                        <li key={lesson.id || li} className="cd-lesson-item">
                                            <span className="cd-lesson-item__num">{String(li + 1).padStart(2, '0')}</span>
                                            <span className="cd-lesson-item__title">{lesson.title}</span>
                                            <span className="cd-lesson-item__type">{lesson.content_type || 'video'}</span>
                                            {isEnrolled && (
                                                <Link to={`/courses/${id}/lessons/${lesson.id}`} className="cd-lesson-item__play">
                                                    ▶
                                                </Link>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )) : (
                        <p className="cd-empty-modules">Curriculum details coming soon.</p>
                    )}
                </section>

                {/* Reviews */}
                <section className="cd-reviews">
                    <h3 className="cd-section-title">Reviews</h3>
                    {reviews.length > 0 ? reviews.map((rev) => (
                        <div key={rev.id} className="cd-review-card">
                            <div className="cd-review-card__header">
                                <strong>{rev.user_name || rev.user?.name || 'Anonymous'}</strong>
                                <StarRating value={rev.rating} size={14} />
                            </div>
                            <p>{rev.comment}</p>
                        </div>
                    )) : (
                        <p className="cd-empty-reviews">No reviews yet.</p>
                    )}

                    {isEnrolled && (
                        <form className="cd-review-form" onSubmit={handleSubmitReview}>
                            <h4>Leave a Review</h4>
                            <div className="cd-review-form__rating">
                                {[1, 2, 3, 4, 5].map((s) => (
                                    <span
                                        key={s}
                                        className={`cd-review-star ${s <= reviewRating ? 'active' : ''}`}
                                        onClick={() => setReviewRating(s)}
                                    >
                                        ★
                                    </span>
                                ))}
                            </div>
                            <textarea
                                value={reviewText}
                                onChange={(e) => setReviewText(e.target.value)}
                                placeholder="Share your experience..."
                                rows={4}
                            />
                            <button type="submit" disabled={submittingReview}>
                                {submittingReview ? 'Submitting…' : 'Submit Review'}
                            </button>
                        </form>
                    )}
                </section>
            </div>
        </DashboardLayout>
    );
};

export default CourseDetail;
