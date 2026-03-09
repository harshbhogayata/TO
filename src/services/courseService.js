/**
 * src/services/courseService.js
 * API service for the Courses / LMS module.
 * Maps to backend endpoints under /api/v1/courses/
 */
import api from './api';

const resolveCourseId = (course) =>
    course?.course_id
    ?? course?.id
    ?? course?.course
    ?? course;

const courseService = {
    listCourses: (params) => api.get('/courses/', { params }),
    getCourse: (slug) => api.get(`/courses/${slug}/`),

    listCategories: () => api.get('/courses/categories/'),
    getCategory: (slug) => api.get(`/courses/categories/${slug}/`),
    listInstructors: () => api.get('/courses/instructors/'),
    getInstructor: (slug) => api.get(`/courses/instructors/${slug}/`),

    listEnrollments: (params) => api.get('/courses/enrollments/', { params }),
    createEnrollment: (course) => api.post('/courses/enrollments/create/', { course_id: resolveCourseId(course) }),
    getEnrollment: (id) => api.get(`/courses/enrollments/${id}/`),
    dropEnrollment: (id) => api.post(`/courses/enrollments/${id}/drop/`),

    getLesson: (courseSlug, lessonSlug) =>
        api.get(`/courses/${courseSlug}/lessons/${lessonSlug}/`),
    updateLessonProgress: (courseSlug, lessonSlug, data) =>
        api.post(`/courses/${courseSlug}/lessons/${lessonSlug}/progress/`, data),
    getCourseProgress: (courseSlug) =>
        api.get(`/courses/${courseSlug}/progress/`),

    listReviews: (courseSlug, params) =>
        api.get(`/courses/${courseSlug}/reviews/`, { params }),
    createReview: (courseSlug, data) =>
        api.post(`/courses/${courseSlug}/reviews/create/`, data),
    voteReview: (reviewId, helpful) =>
        api.post(`/courses/reviews/${reviewId}/vote/`, { helpful }),

    myCertificates: () => api.get('/courses/certificates/'),
    verifyCertificate: (certificateId) => api.get(`/courses/certificates/verify/${certificateId}/`),
};

export default courseService;
