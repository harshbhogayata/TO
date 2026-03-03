import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CompanyAssessmentDashboard.css';

const CompanyAssessmentDashboard = () => {
    const navigate = useNavigate();
    const { companyAssessments, setCompanyAssessments, companyResults, setCompanyResults } = useAssessmentStore();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tab, setTab] = useState('assessments'); // assessments | results | create
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [inviteForm, setInviteForm] = useState({ assessment: '', emails: '', deadline: '' });
    const [sendingInvite, setSendingInvite] = useState(false);

    // Create form
    const [createForm, setCreateForm] = useState({
        title: '', description: '', assessment_type: 'skill_test',
        difficulty: 'medium', time_limit_minutes: 30, passing_score: 70,
        is_proctored: false, max_attempts: 3,
    });
    const [creating, setCreating] = useState(false);

    usePageTitle('Company Assessments', 'Manage assessments, view candidate results, and send invitations.');

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [assessRes, resultsRes] = await Promise.all([
                assessmentService.companyAssessments(),
                assessmentService.companyResults(),
            ]);
            setCompanyAssessments(assessRes.data.results || assessRes.data);
            setCompanyResults(resultsRes.data.results || resultsRes.data);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load company assessment data.'));
        } finally {
            setLoading(false);
        }
    }, [setCompanyAssessments, setCompanyResults]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const handleCreateAssessment = async (e) => {
        e.preventDefault();
        setCreating(true);
        try {
            await assessmentService.createAssessment(createForm);
            setTab('assessments');
            fetchData();
            setCreateForm({
                title: '', description: '', assessment_type: 'skill_test',
                difficulty: 'medium', time_limit_minutes: 30, passing_score: 70,
                is_proctored: false, max_attempts: 3,
            });
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to create assessment.'));
        } finally {
            setCreating(false);
        }
    };

    const handleSendInvite = async (e) => {
        e.preventDefault();
        setSendingInvite(true);
        try {
            const emailList = inviteForm.emails.split(/[,;\n]/).map((e) => e.trim()).filter(Boolean);
            await assessmentService.sendInvitation({
                assessment: inviteForm.assessment,
                emails: emailList,
                deadline: inviteForm.deadline || undefined,
            });
            setShowInviteModal(false);
            setInviteForm({ assessment: '', emails: '', deadline: '' });
            alert('Invitations sent successfully!');
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to send invitations.'));
        } finally {
            setSendingInvite(false);
        }
    };

    const handleExportResults = async () => {
        try {
            const { data } = await assessmentService.exportResults({ format: 'csv' });
            const blob = new Blob([data], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'assessment_results.csv';
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            alert(getApiErrorMessage(err, 'Export failed.'));
        }
    };

    const totalCandidates = companyResults.length;
    const avgScore = companyResults.length
        ? Math.round(companyResults.reduce((s, r) => s + (r.score || r.percentage || 0), 0) / companyResults.length)
        : 0;
    const passRate = companyResults.length
        ? Math.round((companyResults.filter((r) => r.passed).length / companyResults.length) * 100)
        : 0;

    const tabs = [
        { key: 'assessments', label: 'My Assessments', count: companyAssessments.length },
        { key: 'results', label: 'Candidate Results', count: companyResults.length },
        { key: 'create', label: '+ Create New', count: null },
    ];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Company Assessment Dashboard',
                status: 'System Status: Operational',
                info: `${companyAssessments.length} Active Assessments`,
            }}
            pageTitleLine1="Company"
            pageTitleLine2="Assessments"
            headerRightContent={
                <div className="cad-header-stats">
                    <div className="cad-stat"><span className="cad-stat__val">{companyAssessments.length}</span><span className="cad-stat__label">Assessments</span></div>
                    <div className="cad-stat"><span className="cad-stat__val">{totalCandidates}</span><span className="cad-stat__label">Candidates</span></div>
                    <div className="cad-stat"><span className="cad-stat__val">{avgScore}%</span><span className="cad-stat__label">Avg Score</span></div>
                    <div className="cad-stat"><span className="cad-stat__val">{passRate}%</span><span className="cad-stat__label">Pass Rate</span></div>
                </div>
            }
        >
            <div className="cad-page">
                <div className="cad-tabs">
                    {tabs.map((t) => (
                        <button
                            key={t.key}
                            className={`cad-tab ${tab === t.key ? 'active' : ''}`}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label} {t.count != null && <span className="cad-tab__count">({t.count})</span>}
                        </button>
                    ))}
                </div>

                {error && <div className="cad-error">{error}</div>}

                {loading && tab !== 'create' ? (
                    <div className="cad-grid">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} style={{ width: '100%', height: '140px', borderRadius: '8px' }} />
                        ))}
                    </div>
                ) : tab === 'assessments' ? (
                    <>
                        <div className="cad-toolbar">
                            <button className="cad-invite-btn" onClick={() => setShowInviteModal(true)}>
                                ✉ Send Invitations
                            </button>
                        </div>
                        <div className="cad-grid">
                            {companyAssessments.length > 0 ? companyAssessments.map((a) => (
                                <div key={a.id} className="cad-assess-card">
                                    <div className="cad-assess-card__header">
                                        <h4>{a.title}</h4>
                                        <span className={`cad-assess-status ${a.is_published ? 'published' : 'draft'}`}>
                                            {a.is_published ? 'Published' : 'Draft'}
                                        </span>
                                    </div>
                                    <div className="cad-assess-card__meta">
                                        <span>{a.difficulty}</span>
                                        <span>{a.time_limit_minutes || '—'} min</span>
                                        <span>{a.question_count || '—'} questions</span>
                                    </div>
                                    <div className="cad-assess-card__stats">
                                        <span>Attempts: {a.total_attempts || 0}</span>
                                        <span>Avg Score: {a.average_score || '—'}%</span>
                                    </div>
                                    <Link to={`/assessments/${a.id}`} className="cad-assess-card__link">
                                        View Details →
                                    </Link>
                                </div>
                            )) : (
                                <p className="cad-empty">No assessments created yet. Click "+ Create New" to get started.</p>
                            )}
                        </div>
                    </>
                ) : tab === 'results' ? (
                    <>
                        <div className="cad-toolbar">
                            <button className="cad-export-btn" onClick={handleExportResults}>
                                📥 Export CSV
                            </button>
                        </div>
                        <div className="cad-results-table-wrap">
                            <table className="cad-results-table">
                                <thead>
                                    <tr>
                                        <th>Candidate</th>
                                        <th>Assessment</th>
                                        <th>Score</th>
                                        <th>Status</th>
                                        <th>Date</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {companyResults.length > 0 ? companyResults.map((res) => (
                                        <tr key={res.id}>
                                            <td>{res.candidate_name || res.user?.name || '—'}</td>
                                            <td>{res.assessment_title || res.assessment?.title || '—'}</td>
                                            <td>{res.score ?? res.percentage ?? 0}%</td>
                                            <td>
                                                <span className={`cad-result-status ${res.passed ? 'pass' : 'fail'}`}>
                                                    {res.passed ? 'Passed' : 'Failed'}
                                                </span>
                                            </td>
                                            <td>{new Date(res.completed_at || res.created_at).toLocaleDateString()}</td>
                                            <td>
                                                <Link to={`/assessments/${res.assessment_id || res.assessment?.id || res.assessment}/results/${res.id}`}>
                                                    View
                                                </Link>
                                            </td>
                                        </tr>
                                    )) : (
                                        <tr><td colSpan={6} className="cad-empty-row">No results yet.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </>
                ) : (
                    /* Create tab */
                    <form className="cad-create-form" onSubmit={handleCreateAssessment}>
                        <h3>Create New Assessment</h3>
                        <div className="cad-form-grid">
                            <div className="cad-field">
                                <label>Title</label>
                                <input
                                    type="text"
                                    value={createForm.title}
                                    onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="cad-field">
                                <label>Description</label>
                                <textarea
                                    value={createForm.description}
                                    onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                                    rows={3}
                                />
                            </div>
                            <div className="cad-field">
                                <label>Type</label>
                                <select
                                    value={createForm.assessment_type}
                                    onChange={(e) => setCreateForm({ ...createForm, assessment_type: e.target.value })}
                                >
                                    <option value="skill_test">Skill Test</option>
                                    <option value="certification">Certification</option>
                                    <option value="practice">Practice</option>
                                    <option value="interview">Interview</option>
                                </select>
                            </div>
                            <div className="cad-field">
                                <label>Difficulty</label>
                                <select
                                    value={createForm.difficulty}
                                    onChange={(e) => setCreateForm({ ...createForm, difficulty: e.target.value })}
                                >
                                    <option value="easy">Easy</option>
                                    <option value="medium">Medium</option>
                                    <option value="hard">Hard</option>
                                    <option value="expert">Expert</option>
                                </select>
                            </div>
                            <div className="cad-field">
                                <label>Time Limit (minutes)</label>
                                <input
                                    type="number"
                                    min={5}
                                    value={createForm.time_limit_minutes}
                                    onChange={(e) => setCreateForm({ ...createForm, time_limit_minutes: Number(e.target.value) })}
                                />
                            </div>
                            <div className="cad-field">
                                <label>Passing Score (%)</label>
                                <input
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={createForm.passing_score}
                                    onChange={(e) => setCreateForm({ ...createForm, passing_score: Number(e.target.value) })}
                                />
                            </div>
                            <div className="cad-field">
                                <label>Max Attempts</label>
                                <input
                                    type="number"
                                    min={1}
                                    value={createForm.max_attempts}
                                    onChange={(e) => setCreateForm({ ...createForm, max_attempts: Number(e.target.value) })}
                                />
                            </div>
                            <div className="cad-field cad-field--checkbox">
                                <label>
                                    <input
                                        type="checkbox"
                                        checked={createForm.is_proctored}
                                        onChange={(e) => setCreateForm({ ...createForm, is_proctored: e.target.checked })}
                                    />
                                    Enable Proctoring
                                </label>
                            </div>
                        </div>
                        <button type="submit" className="cad-create-btn" disabled={creating}>
                            {creating ? 'Creating…' : 'Create Assessment'}
                        </button>
                    </form>
                )}

                {/* Invite Modal */}
                {showInviteModal && (
                    <div className="cad-modal-overlay" onClick={() => setShowInviteModal(false)}>
                        <div className="cad-modal" onClick={(e) => e.stopPropagation()}>
                            <h3>Send Assessment Invitations</h3>
                            <form onSubmit={handleSendInvite}>
                                <div className="cad-field">
                                    <label>Assessment</label>
                                    <select
                                        value={inviteForm.assessment}
                                        onChange={(e) => setInviteForm({ ...inviteForm, assessment: e.target.value })}
                                        required
                                    >
                                        <option value="">Select assessment…</option>
                                        {companyAssessments.map((a) => (
                                            <option key={a.id} value={a.id}>{a.title}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="cad-field">
                                    <label>Candidate Emails (one per line or comma-separated)</label>
                                    <textarea
                                        value={inviteForm.emails}
                                        onChange={(e) => setInviteForm({ ...inviteForm, emails: e.target.value })}
                                        rows={4}
                                        placeholder="candidate@example.com"
                                        required
                                    />
                                </div>
                                <div className="cad-field">
                                    <label>Deadline (optional)</label>
                                    <input
                                        type="date"
                                        value={inviteForm.deadline}
                                        onChange={(e) => setInviteForm({ ...inviteForm, deadline: e.target.value })}
                                    />
                                </div>
                                <div className="cad-modal__actions">
                                    <button type="button" className="cad-modal__cancel" onClick={() => setShowInviteModal(false)}>
                                        Cancel
                                    </button>
                                    <button type="submit" className="cad-modal__send" disabled={sendingInvite}>
                                        {sendingInvite ? 'Sending…' : 'Send Invitations'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default CompanyAssessmentDashboard;
