import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { useAssessmentStore } from '../store/assessmentStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './QuestionBankManager.css';

/* ── Difficulty helpers ─────────────────────────────────────── */
const DIFF_LABELS = { 1: 'Very Easy', 2: 'Easy', 3: 'Medium', 4: 'Hard', 5: 'Very Hard' };
const TYPE_LABELS = {
    mcq: 'MCQ', multi_select: 'Multi-Select', true_false: 'T/F',
    short_answer: 'Short', code: 'Code', essay: 'Essay', ordering: 'Order',
};

/* ── Create Bank Modal ──────────────────────────────────────── */
const CreateBankModal = ({ open, onClose, onCreated }) => {
    const [form, setForm] = useState({ name: '', description: '', visibility: 'private' });
    const [saving, setSaving] = useState(false);

    if (!open) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const slug = form.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
            await assessmentService.createQuestionBank({ ...form, slug });
            onCreated();
            onClose();
            setForm({ name: '', description: '', visibility: 'private' });
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to create question bank.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="qbm-modal-backdrop" onClick={onClose}>
            <form className="qbm-modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
                <h2>Create Question Bank</h2>
                <div className="qbm-modal-field">
                    <label>Bank Name</label>
                    <input
                        type="text"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="e.g. Python Fundamentals"
                        required
                    />
                </div>
                <div className="qbm-modal-field">
                    <label>Description</label>
                    <textarea
                        rows={3}
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                        placeholder="Brief description of the question bank..."
                    />
                </div>
                <div className="qbm-modal-field">
                    <label>Visibility</label>
                    <select
                        value={form.visibility}
                        onChange={(e) => setForm({ ...form, visibility: e.target.value })}
                    >
                        <option value="private">Private (Draft)</option>
                        <option value="company">Company Only</option>
                        <option value="public">Public</option>
                    </select>
                </div>
                <div className="qbm-modal-actions">
                    <button type="button" className="qbm-modal-cancel" onClick={onClose}>Cancel</button>
                    <button type="submit" className="qbm-modal-submit" disabled={saving || !form.name.trim()}>
                        {saving ? 'Creating...' : 'Create Bank'}
                    </button>
                </div>
            </form>
        </div>
    );
};

/* ── Main Component ─────────────────────────────────────────── */
const QuestionBankManager = () => {
    const {
        questionBanks, questionBanksLoading, questionBanksError, activeBank,
        bankQuestions, bankQuestionsLoading, approvalQueue,
        setQuestionBanks, setQuestionBanksLoading, setQuestionBanksError,
        setActiveBank, setBankQuestions, setBankQuestionsLoading, setApprovalQueue,
    } = useAssessmentStore();

    const [tab, setTab] = useState('questions');
    const [bankSearch, setBankSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState('');
    const [diffFilter, setDiffFilter] = useState('');
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedForApproval, setSelectedForApproval] = useState(new Set());
    const [bulkApproving, setBulkApproving] = useState(false);

    usePageTitle('Question Banks', 'Manage question banks, review questions, and calibrate difficulty.');

    /* fetch banks */
    const fetchBanks = useCallback(async () => {
        setQuestionBanksLoading(true);
        setQuestionBanksError(null);
        try {
            const params = {};
            if (bankSearch) params.search = bankSearch;
            const { data } = await assessmentService.listQuestionBanks(params);
            const list = data.results || data;
            setQuestionBanks(list);
            if (list.length > 0 && !activeBank) {
                setActiveBank(list[0]);
            }
        } catch (err) {
            setQuestionBanksError(getApiErrorMessage(err, 'Failed to load question banks.'));
        } finally {
            setQuestionBanksLoading(false);
        }
    }, [bankSearch, activeBank, setQuestionBanks, setQuestionBanksLoading, setQuestionBanksError, setActiveBank]);

    /* fetch questions for active bank */
    const fetchQuestions = useCallback(async () => {
        if (!activeBank) return;
        setBankQuestionsLoading(true);
        try {
            const params = {};
            if (typeFilter) params.type = typeFilter;
            if (diffFilter) params.difficulty = diffFilter;
            const { data } = await assessmentService.listQuestions(activeBank.id, params);
            const list = data.results || data;
            setBankQuestions(list);

            // Separate approval queue
            const pending = list.filter((q) => !q.is_approved);
            setApprovalQueue(pending);
        } catch { /* silent */ } finally {
            setBankQuestionsLoading(false);
        }
    }, [activeBank, typeFilter, diffFilter, setBankQuestions, setBankQuestionsLoading, setApprovalQueue]);

    useEffect(() => {
        const t = setTimeout(fetchBanks, 300);
        return () => clearTimeout(t);
    }, [fetchBanks]);

    useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

    /* approve single question */
    const handleApprove = async (questionId) => {
        try {
            await assessmentService.approveQuestion(questionId);
            fetchQuestions();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to approve question.'));
        }
    };

    /* bulk approve */
    const handleBulkApprove = async () => {
        if (selectedForApproval.size === 0) return;
        setBulkApproving(true);
        try {
            await assessmentService.bulkApproveQuestions([...selectedForApproval]);
            setSelectedForApproval(new Set());
            fetchQuestions();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Bulk approval failed.'));
        } finally {
            setBulkApproving(false);
        }
    };

    /* delete question */
    const handleDelete = async (questionId) => {
        if (!window.confirm('Soft-delete this question?')) return;
        try {
            await assessmentService.deleteQuestion(questionId);
            fetchQuestions();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to delete question.'));
        }
    };

    /* toggle selection for bulk approve */
    const toggleSelection = (id) => {
        setSelectedForApproval((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    /* calibration data */
    const diffDistribution = [1, 2, 3, 4, 5].map((d) => ({
        level: d,
        label: DIFF_LABELS[d],
        count: bankQuestions.filter((q) => q.difficulty === d).length,
    }));
    const totalQuestions = bankQuestions.length;
    const avgSuccessRate = totalQuestions > 0
        ? (bankQuestions.reduce((sum, q) => sum + (q.success_rate || 0), 0) / totalQuestions).toFixed(1)
        : 0;

    /* filtered display banks */
    const displayBanks = questionBanks.filter((b) =>
        !bankSearch || b.name.toLowerCase().includes(bankSearch.toLowerCase()),
    );

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Assessment Engine',
                status: 'System Status: Operational',
                info: 'Banks: Synced',
            }}
            pageTitleLine1="Question"
            pageTitleLine2="Banks"
            headerRightContent={
                <div className="qbm-header-stats">
                    <div className="qbm-stat-block">
                        <h3>Total Banks</h3>
                        <p>{questionBanks.length}</p>
                    </div>
                    <div className="qbm-stat-block">
                        <h3>Active Questions</h3>
                        <p>{activeBank?.question_count ?? '—'}</p>
                    </div>
                    <div className="qbm-stat-block">
                        <h3>Pending Approval</h3>
                        <p>{approvalQueue.length}</p>
                    </div>
                </div>
            }
        >
            <div className="qbm-layout">
                {/* ── Bank List Panel ────────────────────────── */}
                <aside className="qbm-bank-panel">
                    <div className="qbm-bank-search">
                        <input
                            type="text"
                            className="qbm-bank-search-input"
                            placeholder="Search banks..."
                            value={bankSearch}
                            onChange={(e) => setBankSearch(e.target.value)}
                        />
                    </div>

                    <div className="qbm-bank-list">
                        {questionBanksLoading ? (
                            Array.from({ length: 4 }).map((_, i) => (
                                <div key={i} className="qbm-bank-card">
                                    <Skeleton style={{ width: '70%', height: 16, marginBottom: 8 }} />
                                    <Skeleton style={{ width: '50%', height: 12 }} />
                                </div>
                            ))
                        ) : (
                            displayBanks.map((bank) => (
                                <div
                                    key={bank.id}
                                    className={`qbm-bank-card ${activeBank?.id === bank.id ? 'qbm-bank-card--active' : ''}`}
                                    onClick={() => setActiveBank(bank)}
                                >
                                    <div className="qbm-bank-card__name">{bank.name}</div>
                                    <div className="qbm-bank-card__meta">
                                        <span>{bank.question_count} Questions</span>
                                        <span>v{bank.version}</span>
                                    </div>
                                    <div>
                                        {bank.primary_tag_name && (
                                            <span className="qbm-bank-card__tag">{bank.primary_tag_name}</span>
                                        )}
                                        <span className="qbm-bank-card__vis">{bank.visibility}</span>
                                    </div>
                                </div>
                            ))
                        )}
                        {!questionBanksLoading && displayBanks.length === 0 && (
                            <p className="qbm-empty">No question banks found.</p>
                        )}
                    </div>

                    <div className="qbm-bank-actions">
                        <button
                            className="qbm-create-bank-btn"
                            onClick={() => setShowCreateModal(true)}
                        >
                            + New Bank
                        </button>
                    </div>
                </aside>

                {/* ── Main Content ───────────────────────────── */}
                <div className="qbm-content">
                    {/* Tabs */}
                    <div className="qbm-tabs">
                        {['questions', 'calibration', 'approval'].map((t) => (
                            <button
                                key={t}
                                className={`qbm-tab ${tab === t ? 'qbm-tab--active' : ''}`}
                                onClick={() => setTab(t)}
                            >
                                {t === 'questions' ? 'Questions' : t === 'calibration' ? 'Calibration' : `Approval (${approvalQueue.length})`}
                            </button>
                        ))}
                    </div>

                    <div className="qbm-tab-content">
                        {questionBanksError && <div className="qbm-error-banner">{questionBanksError}</div>}

                        {!activeBank ? (
                            <p className="qbm-empty">Select or create a question bank to get started.</p>
                        ) : (
                            <>
                                {/* ── Questions Tab ─────────────────── */}
                                {tab === 'questions' && (
                                    <>
                                        <div className="qbm-questions-toolbar">
                                            <div className="qbm-toolbar-left">
                                                <select
                                                    className="qbm-toolbar-select"
                                                    value={typeFilter}
                                                    onChange={(e) => setTypeFilter(e.target.value)}
                                                >
                                                    <option value="">All Types</option>
                                                    {Object.entries(TYPE_LABELS).map(([val, label]) => (
                                                        <option key={val} value={val}>{label}</option>
                                                    ))}
                                                </select>
                                                <select
                                                    className="qbm-toolbar-select"
                                                    value={diffFilter}
                                                    onChange={(e) => setDiffFilter(e.target.value)}
                                                >
                                                    <option value="">All Difficulties</option>
                                                    {Object.entries(DIFF_LABELS).map(([val, label]) => (
                                                        <option key={val} value={val}>{label}</option>
                                                    ))}
                                                </select>
                                            </div>
                                            <button className="qbm-add-question-btn">+ Add Question</button>
                                        </div>

                                        {bankQuestionsLoading ? (
                                            <div className="qbm-question-list">
                                                {Array.from({ length: 4 }).map((_, i) => (
                                                    <div key={i} className="qbm-question-item">
                                                        <div style={{ flex: 1 }}>
                                                            <Skeleton style={{ width: '60%', height: 16, marginBottom: 8 }} />
                                                            <Skeleton style={{ width: '40%', height: 12 }} />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="qbm-question-list">
                                                {bankQuestions.map((q) => (
                                                    <div key={q.id} className="qbm-question-item">
                                                        <div className="qbm-question-info">
                                                            <div className="qbm-question-title">{q.title}</div>
                                                            <div className="qbm-question-meta">
                                                                <span>{TYPE_LABELS[q.question_type] || q.question_type}</span>
                                                                <span className={`qbm-diff-badge qbm-diff-badge--${q.difficulty}`}>
                                                                    {DIFF_LABELS[q.difficulty] || `D${q.difficulty}`}
                                                                </span>
                                                                <span>{q.points} pts</span>
                                                                <span>{q.times_used || 0} uses</span>
                                                                <span>{q.success_rate ?? 0}% success</span>
                                                            </div>
                                                        </div>
                                                        <div className="qbm-question-actions">
                                                            {!q.is_approved && (
                                                                <button
                                                                    className="qbm-action-btn qbm-action-btn--approve"
                                                                    onClick={() => handleApprove(q.id)}
                                                                >
                                                                    Approve
                                                                </button>
                                                            )}
                                                            <button
                                                                className="qbm-action-btn qbm-action-btn--danger"
                                                                onClick={() => handleDelete(q.id)}
                                                            >
                                                                Delete
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                                {bankQuestions.length === 0 && (
                                                    <p className="qbm-empty">No questions in this bank yet.</p>
                                                )}
                                            </div>
                                        )}
                                    </>
                                )}

                                {/* ── Calibration Tab ───────────────── */}
                                {tab === 'calibration' && (
                                    <div className="qbm-calibration-grid">
                                        <div className="qbm-calibration-card">
                                            <h4>Difficulty Distribution</h4>
                                            {diffDistribution.map((d) => (
                                                <div key={d.level} className="qbm-calibration-row">
                                                    <span>{d.label}</span>
                                                    <div className="qbm-calibration-bar-wrap">
                                                        <div
                                                            className="qbm-calibration-bar"
                                                            style={{ width: `${totalQuestions ? (d.count / totalQuestions) * 100 : 0}%` }}
                                                        />
                                                    </div>
                                                    <span>{d.count}</span>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="qbm-calibration-card">
                                            <h4>Bank Statistics</h4>
                                            <div className="qbm-calibration-row">
                                                <span>Total Questions</span>
                                                <span style={{ fontFamily: 'var(--font-display)' }}>{totalQuestions}</span>
                                            </div>
                                            <div className="qbm-calibration-row">
                                                <span>Avg Difficulty</span>
                                                <span style={{ fontFamily: 'var(--font-display)' }}>{activeBank.avg_difficulty}</span>
                                            </div>
                                            <div className="qbm-calibration-row">
                                                <span>Avg Success Rate</span>
                                                <span style={{ fontFamily: 'var(--font-display)' }}>{avgSuccessRate}%</span>
                                            </div>
                                            <div className="qbm-calibration-row">
                                                <span>Approved</span>
                                                <span style={{ fontFamily: 'var(--font-display)' }}>
                                                    {bankQuestions.filter((q) => q.is_approved).length} / {totalQuestions}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="qbm-calibration-card">
                                            <h4>Type Distribution</h4>
                                            {Object.entries(TYPE_LABELS).map(([type, label]) => {
                                                const count = bankQuestions.filter((q) => q.question_type === type).length;
                                                if (count === 0) return null;
                                                return (
                                                    <div key={type} className="qbm-calibration-row">
                                                        <span>{label}</span>
                                                        <div className="qbm-calibration-bar-wrap">
                                                            <div
                                                                className="qbm-calibration-bar"
                                                                style={{ width: `${(count / totalQuestions) * 100}%` }}
                                                            />
                                                        </div>
                                                        <span>{count}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}

                                {/* ── Approval Queue Tab ─────────────── */}
                                {tab === 'approval' && (
                                    <>
                                        <div className="qbm-approval-toolbar">
                                            <span className="qbm-approval-count">
                                                {approvalQueue.length} Pending · {selectedForApproval.size} Selected
                                            </span>
                                            <button
                                                className="qbm-bulk-approve-btn"
                                                disabled={selectedForApproval.size === 0 || bulkApproving}
                                                onClick={handleBulkApprove}
                                            >
                                                {bulkApproving ? 'Approving...' : 'Bulk Approve'}
                                            </button>
                                        </div>

                                        <div className="qbm-question-list">
                                            {approvalQueue.map((q) => (
                                                <div key={q.id} className="qbm-question-item">
                                                    <label style={{ marginRight: 12, cursor: 'pointer' }}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedForApproval.has(q.id)}
                                                            onChange={() => toggleSelection(q.id)}
                                                            style={{ accentColor: '#000' }}
                                                        />
                                                    </label>
                                                    <div className="qbm-question-info">
                                                        <div className="qbm-question-title">{q.title}</div>
                                                        <div className="qbm-question-meta">
                                                            <span>{TYPE_LABELS[q.question_type] || q.question_type}</span>
                                                            <span className={`qbm-diff-badge qbm-diff-badge--${q.difficulty}`}>
                                                                {DIFF_LABELS[q.difficulty] || `D${q.difficulty}`}
                                                            </span>
                                                            <span>{q.points} pts</span>
                                                        </div>
                                                    </div>
                                                    <div className="qbm-question-actions">
                                                        <button
                                                            className="qbm-action-btn qbm-action-btn--approve"
                                                            onClick={() => handleApprove(q.id)}
                                                        >
                                                            Approve
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                            {approvalQueue.length === 0 && (
                                                <p className="qbm-empty">All questions are approved. Nothing pending.</p>
                                            )}
                                        </div>
                                    </>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Create Bank Modal */}
            <CreateBankModal
                open={showCreateModal}
                onClose={() => setShowCreateModal(false)}
                onCreated={fetchBanks}
            />
        </DashboardLayout>
    );
};

export default QuestionBankManager;
