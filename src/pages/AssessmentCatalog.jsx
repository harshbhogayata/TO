import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { normaliseAssessmentListItem } from '../utils/learningContracts';
import './AssessmentCatalog.css';

const difficultyColors = {
    easy: '#4CAF50',
    medium: '#FF9800',
    hard: '#F44336',
    expert: '#9C27B0',
};

const AssessmentCard = ({ assessment, onView }) => (
    <div className="ac-card">
        <div className="ac-card__header">
            <span
                className="ac-card__difficulty"
                style={{ backgroundColor: difficultyColors[assessment.difficulty] || '#888' }}
            >
                {assessment.difficulty || 'medium'}
            </span>
            <span className="ac-card__type">{assessment.assessment_type || 'skill_test'}</span>
        </div>
        <h3 className="ac-card__title">{assessment.title}</h3>
        <p className="ac-card__desc">{assessment.description?.slice(0, 120)}{assessment.description?.length > 120 ? '...' : ''}</p>
        <div className="ac-card__meta">
            <span>Time {assessment.time_limit_minutes || '-'} min</span>
            <span>{assessment.question_count || '-'} questions</span>
        </div>
        <div className="ac-card__tags">
            {assessment.skills.slice(0, 3).map((tag) => (
                <span key={tag} className="ac-card__tag">{tag}</span>
            ))}
        </div>
        <button className="ac-card__btn" onClick={() => onView(assessment.id)}>
            View Details
        </button>
    </div>
);

const difficultyOptions = [
    { value: '2', label: 'Easy' },
    { value: '3', label: 'Medium' },
    { value: '4', label: 'Hard' },
    { value: '5', label: 'Expert' },
];

const typeOptions = ['skill_test', 'certification', 'practice', 'interview'];
const sortOptions = [
    { value: 'newest', label: 'Newest' },
    { value: 'popular', label: 'Popular' },
    { value: 'pass_rate', label: 'Pass Rate' },
];

const AssessmentCatalog = () => {
    const navigate = useNavigate();
    const {
        assessments, assessmentsLoading, assessmentsError, filters,
        setAssessments, setAssessmentsLoading, setAssessmentsError, setFilter,
    } = useAssessmentStore();
    const [totalCount, setTotalCount] = useState(0);

    usePageTitle('Assessment Catalog', 'Browse skill assessments and certifications.');

    const fetchAssessments = useCallback(async () => {
        setAssessmentsLoading(true);
        setAssessmentsError(null);
        try {
            const params = {};
            if (filters.search) params.search = filters.search;
            if (filters.difficulty) params.difficulty = filters.difficulty;
            if (filters.type) params.type = filters.type;
            if (filters.skill) params.skill = filters.skill;
            if (filters.sort) params.ordering = filters.sort;
            const { data } = await assessmentService.listAssessments(params);
            const items = (data.results || data).map(normaliseAssessmentListItem);
            setAssessments(items);
            setTotalCount(data.count ?? items.length);
        } catch (err) {
            setAssessmentsError(getApiErrorMessage(err, 'Failed to load assessments.'));
        } finally {
            setAssessmentsLoading(false);
        }
    }, [filters, setAssessments, setAssessmentsLoading, setAssessmentsError]);

    useEffect(() => {
        const timeoutId = setTimeout(fetchAssessments, 300);
        return () => clearTimeout(timeoutId);
    }, [fetchAssessments]);

    const handleView = (id) => navigate(`/assessments/${id}`);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Assessment Engine',
                status: 'System Status: Operational',
                info: 'Assessment Library: Active',
            }}
            pageTitleLine1="Assessment"
            pageTitleLine2="Catalog"
            headerRightContent={
                <div className="ac-header-stats">
                    <div className="ac-stat-block">
                        <h3 className="ac-stat-label">Available</h3>
                        <p className="ac-stat-value">{totalCount} Assessments</p>
                    </div>
                </div>
            }
        >
            <div className="ac-catalog-layout">
                <aside className="ac-filters-panel">
                    <div className="ac-filter-group">
                        <h4 className="ac-filter-title">Sort By</h4>
                        {sortOptions.map((option) => (
                            <label key={option.value} className="ac-filter-option">
                                <input
                                    type="radio"
                                    name="sort"
                                    checked={filters.sort === option.value}
                                    onChange={() => setFilter('sort', option.value)}
                                />
                                {option.label}
                            </label>
                        ))}
                    </div>

                    <div className="ac-filter-group">
                        <h4 className="ac-filter-title">Difficulty</h4>
                        {difficultyOptions.map((difficulty) => (
                            <label key={difficulty.value} className="ac-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.difficulty === difficulty.value}
                                    onChange={() => setFilter('difficulty', filters.difficulty === difficulty.value ? '' : difficulty.value)}
                                />
                                {difficulty.label}
                            </label>
                        ))}
                    </div>

                    <div className="ac-filter-group">
                        <h4 className="ac-filter-title">Type</h4>
                        {typeOptions.map((type) => (
                            <label key={type} className="ac-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.type === type}
                                    onChange={() => setFilter('type', filters.type === type ? '' : type)}
                                />
                                {type.replace('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())}
                            </label>
                        ))}
                    </div>
                </aside>

                <div className="ac-catalog-content">
                    <div className="ac-search-strip">
                        <input
                            type="text"
                            className="ac-search-input"
                            placeholder="Search assessments, skills, topics..."
                            value={filters.search}
                            onChange={(event) => setFilter('search', event.target.value)}
                        />
                        <span className="ac-results-count">
                            {assessments.length} of {totalCount} results
                        </span>
                    </div>

                    {assessmentsError && <div className="ac-error-banner">{assessmentsError}</div>}

                    {assessmentsLoading ? (
                        <div className="ac-grid">
                            {Array.from({ length: 6 }).map((_, index) => (
                                <div key={index} className="ac-card">
                                    <Skeleton style={{ width: '100%', height: '180px' }} />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="ac-grid">
                            {assessments.map((assessment) => (
                                <AssessmentCard key={assessment.id} assessment={assessment} onView={handleView} />
                            ))}
                            {assessments.length === 0 && !assessmentsError && (
                                <p className="ac-empty">No assessments match your filters.</p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default AssessmentCatalog;
