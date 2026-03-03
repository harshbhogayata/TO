import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
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
                {assessment.difficulty || 'Medium'}
            </span>
            <span className="ac-card__type">{assessment.assessment_type || 'Skill Test'}</span>
        </div>
        <h3 className="ac-card__title">{assessment.title}</h3>
        <p className="ac-card__desc">{assessment.description?.slice(0, 120)}{assessment.description?.length > 120 ? '…' : ''}</p>
        <div className="ac-card__meta">
            <span>⏱ {assessment.time_limit_minutes || assessment.duration || '—'} min</span>
            <span>❓ {assessment.question_count || assessment.total_questions || '—'} questions</span>
        </div>
        <div className="ac-card__tags">
            {(assessment.skills || assessment.tags || []).slice(0, 3).map((tag, i) => (
                <span key={i} className="ac-card__tag">{typeof tag === 'string' ? tag : tag.name}</span>
            ))}
        </div>
        <button className="ac-card__btn" onClick={() => onView(assessment.id)}>
            View Details
        </button>
    </div>
);

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
            if (filters.type) params.assessment_type = filters.type;
            if (filters.skill) params.skill = filters.skill;
            if (filters.sort) params.ordering = filters.sort;
            const { data } = await assessmentService.listAssessments(params);
            setAssessments(data.results || data);
            setTotalCount(data.count ?? (data.results || data).length);
        } catch (err) {
            setAssessmentsError(getApiErrorMessage(err, 'Failed to load assessments.'));
        } finally {
            setAssessmentsLoading(false);
        }
    }, [filters, setAssessments, setAssessmentsLoading, setAssessmentsError]);

    useEffect(() => {
        const t = setTimeout(fetchAssessments, 300);
        return () => clearTimeout(t);
    }, [fetchAssessments]);

    const handleView = (id) => navigate(`/assessments/${id}`);

    const difficultyOptions = ['easy', 'medium', 'hard', 'expert'];
    const typeOptions = ['skill_test', 'certification', 'practice', 'interview'];
    const sortOptions = [
        { value: '-created_at', label: 'Newest' },
        { value: '-popularity', label: 'Popular' },
        { value: 'difficulty', label: 'Difficulty' },
    ];

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
                        {sortOptions.map((opt) => (
                            <label key={opt.value} className="ac-filter-option">
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

                    <div className="ac-filter-group">
                        <h4 className="ac-filter-title">Difficulty</h4>
                        {difficultyOptions.map((d) => (
                            <label key={d} className="ac-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.difficulty === d}
                                    onChange={() => setFilter('difficulty', filters.difficulty === d ? '' : d)}
                                />
                                {d.charAt(0).toUpperCase() + d.slice(1)}
                            </label>
                        ))}
                    </div>

                    <div className="ac-filter-group">
                        <h4 className="ac-filter-title">Type</h4>
                        {typeOptions.map((t) => (
                            <label key={t} className="ac-filter-option">
                                <input
                                    type="checkbox"
                                    checked={filters.type === t}
                                    onChange={() => setFilter('type', filters.type === t ? '' : t)}
                                />
                                {t.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
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
                            onChange={(e) => setFilter('search', e.target.value)}
                        />
                        <span className="ac-results-count">
                            {assessments.length} of {totalCount} results
                        </span>
                    </div>

                    {assessmentsError && <div className="ac-error-banner">{assessmentsError}</div>}

                    {assessmentsLoading ? (
                        <div className="ac-grid">
                            {Array.from({ length: 6 }).map((_, i) => (
                                <div key={i} className="ac-card">
                                    <Skeleton style={{ width: '100%', height: '180px' }} />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="ac-grid">
                            {assessments.map((a) => (
                                <AssessmentCard key={a.id} assessment={a} onView={handleView} />
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
