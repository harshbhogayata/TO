import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { getCourseProgressRoute, getLessonRoute, normaliseCourseDetail } from '../utils/learningContracts';
import './CourseDetail.css';

const StarRating = ({ value = 0, size = 18 }) => (
    <span className="cd-star-row">
        {[1, 2, 3, 4, 5].map((star) => (
            <span
                key={star}
                style={{ fontSize: size, color: star <= Math.round(value) ? '#FFD700' : '#555' }}
            >
                *
            </span>
        ))}
    </span>
);

const CourseDetail = () => {
    const { id: courseSlug } = useParams();
    const navigate = useNavigate();
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
            const { data } = await courseService.getCourse(courseSlug);
            const normalisedCourse = normaliseCourseDetail(data);
            setActiveCourse(normalisedCourse);
            setIsEnrolled(normalisedCourse.is_enrolled);
            setEnrollmentId(normalisedCourse.enrollment?.id ?? null);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load course details.'));
        } finally {
            setLoading(false);
        }
    }, [courseSlug, setActiveCourse]);

    const fetchReviews = useCallback(async () => {
        try {
            const { data } = await courseService.listReviews(courseSlug);
            setReviews(data.results || data);
        } catch {
            setReviews([]);
        }
    }, [courseSlug, setReviews]);

    useEffect(() => {
        fetchCourse();
        fetchReviews();
    }, [fetchCourse, fetchReviews]);

    const handleEnroll = async () => {
        const course = activeCourse;
        if (!course?.id) {
            return;
        }

        setEnrolling(true);
        try {
            const { data } = await courseService.createEnrollment(course.id);
            setIsEnrolled(true);
            setEnrollmentId(data.id ?? null);
            setActiveCourse({
                ...course,
                is_enrolled: true,
                enrollment: data,
            });
        } catch (err) {
            window.alert(getApiErrorMessage(err, 'Enrollment failed.'));
        } finally {
            setEnrolling(false);
        }
    };

    const handleDrop = async () => {
        if (!enrollmentId || !window.confirm('Drop this course?')) {
            return;
        }

        try {
            await courseService.dropEnrollment(enrollmentId);
            setIsEnrolled(false);
            setEnrollmentId(null);
            setActiveCourse(activeCourse ? { ...activeCourse, is_enrolled: false, enrollment: null } : activeCourse);
        } catch (err) {
            window.alert(getApiErrorMessage(err, 'Failed to drop course.'));
        }
    };

    const handleSubmitReview = async (event) => {
        event.preventDefault();
        if (!reviewText.trim() || !activeCourse?.id) {
            return;
        }

        setSubmittingReview(true);
        try {
            await courseService.createReview(courseSlug, {
                course: activeCourse.id,
                rating: reviewRating,
                title: reviewText.trim().slice(0, 80),
                content: reviewText.trim(),
            });
            setReviewText('');
            setReviewRating(5);
            fetchReviews();
        } catch (err) {
            window.alert(getApiErrorMessage(err, 'Could not submit review.'));
        } finally {
            setSubmittingReview(false);
        }
    };

    const course = activeCourse;
    const modules = course?.modules || [];

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
                info: course?.slug ? `Course: ${course.slug}` : `Course: ${courseSlug}`,
            }}
            pageTitleLine1={course?.title?.split(' ').slice(0, 2).join(' ') || 'Course'}
            pageTitleLine2={course?.title?.split(' ').slice(2).join(' ') || 'Detail'}
            headerRightContent={
                <div className="cd-header-actions">
                    {!isEnrolled ? (
                        <button className="cd-enroll-btn" onClick={handleEnroll} disabled={enrolling}>
                            {enrolling ? 'Enrolling...' : 'Enroll Now'}
                        </button>
                    ) : (
                        <div className="cd-enrolled-actions">
                            <button className="cd-continue-btn" onClick={() => navigate(getCourseProgressRoute(course))}>
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
                        <p>{course?.instructor_name || 'TBA'}</p>
                    </div>
                    <div className="cd-info-block">
                        <h4>Duration</h4>
                        <p>{course?.estimated_duration || '-'}</p>
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
                                {(Array.isArray(course.learning_outcomes) ? course.learning_outcomes : []).map((item, index) => (
                                    <li key={index}>{item}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {course?.prerequisites?.length > 0 && (
                        <div className="cd-prereqs">
                            <h4>Prerequisites</h4>
                            <p>{course.prerequisites.map((item) => item.title ?? item).join(', ')}</p>
                        </div>
                    )}
                </section>

                <section className="cd-curriculum">
                    <h3 className="cd-section-title">Curriculum</h3>
                    {modules.length > 0 ? modules.map((module, moduleIndex) => (
                        <div key={module.id || moduleIndex} className="cd-module">
                            <button
                                className="cd-module__header"
                                onClick={() => setExpandedModule(expandedModule === moduleIndex ? null : moduleIndex)}
                            >
                                <span className="cd-module__num">{String(moduleIndex + 1).padStart(2, '0')}</span>
                                <span className="cd-module__title">{module.title}</span>
                                <span className="cd-module__toggle">
                                    {expandedModule === moduleIndex ? '-' : '+'}
                                </span>
                            </button>
                            {expandedModule === moduleIndex && (
                                <ul className="cd-lessons-list">
                                    {(module.lessons || []).map((lesson, lessonIndex) => (
                                        <li key={lesson.id || lessonIndex} className="cd-lesson-item">
                                            <span className="cd-lesson-item__num">{String(lessonIndex + 1).padStart(2, '0')}</span>
                                            <span className="cd-lesson-item__title">{lesson.title}</span>
                                            <span className="cd-lesson-item__type">{lesson.content_type || 'video'}</span>
                                            {isEnrolled && lesson.slug && (
                                                <Link to={getLessonRoute(course, lesson)} className="cd-lesson-item__play">
                                                    Play
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

                <section className="cd-reviews">
                    <h3 className="cd-section-title">Reviews</h3>
                    {reviews.length > 0 ? reviews.map((review) => (
                        <div key={review.id} className="cd-review-card">
                            <div className="cd-review-card__header">
                                <strong>{review.user_name || review.user?.name || 'Anonymous'}</strong>
                                <StarRating value={review.rating} size={14} />
                            </div>
                            <p>{review.content || review.comment}</p>
                        </div>
                    )) : (
                        <p className="cd-empty-reviews">No reviews yet.</p>
                    )}

                    {isEnrolled && (
                        <form className="cd-review-form" onSubmit={handleSubmitReview}>
                            <h4>Leave a Review</h4>
                            <div className="cd-review-form__rating">
                                {[1, 2, 3, 4, 5].map((star) => (
                                    <span
                                        key={star}
                                        className={`cd-review-star ${star <= reviewRating ? 'active' : ''}`}
                                        onClick={() => setReviewRating(star)}
                                    >
                                        *
                                    </span>
                                ))}
                            </div>
                            <textarea
                                value={reviewText}
                                onChange={(event) => setReviewText(event.target.value)}
                                placeholder="Share your experience..."
                                rows={4}
                            />
                            <button type="submit" disabled={submittingReview}>
                                {submittingReview ? 'Submitting...' : 'Submit Review'}
                            </button>
                        </form>
                    )}
                </section>
            </div>
        </DashboardLayout>
    );
};

export default CourseDetail;
