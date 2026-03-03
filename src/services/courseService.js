/**
 * src/services/courseService.js
 * API service for the Courses / LMS module.
 * Maps to backend endpoints under /api/v1/courses/
 */
import api from './api';

const courseService = {
    // ── Catalog ──────────────────────────────────────────────────────────────
    listCourses: (params) => api.get('/courses/', { params }),
    getCourse: (id) => api.get(`/courses/${id}/`),

    // ── Categories & Instructors ─────────────────────────────────────────────
    listCategories: () => api.get('/courses/categories/'),
    getCategory: (id) => api.get(`/courses/categories/${id}/`),
    listInstructors: () => api.get('/courses/instructors/'),
    getInstructor: (id) => api.get(`/courses/instructors/${id}/`),

    // ── Enrollments ──────────────────────────────────────────────────────────
    listEnrollments: (params) => api.get('/courses/enrollments/', { params }),
    createEnrollment: (courseId) => api.post('/courses/enrollments/create/', { course: courseId }),
    getEnrollment: (id) => api.get(`/courses/enrollments/${id}/`),
    dropEnrollment: (id) => api.post(`/courses/enrollments/${id}/drop/`),

    // ── Lessons & Progress ───────────────────────────────────────────────────
    getLesson: (courseId, lessonId) =>
        api.get(`/courses/${courseId}/lessons/${lessonId}/`),
    updateLessonProgress: (courseId, lessonId, data) =>
        api.post(`/courses/${courseId}/lessons/${lessonId}/progress/`, data),
    getCourseProgress: (courseId) =>
        api.get(`/courses/${courseId}/progress/`),

    // ── Reviews ──────────────────────────────────────────────────────────────
    listReviews: (courseId, params) =>
        api.get(`/courses/${courseId}/reviews/`, { params }),
    createReview: (courseId, data) =>
        api.post(`/courses/${courseId}/reviews/create/`, data),
    voteReview: (reviewId, vote) =>
        api.post(`/courses/reviews/${reviewId}/vote/`, { vote }),

    // ── Certificates ─────────────────────────────────────────────────────────
    myCertificates: () => api.get('/courses/certificates/'),
    verifyCertificate: (uuid) => api.get(`/courses/certificates/${uuid}/verify/`),
};

export default courseService;
