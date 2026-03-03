/**
 * src/store/courseStore.js
 * Zustand store for courses / LMS state.
 */
import { create } from 'zustand';

export const useCourseStore = create((set, get) => ({
    // ── Catalog ──────────────────────────────────────────────────────────────
    courses: [],
    coursesLoading: false,
    coursesError: null,
    categories: [],
    filters: {
        search: '',
        category: '',
        level: '',
        access: '',
        sort: '-popularity',
    },

    setCourses: (courses) => set({ courses }),
    setCoursesLoading: (loading) => set({ coursesLoading: loading }),
    setCoursesError: (error) => set({ coursesError: error }),
    setCategories: (categories) => set({ categories }),
    setFilter: (key, value) =>
        set((state) => ({ filters: { ...state.filters, [key]: value } })),
    resetFilters: () =>
        set({
            filters: { search: '', category: '', level: '', access: '', sort: '-popularity' },
        }),

    // ── Active course / detail ───────────────────────────────────────────────
    activeCourse: null,
    setActiveCourse: (course) => set({ activeCourse: course }),

    // ── Enrollments ──────────────────────────────────────────────────────────
    enrollments: [],
    enrollmentsLoading: false,
    setEnrollments: (enrollments) => set({ enrollments }),
    setEnrollmentsLoading: (loading) => set({ enrollmentsLoading: loading }),
    addEnrollment: (enrollment) =>
        set((state) => ({ enrollments: [enrollment, ...state.enrollments] })),
    removeEnrollment: (id) =>
        set((state) => ({
            enrollments: state.enrollments.filter((e) => e.id !== id),
        })),

    // ── Lesson player ────────────────────────────────────────────────────────
    activeLesson: null,
    lessonProgress: {},
    setActiveLesson: (lesson) => set({ activeLesson: lesson }),
    updateLessonProgress: (lessonId, data) =>
        set((state) => ({
            lessonProgress: { ...state.lessonProgress, [lessonId]: data },
        })),

    // ── Course progress ──────────────────────────────────────────────────────
    courseProgress: null,
    setCourseProgress: (progress) => set({ courseProgress: progress }),

    // ── Certificates ─────────────────────────────────────────────────────────
    certificates: [],
    setCertificates: (certificates) => set({ certificates }),

    // ── Reviews ──────────────────────────────────────────────────────────────
    reviews: [],
    setReviews: (reviews) => set({ reviews }),
    addReview: (review) =>
        set((state) => ({ reviews: [review, ...state.reviews] })),
}));
