import { useState, useEffect, useCallback } from 'react';
import { useToast } from '../contexts/ToastContext';
import Sidebar from '../components/Sidebar';
import TapeBar from '../components/TapeBar';
import { complianceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';

/* ── Action / category options for filter dropdowns ──────────────────────── */
const ACTION_OPTIONS = [
    { value: '', label: 'All Actions' },
    { value: 'LOGIN', label: 'Login' },
    { value: 'LOGOUT', label: 'Logout' },
    { value: 'LOGIN_FAILED', label: 'Login Failed' },
    { value: 'PASSWORD_CHANGE', label: 'Password Change' },
    { value: 'UPDATE', label: 'Profile Update' },
    { value: '2FA_ENABLE', label: '2FA Enabled' },
    { value: '2FA_DISABLE', label: '2FA Disabled' },
    { value: 'CONSENT_GRANT', label: 'Consent Granted' },
    { value: 'CONSENT_WITHDRAW', label: 'Consent Withdrawn' },
    { value: 'DATA_EXPORT_REQUEST', label: 'Export Requested' },
    { value: 'DATA_DELETION_REQUEST', label: 'Deletion Requested' },
    { value: 'TEAM_CREATE', label: 'Team Created' },
    { value: 'TEAM_INVITE', label: 'Member Invited' },
    { value: 'TEAM_INVITE_ACCEPT', label: 'Member Joined' },
    { value: 'TEAM_MEMBER_REMOVE', label: 'Member Removed' },
    { value: 'CREATE', label: 'Job Created' },
    { value: 'APPLICATION_SUBMIT', label: 'Application Submitted' },
    { value: 'ADMIN_VERIFY_USER', label: 'Admin Verify User' },
    { value: 'SUBSCRIPTION_CREATE', label: 'Subscription Created' },
    { value: 'PAYMENT_FAILED', label: 'Payment Failed' },
];

const CATEGORY_OPTIONS = [
    { value: '', label: 'All Categories' },
    { value: 'AUTH', label: 'Authentication' },
    { value: 'USER', label: 'Account' },
    { value: 'COMPLIANCE', label: 'Compliance' },
    { value: 'TEAM', label: 'Team' },
    { value: 'APPLICATION', label: 'Application' },
    { value: 'JOB', label: 'Job' },
    { value: 'MESSAGE', label: 'Messaging' },
    { value: 'PAYMENT', label: 'Payment' },
    { value: 'ADMIN', label: 'Admin' },
    { value: 'SYSTEM', label: 'System' },
];

/* ── Design-faithful inline styles (Design 3) ────────────────────────────── */
const s = {
    statsStrip: {
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0',
        borderBottom: '1px solid #000000',
    },
    statCard: {
        padding: '24px 32px', borderRight: '1px solid #000000',
    },
    statCardLast: {
        padding: '24px 32px',
    },
    statLabel: {
        fontFamily: "'Bodoni Moda', serif", fontSize: '11px', textTransform: 'uppercase',
        opacity: 0.7, marginBottom: '4px',
    },
    statValue: {
        fontFamily: "'Anton', sans-serif", fontSize: '36px', letterSpacing: '-1px',
    },
    filtersRow: {
        display: 'flex', gap: '12px', padding: '20px 32px',
        borderBottom: '1px solid #000000', flexWrap: 'wrap', alignItems: 'center',
    },
    filterSelect: {
        padding: '10px 12px', background: 'transparent', border: '1px solid #000000',
        fontFamily: "'Inter', sans-serif", fontSize: '12px', outline: 'none',
        cursor: 'pointer', minWidth: '150px',
    },
    filterInput: {
        padding: '10px 12px', background: 'transparent', border: '1px solid #000000',
        fontFamily: "'Inter', sans-serif", fontSize: '12px', outline: 'none',
        minWidth: '140px',
    },
    searchInput: {
        padding: '10px 12px', background: 'transparent', border: '1px solid #000000',
        fontFamily: "'Inter', sans-serif", fontSize: '12px', outline: 'none',
        flex: 1, minWidth: '200px',
    },
    table: {
        width: '100%', borderCollapse: 'collapse',
    },
    th: {
        fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '1px', padding: '14px 16px',
        borderBottom: '2px solid #000000', textAlign: 'left', whiteSpace: 'nowrap',
    },
    td: {
        fontFamily: "'Inter', sans-serif", fontSize: '13px', padding: '14px 16px',
        borderBottom: '1px solid rgba(0,0,0,0.1)', verticalAlign: 'middle',
    },
    actionBadge: {
        display: 'inline-block', padding: '2px 8px', border: '1px solid #000000',
        fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
        fontFamily: "'Inter', sans-serif",
    },
    categoryPill: {
        display: 'inline-block', padding: '2px 8px', fontSize: '10px', fontWeight: 600,
        textTransform: 'uppercase', fontFamily: "'Inter', sans-serif",
        background: '#f0f0f0', border: '1px solid #ccc',
    },
    expandBtn: {
        background: 'none', border: '1px solid #000000', width: '28px', height: '28px',
        cursor: 'pointer', fontFamily: "'Inter', sans-serif", fontSize: '14px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
    },
    expandedRow: {
        background: '#f9f8f5', padding: '24px 32px', borderBottom: '1px solid #000000',
    },
    metaGrid: {
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px',
        marginTop: '16px',
    },
    metaLabel: {
        fontFamily: "'Bodoni Moda', serif", fontSize: '10px', textTransform: 'uppercase',
        opacity: 0.6, marginBottom: '2px',
    },
    metaValue: {
        fontFamily: "'Inter', sans-serif", fontSize: '12px', wordBreak: 'break-all',
    },
    changesBlock: {
        background: '#111111', color: '#E6E2D8', padding: '16px', fontFamily: 'monospace',
        fontSize: '12px', marginTop: '12px', maxHeight: '200px', overflowY: 'auto',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    },
    pagination: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '16px 32px', borderTop: '1px solid #000000',
    },
    pageBtn: {
        background: 'transparent', border: '1px solid #000000', padding: '8px 14px',
        fontFamily: "'Inter', sans-serif", fontSize: '11px', cursor: 'pointer',
        fontWeight: 700,
    },
    pageBtnActive: {
        background: '#111111', color: '#E6E2D8', border: '1px solid #111111',
        padding: '8px 14px', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        cursor: 'default', fontWeight: 700,
    },
    integrityBadge: {
        display: 'inline-flex', alignItems: 'center', gap: '6px',
        padding: '6px 12px', fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', fontFamily: "'Inter', sans-serif",
        border: '1px solid',
    },
    btnVerify: {
        background: 'transparent', border: '1px solid #000000', padding: '8px 16px',
        fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px',
    },
};

const PAGE_SIZE = 20;

const formatTimestamp = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
        + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
};

const formatAction = (action) => (action || '').replace(/_/g, ' ');

const AuditLog = () => {
    usePageTitle('Audit Log', 'Security audit trail for platform activity.');
    const { addToast } = useToast();
    const { user } = useAuthStore();

    const [stats, setStats] = useState(null);
    const [logs, setLogs] = useState([]);
    const [count, setCount] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState(null);
    const [integrity, setIntegrity] = useState(null);
    const [verifying, setVerifying] = useState(false);

    const [filters, setFilters] = useState({
        action: '', category: '', date_from: '', date_to: '', search: '',
    });

    /* ── Fetch data ────────────────────────────────────────────────────── */
    const fetchStats = useCallback(async () => {
        try {
            const { data } = await complianceService.getAuditLogStats();
            setStats(data);
        } catch { /* silent */ }
    }, []);

    const fetchLogs = useCallback(async () => {
        setLoading(true);
        try {
            const params = { page };
            if (filters.action) params.action = filters.action;
            if (filters.category) params.category = filters.category;
            if (filters.date_from) params.date_from = filters.date_from;
            if (filters.date_to) params.date_to = filters.date_to;
            if (filters.search) params.search = filters.search;

            const { data } = await complianceService.getAuditLogs(params);
            setLogs(data.results || []);
            setCount(data.count || 0);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to load audit logs.'), 'error');
        } finally {
            setLoading(false);
        }
    }, [page, filters, addToast]);

    useEffect(() => { fetchStats(); }, [fetchStats]);
    useEffect(() => { fetchLogs(); }, [fetchLogs]);

    /* ── Integrity check ──────────────────────────────────────────────── */
    const handleVerify = async () => {
        setVerifying(true);
        try {
            const { data } = await complianceService.getAuditLogIntegrity(5000);
            setIntegrity(data);
            addToast(data.valid ? 'Chain integrity verified ✓' : 'Integrity breach detected!', data.valid ? 'success' : 'error');
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        } finally {
            setVerifying(false);
        }
    };

    /* ── Filter handlers ──────────────────────────────────────────────── */
    const updateFilter = (key, value) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    /* ── Pagination ───────────────────────────────────────────────────── */
    const totalPages = Math.ceil(count / PAGE_SIZE);
    const startItem = (page - 1) * PAGE_SIZE + 1;
    const endItem = Math.min(page * PAGE_SIZE, count);

    const getPageNumbers = () => {
        const pages = [];
        const maxVisible = 5;
        let start = Math.max(1, page - Math.floor(maxVisible / 2));
        let end = Math.min(totalPages, start + maxVisible - 1);
        if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1);
        for (let i = start; i <= end; i++) pages.push(i);
        return pages;
    };

    return (
        <>
            <a href="#main-content" className="skip-link">Skip to content</a>
            <TapeBar
                title="TalentOrbit Security Console v4.0.2"
                status={integrity?.valid ? 'Ledger Integrity: Verified' : 'Ledger Integrity: Unknown'}
                info={`Admin Session: ${user?.email || 'active'}`}
            />
            <div className="app-container">
                <Sidebar />
                <main id="main-content" className="main-content" tabIndex={-1}>
                    {/* ── Header ───────────────────────────────── */}
                    <header className="content-header">
                        <h1 className="page-title">Audit<br />Log</h1>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            {integrity && (
                                <span style={{
                                    ...s.integrityBadge,
                                    borderColor: integrity.valid ? '#2e7d32' : '#c62828',
                                    color: integrity.valid ? '#2e7d32' : '#c62828',
                                }}>
                                    {integrity.valid ? '● Verified' : '● Breach Detected'}
                                </span>
                            )}
                            <button
                                style={s.btnVerify}
                                onClick={handleVerify}
                                disabled={verifying}
                            >
                                {verifying ? 'Verifying…' : 'Verify Integrity'}
                            </button>
                        </div>
                    </header>

                    {/* ── Stats Strip ─────────────────────────── */}
                    {stats && (
                        <div style={s.statsStrip}>
                            <div style={s.statCard}>
                                <div style={s.statLabel}>Total Events</div>
                                <div style={s.statValue}>{(stats.total_entries || 0).toLocaleString()}</div>
                            </div>
                            <div style={s.statCard}>
                                <div style={s.statLabel}>Last 24 Hours</div>
                                <div style={s.statValue}>{(stats.last_24h || 0).toLocaleString()}</div>
                            </div>
                            <div style={s.statCard}>
                                <div style={s.statLabel}>Last 7 Days</div>
                                <div style={s.statValue}>{(stats.last_7d || 0).toLocaleString()}</div>
                            </div>
                            <div style={s.statCardLast}>
                                <div style={s.statLabel}>Failed Logins (24h)</div>
                                <div style={{ ...s.statValue, color: (stats.failed_logins_24h || 0) > 0 ? '#C4342D' : undefined }}>
                                    {(stats.failed_logins_24h || 0).toLocaleString()}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ── Filters ─────────────────────────────── */}
                    <div style={s.filtersRow}>
                        <select
                            style={s.filterSelect}
                            value={filters.action}
                            onChange={e => updateFilter('action', e.target.value)}
                        >
                            {ACTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                        <select
                            style={s.filterSelect}
                            value={filters.category}
                            onChange={e => updateFilter('category', e.target.value)}
                        >
                            {CATEGORY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                        <input
                            type="date"
                            style={s.filterInput}
                            value={filters.date_from}
                            onChange={e => updateFilter('date_from', e.target.value)}
                            placeholder="From"
                        />
                        <input
                            type="date"
                            style={s.filterInput}
                            value={filters.date_to}
                            onChange={e => updateFilter('date_to', e.target.value)}
                            placeholder="To"
                        />
                        <input
                            type="text"
                            style={s.searchInput}
                            value={filters.search}
                            onChange={e => updateFilter('search', e.target.value)}
                            placeholder="Search by description, email, resource…"
                        />
                    </div>

                    {/* ── Table ────────────────────────────────── */}
                    <div style={{ overflowX: 'auto' }}>
                        <table style={s.table}>
                            <thead>
                                <tr>
                                    <th style={s.th}>Timestamp</th>
                                    <th style={s.th}>Action</th>
                                    <th style={s.th}>Actor</th>
                                    <th style={s.th}>Category</th>
                                    <th style={s.th}>IP Address</th>
                                    <th style={{ ...s.th, width: '40px' }}></th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr>
                                        <td colSpan={6} style={{ ...s.td, textAlign: 'center', padding: '48px', opacity: 0.5, textTransform: 'uppercase', fontSize: '12px', letterSpacing: '1px' }}>
                                            Loading audit trail…
                                        </td>
                                    </tr>
                                ) : logs.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} style={{ ...s.td, textAlign: 'center', padding: '48px', opacity: 0.5 }}>
                                            No audit entries found.
                                        </td>
                                    </tr>
                                ) : logs.map(log => (
                                    <LogRow
                                        key={log.id}
                                        log={log}
                                        expanded={expandedId === log.id}
                                        onToggle={() => setExpandedId(expandedId === log.id ? null : log.id)}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* ── Pagination ───────────────────────────── */}
                    {count > 0 && (
                        <div style={s.pagination}>
                            <span style={{ fontFamily: "'Inter', sans-serif", fontSize: '12px', opacity: 0.7 }}>
                                Showing {startItem}–{endItem} of {count.toLocaleString()} results
                            </span>
                            <div style={{ display: 'flex', gap: '4px' }}>
                                <button
                                    style={s.pageBtn}
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                >
                                    ‹
                                </button>
                                {getPageNumbers().map(p => (
                                    <button
                                        key={p}
                                        style={p === page ? s.pageBtnActive : s.pageBtn}
                                        onClick={() => p !== page && setPage(p)}
                                    >
                                        {p}
                                    </button>
                                ))}
                                <button
                                    style={s.pageBtn}
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                >
                                    ›
                                </button>
                            </div>
                        </div>
                    )}
                </main>
            </div>
        </>
    );
};

/* ── Log Row + Expanded Detail ────────────────────────────────────────────── */
const LogRow = ({ log, expanded, onToggle }) => {
    const isFailed = (log.action || '').includes('failed');

    return (
        <>
            <tr
                style={{ cursor: 'pointer', background: expanded ? '#f9f8f5' : 'transparent' }}
                onClick={onToggle}
            >
                <td style={s.td}>
                    <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                        {formatTimestamp(log.created_at)}
                    </span>
                </td>
                <td style={s.td}>
                    <span style={{
                        ...s.actionBadge,
                        borderColor: isFailed ? '#c62828' : '#000000',
                        color: isFailed ? '#c62828' : '#000000',
                    }}>
                        {formatAction(log.action)}
                    </span>
                </td>
                <td style={s.td}>
                    <div>
                        <span style={{ fontSize: '13px' }}>{log.actor_email || 'System'}</span>
                        {log.actor_role && (
                            <span style={{ fontSize: '10px', opacity: 0.5, marginLeft: '6px', textTransform: 'uppercase' }}>
                                ({log.actor_role})
                            </span>
                        )}
                    </div>
                </td>
                <td style={s.td}>
                    <span style={s.categoryPill}>{log.category}</span>
                </td>
                <td style={s.td}>
                    <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                        {log.ip_address || '—'}
                    </span>
                </td>
                <td style={s.td}>
                    <button style={s.expandBtn} onClick={(e) => { e.stopPropagation(); onToggle(); }}>
                        {expanded ? '−' : '+'}
                    </button>
                </td>
            </tr>
            {expanded && (
                <tr>
                    <td colSpan={6} style={{ padding: 0 }}>
                        <div style={s.expandedRow}>
                            <div style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px', marginBottom: '8px' }}>
                                {log.description}
                            </div>
                            <div style={s.metaGrid}>
                                <div>
                                    <div style={s.metaLabel}>Resource</div>
                                    <div style={s.metaValue}>
                                        {log.resource_type ? `${log.resource_type} #${log.resource_id}` : '—'}
                                    </div>
                                </div>
                                <div>
                                    <div style={s.metaLabel}>Request ID</div>
                                    <div style={s.metaValue}>{log.request_id || '—'}</div>
                                </div>
                                <div>
                                    <div style={s.metaLabel}>User Agent</div>
                                    <div style={s.metaValue}>{log.user_agent || '—'}</div>
                                </div>
                            </div>
                            <div style={{ marginTop: '12px' }}>
                                <div style={s.metaLabel}>Checksum (SHA-256)</div>
                                <div style={{ ...s.metaValue, fontFamily: 'monospace', fontSize: '11px', opacity: 0.8 }}>
                                    {log.checksum || '—'}
                                </div>
                            </div>
                            {log.changes && Object.keys(log.changes).length > 0 && (
                                <>
                                    <div style={{ ...s.metaLabel, marginTop: '16px' }}>Changes</div>
                                    <div style={s.changesBlock}>
                                        {JSON.stringify(log.changes, null, 2)}
                                    </div>
                                </>
                            )}
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
};

export default AuditLog;
