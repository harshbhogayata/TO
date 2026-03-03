import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { useCourseStore } from '../store/courseStore';
import { getApiErrorMessage } from '../services/api';
import { useNavigate } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CourseCatalog.css';

const CourseCard = ({ course, onView }) => {
    const [hovered, setHovered] = useState(false);
    return (
        <div className="cc-card">
            <img
                src={course.thumbnail || 'https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=800&auto=format&fit=crop'}
                className="cc-card__thumb"
                alt={course.title}
                loading="lazy"
            />
            <div className="cc-card__body">
                <span className="cc-card__level">{course.level || 'Beginner'}</span>
                <h3 className="cc-card__title">{course.title}</h3>
                <p className="cc-card__instructor">
                    Instructor: {course.instructor_name || course.instructor?.name || 'TBA'}
                </p>
                <div className="cc-card__meta-bottom">
                    <span className="cc-card__rating">
                        {course.average_rating ? `${course.average_rating} ★` : '— ★'}
                    </span>
                    <span className="cc-card__enrolled">
                        {course.enrollment_count ?? 0} Enrolled
                    </span>
                </div>
            </div>
            <div className="cc-card__footer">
                <span>{course.estimated_duration || '—'}</span>
                <span>{course.access_level === 'free' ? 'Free' : 'Premium'}</span>
            </div>
            <button
                className="cc-card__btn"
                style={{ opacity: hovered ? 0.85 : 1 }}
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
                onClick={() => onView(course.id)}
            >
                View Course
            </button>
        </div>
    );
};

const CourseCatalog = () => {
    const navigate = useNavigate();
    const {
        courses, coursesLoading, coursesError, categories, filters,
        setCourses, setCoursesLoading, setCoursesError, setCategories, setFilter,
    } = useCourseStore();

    const [totalCount, setTotalCount] = useState(0);
    usePageTitle('Course Catalog', 'Browse all available courses. Filter by category, level, and access type.');

    const fetchCourses = useCallback(async () => {
        setCoursesLoading(true);
        setCoursesError(null);
        try {
            const params = {};
            if (filters.search) params.search = filters.search;
            if (filters.category) params.category = filters.category;
            if (filters.level) params.level = filters.level;
            if (filters.access) params.access_level = filters.access;
            if (filters.sort) params.ordering = filters.sort;
            const { data } = await courseService.listCourses(params);
            setCourses(data.results || data);
            setTotalCount(data.count ?? (data.results || data).length);
        } catch (err) {
            setCoursesError(getApiErrorMessage(err, 'Failed to load courses.'));
        } finally {
            setCoursesLoading(false);
        }
    }, [filters, setCourses, setCoursesLoading, setCoursesError]);

    const fetchCategories = useCallback(async () => {
        try {
            const { data } = await courseService.listCategories();
            setCategories(data.results || data);
        } catch { /* silent */ }
    }, [setCategories]);

    useEffect(() => {
        fetchCategories();
    }, [fetchCategories]);

    useEffect(() => {
        const t = setTimeout(fetchCourses, 300);
        return () => clearTimeout(t);
    }, [fetchCourses]);

    const handleView = (id) => navigate(`/courses/${id}`);

    const sortOptions = [
        { value: '-popularity', label: 'Popularity' },
        { value: '-created_at', label: 'Newest' },
        { value: '-average_rating', label: 'Rating' },
    ];

    const levelOptions = ['beginner', 'intermediate', 'advanced'];
    const accessOptions = ['free', 'premium', 'subscription'];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Learning Platform',
                status: 'System Status: Operational',
                info: 'Library Index: Syncing',
            }}
            pageTitleLine1="Course"
            pageTitleLine2="Catalog"
            headerRightContent={
                <div className="cc-header-stats">
                    <div className="cc-stat-block">
                        <h3 className="cc-stat-label">Total Courses</h3>
                        <p className="cc-stat-value">{totalCount} Published</p>
                    </div>
                </div>
            }
        >
            <div className="cc-catalog-layout">
                {/* Filters sidebar */}
                <aside className="cc-filters-panel">
                    <div className="cc-filter-group">
                        <h4 className="cc-filter-title">Sort By</h4>
                        {sortOptions.map((opt) => (
                            <label key={opt.value} className="cc-filter-option">
                                <input
                                    type="radio"
                                    name="sort"
                                    checked={filters.sort === opt.value}
                                    onChange={() => setFilter('sort', opt.value)}
                                />
                                {opt.label}
                            </label>
                        ))}
                    </div>

                    {categories.length > 0 && (
                        <div className="cc-filter-group">
                            <h4 className="cc-filter-title">Category</h4>
                            <label className="cc-filter-option">
                                <input
                                    type="radio"
                                    name="category"
                                    checked={!filters.category}
                                    onChange={() => setFilter('category', '')}
                                />
                                All
                            </label>
                            {categories.map((cat) => (
                                <label key={cat.id} className="cc-filter-option">
                                    <input
                                        type="radio"
                                        name="category"
                                        checked={filters.category === String(cat.id)}
                                        onChange={() => setFilter('category', String(cat.id))}
                                    />
                                    {cat.name}
                                </label>
                            ))}
                        </div>
                    )}

                    <div className="cc-filter-group">
                        <h4 className="cc-filter-title">Level</h4>
                        <label className="cc-filter-option">
                            <input
                                type="checkbox"
                                checked={!filters.level}
                                onChange={() => setFilter('level', '')}
                            />
                            All
                        </label>
                        {levelOptions.map((lvl) => (
                            <label key={lvl} className="cc-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.level === lvl}
                                    onChange={() => setFilter('level', filters.level === lvl ? '' : lvl)}
                                />
                                {lvl.charAt(0).toUpperCase() + lvl.slice(1)}
                            </label>
                        ))}
                    </div>

                    <div className="cc-filter-group">
                        <h4 className="cc-filter-title">Access</h4>
                        {accessOptions.map((acc) => (
                            <label key={acc} className="cc-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.access === acc}
                                    onChange={() => setFilter('access', filters.access === acc ? '' : acc)}
                                />
                                {acc.charAt(0).toUpperCase() + acc.slice(1)}
                            </label>
                        ))}
                    </div>
                </aside>

                {/* Main content */}
                <div className="cc-catalog-content">
                    <div className="cc-search-strip">
                        <div className="cc-search-wrapper">
                            <input
                                type="text"
                                className="cc-search-input"
                                placeholder="Search courses, instructors, keywords..."
                                value={filters.search}
                                onChange={(e) => setFilter('search', e.target.value)}
                            />
                        </div>
                        <span className="cc-results-count">
                            Showing {courses.length} of {totalCount} results
                        </span>
                    </div>

                    {coursesError && (
                        <div className="cc-error-banner">{coursesError}</div>
                    )}

                    {coursesLoading ? (
                        <div className="cc-grid">
                            {Array.from({ length: 6 }).map((_, i) => (
                                <div key={i} className="cc-card">
                                    <Skeleton style={{ width: '100%', aspectRatio: '16/9' }} />
                                    <div className="cc-card__body">
                                        <Skeleton style={{ width: '60px', height: '16px', marginBottom: '12px' }} />
                                        <Skeleton style={{ width: '100%', height: '22px', marginBottom: '8px' }} />
                                        <Skeleton style={{ width: '140px', height: '14px' }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="cc-grid">
                            {courses.map((course) => (
                                <CourseCard key={course.id} course={course} onView={handleView} />
                            ))}
                            {courses.length === 0 && !coursesError && (
                                <p className="cc-empty">No courses match your filters.</p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CourseCatalog;
