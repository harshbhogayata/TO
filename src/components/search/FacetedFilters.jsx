/**
 * src/components/search/FacetedFilters.jsx
 * Sidebar filters for search results — job type, work mode, salary range,
 * experience level, skills, and location. Brutalist design.
 */
import { useState, useCallback } from 'react';
import { useSearchStore } from '../../store/searchStore';
import './Search.css';

const JOB_TYPES = [
    { value: 'full_time', label: 'Full-Time' },
    { value: 'part_time', label: 'Part-Time' },
    { value: 'contract', label: 'Contract' },
    { value: 'freelance', label: 'Freelance' },
];

const WORK_MODES = [
    { value: 'remote', label: 'Remote' },
    { value: 'on_site', label: 'On-Site' },
    { value: 'hybrid', label: 'Hybrid' },
];

const EXPERIENCE_LEVELS = [
    { value: 'junior', label: 'Junior (1-2y)' },
    { value: 'mid', label: 'Mid-Level (3-5y)' },
    { value: 'senior', label: 'Senior (5-8y)' },
    { value: 'lead', label: 'Lead / Director (8+y)' },
];

const SORT_OPTIONS = [
    { value: 'relevance', label: 'Relevance' },
    { value: 'date', label: 'Newest First' },
    { value: 'salary', label: 'Highest Salary' },
];

const FacetedFilters = ({ entityType = 'jobs' }) => {
    const { filters, updateFilter, removeFilter, clearFilters, sort, setSort } = useSearchStore();

    const [salaryMin, setSalaryMin] = useState(filters.salary_min || '');
    const [salaryMax, setSalaryMax] = useState(filters.salary_max || '');
    const [skillInput, setSkillInput] = useState('');

    const handleCheckboxFilter = useCallback((key, value) => {
        const current = (filters[key] || '').split(',').filter(Boolean);
        const idx = current.indexOf(value);

        if (idx >= 0) {
            current.splice(idx, 1);
        } else {
            current.push(value);
        }

        if (current.length === 0) {
            removeFilter(key);
        } else {
            updateFilter(key, current.join(','));
        }
    }, [filters, updateFilter, removeFilter]);

    const isChecked = (key, value) => {
        return (filters[key] || '').split(',').includes(value);
    };

    const handleSalaryApply = () => {
        if (salaryMin) updateFilter('salary_min', salaryMin);
        else removeFilter('salary_min');
        if (salaryMax) updateFilter('salary_max', salaryMax);
        else removeFilter('salary_max');
    };

    const handleAddSkill = () => {
        const skill = skillInput.trim();
        if (!skill) return;
        const current = (filters.skills || '').split(',').filter(Boolean);
        if (!current.includes(skill)) {
            current.push(skill);
            updateFilter('skills', current.join(','));
        }
        setSkillInput('');
    };

    const handleRemoveSkill = (skill) => {
        const current = (filters.skills || '').split(',').filter(Boolean);
        const next = current.filter(s => s !== skill);
        if (next.length === 0) removeFilter('skills');
        else updateFilter('skills', next.join(','));
    };

    const activeSkills = (filters.skills || '').split(',').filter(Boolean);
    const activeFilterCount = Object.keys(filters).length;

    return (
        <aside className="faceted-filters">
            <div className="filter-header">
                <h3 className="filter-title">Filters</h3>
                {activeFilterCount > 0 && (
                    <button className="filter-clear-btn" onClick={clearFilters} type="button">
                        Clear All ({activeFilterCount})
                    </button>
                )}
            </div>

            {/* Sort */}
            <div className="filter-section">
                <h4 className="filter-section-title">Sort By</h4>
                {SORT_OPTIONS.map(opt => (
                    <label key={opt.value} className="filter-radio">
                        <input
                            type="radio"
                            name="sort"
                            checked={sort === opt.value}
                            onChange={() => setSort(opt.value)}
                        />
                        {opt.label}
                    </label>
                ))}
            </div>

            {/* Job Type (jobs only) */}
            {entityType === 'jobs' && (
                <div className="filter-section">
                    <h4 className="filter-section-title">Job Type</h4>
                    {JOB_TYPES.map(opt => (
                        <label key={opt.value} className="filter-checkbox">
                            <input
                                type="checkbox"
                                checked={isChecked('job_type', opt.value)}
                                onChange={() => handleCheckboxFilter('job_type', opt.value)}
                            />
                            {opt.label}
                        </label>
                    ))}
                </div>
            )}

            {/* Work Mode (jobs only) */}
            {entityType === 'jobs' && (
                <div className="filter-section">
                    <h4 className="filter-section-title">Work Mode</h4>
                    {WORK_MODES.map(opt => (
                        <label key={opt.value} className="filter-checkbox">
                            <input
                                type="checkbox"
                                checked={isChecked('work_mode', opt.value)}
                                onChange={() => handleCheckboxFilter('work_mode', opt.value)}
                            />
                            {opt.label}
                        </label>
                    ))}
                </div>
            )}

            {/* Experience Level (jobs only) */}
            {entityType === 'jobs' && (
                <div className="filter-section">
                    <h4 className="filter-section-title">Experience</h4>
                    {EXPERIENCE_LEVELS.map(opt => (
                        <label key={opt.value} className="filter-checkbox">
                            <input
                                type="checkbox"
                                checked={isChecked('experience_level', opt.value)}
                                onChange={() => handleCheckboxFilter('experience_level', opt.value)}
                            />
                            {opt.label}
                        </label>
                    ))}
                </div>
            )}

            {/* Salary Range (jobs only) */}
            {entityType === 'jobs' && (
                <div className="filter-section">
                    <h4 className="filter-section-title">Salary Range</h4>
                    <div className="salary-inputs">
                        <input
                            type="number"
                            className="salary-input"
                            placeholder="Min"
                            value={salaryMin}
                            onChange={(e) => setSalaryMin(e.target.value)}
                            onBlur={handleSalaryApply}
                            min="0"
                        />
                        <span className="salary-separator">—</span>
                        <input
                            type="number"
                            className="salary-input"
                            placeholder="Max"
                            value={salaryMax}
                            onChange={(e) => setSalaryMax(e.target.value)}
                            onBlur={handleSalaryApply}
                            min="0"
                        />
                    </div>
                </div>
            )}

            {/* Skills Filter */}
            {(entityType === 'jobs' || entityType === 'talent') && (
                <div className="filter-section">
                    <h4 className="filter-section-title">Skills</h4>
                    <div className="skill-input-row">
                        <input
                            type="text"
                            className="skill-input"
                            placeholder="Add skill..."
                            value={skillInput}
                            onChange={(e) => setSkillInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleAddSkill();
                                }
                            }}
                        />
                        <button
                            className="skill-add-btn"
                            onClick={handleAddSkill}
                            type="button"
                            disabled={!skillInput.trim()}
                        >
                            +
                        </button>
                    </div>
                    {activeSkills.length > 0 && (
                        <div className="active-skills">
                            {activeSkills.map(skill => (
                                <span key={skill} className="skill-chip">
                                    {skill}
                                    <button
                                        onClick={() => handleRemoveSkill(skill)}
                                        className="skill-remove"
                                        type="button"
                                        aria-label={`Remove ${skill}`}
                                    >
                                        ×
                                    </button>
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Location (all entity types) */}
            <div className="filter-section">
                <h4 className="filter-section-title">Location</h4>
                <input
                    type="text"
                    className="location-input"
                    placeholder="City or region..."
                    value={filters.location || ''}
                    onChange={(e) => {
                        if (e.target.value) updateFilter('location', e.target.value);
                        else removeFilter('location');
                    }}
                />
            </div>
        </aside>
    );
};

export default FacetedFilters;
