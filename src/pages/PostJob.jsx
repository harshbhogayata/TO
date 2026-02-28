import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { jobsService, getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './PostJob.css';

const PostJob = () => {
    const navigate = useNavigate();
    usePageTitle('Post a Job');
    const [skills, setSkills] = useState([]);
    const [skillInput, setSkillInput] = useState('');

    const [form, setForm] = useState({
        title: '',
        description: '',
        location: '',
        salary: '',
        experience_level: 'mid',
        job_type: 'full_time',
        work_mode: 'remote',
        status: 'open'
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const handleInput = (e) => setForm({ ...form, [e.target.name]: e.target.value });

    const handleAddSkill = (e) => {
        if (e.key === 'Enter' && skillInput.trim() !== '') {
            e.preventDefault();
            if (!skills.includes(skillInput.trim())) {
                setSkills([...skills, skillInput.trim()]);
            }
            setSkillInput('');
        }
    };

    const removeSkill = (skillToRemove) => {
        setSkills(skills.filter(s => s !== skillToRemove));
    };

    const handlePublish = async (isDraft = false) => {
        setError('');
        setIsLoading(true);
        try {
            // Parse salary string e.g. "80k - 110k" -> min: 80000, max: 110000
            let salary_min = null;
            let salary_max = null;
            const numbers = form.salary.match(/\d+/g);
            if (numbers && numbers.length >= 1) {
                salary_min = parseInt(numbers[0]);
                if (salary_min < 1000) salary_min *= 1000;
            }
            if (numbers && numbers.length >= 2) {
                salary_max = parseInt(numbers[1]);
                if (salary_max < 1000) salary_max *= 1000;
            }

            const payload = {
                title: form.title,
                description: form.description,
                location: form.location,
                salary_min,
                salary_max,
                salary_currency: 'USD',
                skills_required: skills,
                experience_level: form.experience_level,
                job_type: form.job_type,
                work_mode: form.work_mode,
                status: isDraft ? 'draft' : 'open'
            };

            await jobsService.createJob(payload);
            navigate('/company');
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to create job posting. Please check all fields and try again.'));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Post Job",
                status: "Create New Listing",
                info: "Terminal: 0x4492"
            }}
            pageTitleLine1="Post"
            pageTitleLine2="A Job"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Status</h3>
                        <p>Drafting Mode</p>
                    </div>
                </div>
            }
        >
            <div className="post-form-grid">
                <div className="form-section">
                    {error && <div style={{ color: 'red', marginBottom: '16px', fontSize: '12px' }}>{error}</div>}

                    <div className="input-group">
                        <label className="input-label">Position Title</label>
                        <input type="text" className="input-field" name="title" value={form.title} onChange={handleInput} placeholder="e.g. Lead Technical Architect" required />
                    </div>

                    <div className="input-group">
                        <label className="input-label">Job Description</label>
                        <textarea className="textarea-editor" name="description" value={form.description} onChange={handleInput} placeholder="Outline the role, responsibilities, and team culture..." required></textarea>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Skills Required</label>
                        <div className="tag-container">
                            {skills.map(skill => (
                                <span key={skill} className="skill-tag-item">
                                    {skill} <span onClick={() => removeSkill(skill)} style={{ cursor: 'pointer', marginLeft: '4px' }}>×</span>
                                </span>
                            ))}
                            <input
                                type="text"
                                className="tag-input"
                                placeholder="Add skill (press Enter)..."
                                value={skillInput}
                                onChange={(e) => setSkillInput(e.target.value)}
                                onKeyDown={handleAddSkill}
                            />
                        </div>
                    </div>

                    <div className="dual-input">
                        <div className="input-group">
                            <label className="input-label">Location</label>
                            <input type="text" className="input-field" name="location" value={form.location} onChange={handleInput} placeholder="Remote / London / NYC" />
                        </div>
                        <div className="input-group">
                            <label className="input-label">Salary Range</label>
                            <input type="text" className="input-field" name="salary" value={form.salary} onChange={handleInput} placeholder="e.g. 80k - 110k" />
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex' }}>
                    <div className="sidebar-controls">
                        <div className="input-group">
                            <label className="input-label">Experience Level</label>
                            <select className="select-field" name="experience_level" value={form.experience_level} onChange={handleInput}>
                                <option value="junior">Junior (1-2 years)</option>
                                <option value="mid">Mid-Level (3-5 years)</option>
                                <option value="senior">Senior (5-8 years)</option>
                                <option value="lead">Lead / Director (8+ years)</option>
                            </select>
                        </div>

                        <div className="input-group">
                            <label className="input-label">Contract Type</label>
                            <select className="select-field" name="job_type" value={form.job_type} onChange={handleInput}>
                                <option value="full_time">Full-Time Permanent</option>
                                <option value="contract">Contract / Freelance</option>
                                <option value="part_time">Part-Time</option>
                                <option value="freelance">Freelance</option>
                            </select>
                        </div>

                        <div className="input-group">
                            <label className="input-label">Work Mode</label>
                            <select className="select-field" name="work_mode" value={form.work_mode} onChange={handleInput}>
                                <option value="remote">Remote</option>
                                <option value="on_site">On-Site</option>
                                <option value="hybrid">Hybrid</option>
                            </select>
                        </div>

                        <div style={{ marginTop: '40px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <button className="btn-primary" onClick={() => handlePublish(false)} disabled={isLoading}>
                                {isLoading ? 'Publishing...' : 'Publish Job'}
                            </button>
                            <button className="btn-secondary" onClick={() => handlePublish(true)} disabled={isLoading}>
                                Save Draft
                            </button>
                        </div>

                        <div className="publish-meta">
                            Last Autosaved: Just now<br />
                            Visibility: Public upon approval
                        </div>
                    </div>
                    <VerticalLabel text="Entry Management // Posting" />
                </div>
            </div>
        </DashboardLayout>
    );
};

export default PostJob;
