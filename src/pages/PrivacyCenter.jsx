import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import Sidebar from '../components/Sidebar';
import TapeBar from '../components/TapeBar';
import { complianceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';

/* ── Design-faithful inline styles ─────────────────────────────────────────── */
const s = {
    pendingBanner: {
        backgroundColor: '#ef6c00', color: 'white', padding: '12px 40px',
        fontFamily: "'Inter', sans-serif", fontSize: '11px', fontWeight: 700,
        textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    },
    sectionContainer: { padding: '40px', borderBottom: '1px solid #000000' },
    sectionContainerLast: { padding: '40px' },
    sectionTitle: {
        fontFamily: "'Anton', sans-serif", fontSize: '28px', textTransform: 'uppercase',
        marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px',
    },
    cardGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' },
    policyCard: {
        border: '1px solid #000000', padding: '20px', display: 'flex',
        flexDirection: 'column', height: '100%',
    },
    policyHeader: { marginBottom: '20px' },
    policyName: {
        fontFamily: "'Bodoni Moda', serif", fontSize: '18px', textTransform: 'uppercase',
        display: 'block', marginBottom: '4px',
    },
    policyVersion: { fontFamily: "'Inter', sans-serif", fontSize: '10px', opacity: 0.6, textTransform: 'uppercase' },
    badgeConsented: {
        display: 'inline-block', padding: '4px 8px', fontSize: '9px', fontWeight: 700,
        textTransform: 'uppercase', background: '#2e7d32', color: 'white', border: 'none', marginBottom: '16px',
    },
    badgePending: {
        display: 'inline-block', padding: '4px 8px', fontSize: '9px', fontWeight: 700,
        textTransform: 'uppercase', background: '#ef6c00', color: 'white', border: 'none', marginBottom: '16px',
    },
    btnSm: {
        padding: '8px 12px', fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', cursor: 'pointer', border: '1px solid #000000',
        background: 'transparent', width: '100%', marginTop: 'auto',
    },
    btnSmFilled: {
        padding: '8px 12px', fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', cursor: 'pointer', border: '1px solid #000000',
        background: '#000000', color: '#E6E2D8', width: '100%', marginTop: 'auto',
    },
    dataTable: { width: '100%', borderCollapse: 'collapse', marginTop: '12px' },
    tableTh: {
        textAlign: 'left', padding: '12px', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        textTransform: 'uppercase', borderBottom: '1px solid #000000', opacity: 0.6,
    },
    tableTd: {
        padding: '16px 12px', fontFamily: "'Inter', sans-serif", fontSize: '13px',
        borderBottom: '1px solid rgba(0,0,0,0.1)',
    },
    statusPill: {
        padding: '2px 6px', fontSize: '9px', fontWeight: 700,
        textTransform: 'uppercase', border: '1px solid #000000',
    },
    dangerZone: {
        background: 'rgba(196, 52, 45, 0.05)', border: '1px solid #C4342D',
        padding: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    },
    dangerH4: {
        fontFamily: "'Bodoni Moda', serif", fontSize: '20px', textTransform: 'uppercase',
        color: '#C4342D', marginBottom: '8px',
    },
    dangerP: { fontFamily: "'Inter', sans-serif", fontSize: '12px', maxWidth: '500px', lineHeight: 1.5 },
    btnDanger: {
        background: '#C4342D', color: 'white', border: 'none', padding: '14px 28px',
        fontFamily: "'Inter', sans-serif", fontSize: '11px', fontWeight: 700,
        textTransform: 'uppercase', cursor: 'pointer',
    },
    countdown: { fontFamily: "'Anton', sans-serif", fontSize: '18px', color: '#C4342D', letterSpacing: '1px' },
    formLabel: {
        display: 'block', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        fontWeight: 700, textTransform: 'uppercase', marginBottom: '8px',
    },
    modalOverlay: {
        position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
        background: 'rgba(0,0,0,0.8)', display: 'flex', justifyContent: 'center',
        alignItems: 'center', zIndex: 1000,
    },
    modal: { background: '#E6E2D8', width: '500px', padding: '40px', border: '2px solid #000000' },
    modalTitle: { fontFamily: "'Anton', sans-serif", fontSize: '32px', textTransform: 'uppercase', marginBottom: '24px' },
    formGroup: { marginBottom: '20px' },
    formInput: {
        width: '100%', padding: '12px', border: '1px solid #000000',
        background: 'transparent', fontFamily: "'Inter', sans-serif", boxSizing: 'border-box',
    },
    formTextarea: {
        width: '100%', padding: '12px', border: '1px solid #000000',
        background: 'transparent', fontFamily: "'Inter', sans-serif", boxSizing: 'border-box',
    },
    verticalTag: {
        writingMode: 'vertical-rl', textOrientation: 'mixed', transform: 'rotate(180deg)',
        padding: '20px', fontFamily: "'Anton', sans-serif", fontSize: '24px',
        borderLeft: '1px solid #000000', backgroundColor: '#E6E2D8',
        height: '100%', textTransform: 'uppercase',
    },
};

const DeleteModal = ({ isOpen, onClose, onSubmit, submitting }) => {
    const [password, setPassword] = useState('');
    const [reason, setReason] = useState('');

    if (!isOpen) return null;

    const handleConfirm = () => {
        if (!password) return;
        onSubmit({ password, reason });
    };

    return (
        <div style={s.modalOverlay} onClick={onClose}>
            <div style={s.modal} onClick={(e) => e.stopPropagation()}>
                <h2 style={s.modalTitle}>Confirm Deletion</h2>
                <div style={s.formGroup}>
                    <label style={s.formLabel}>Verify Password</label>
                    <input
                        type="password"
                        style={s.formInput}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        autoComplete="current-password"
                    />
                </div>
                <div style={s.formGroup}>
                    <label style={s.formLabel}>Reason for leaving (Optional)</label>
                    <textarea
                        style={s.formTextarea}
                        rows={3}
                        placeholder="Tell us why..."
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                    />
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                        style={{ ...s.btnDanger, flex: 1, opacity: (!password || submitting) ? 0.6 : 1 }}
                        onClick={handleConfirm}
                        disabled={!password || submitting}
                    >
                        {submitting ? 'Requesting…' : 'Confirm Request'}
                    </button>
                    <button
                        style={{ ...s.btnSm, flex: 1, marginTop: 0 }}
                        onClick={onClose}
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
};

const PrivacyCenter = () => {
    usePageTitle('Privacy Center', 'Manage your data, consent, and privacy settings.');
    const { addToast } = useToast();
    const { user } = useAuthStore();

    const [loading, setLoading] = useState(true);
    const [consentStatus, setConsentStatus] = useState(null);
    const [exports, setExports] = useState([]);
    const [deletions, setDeletions] = useState([]);
    const [modalOpen, setModalOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [exportRequesting, setExportRequesting] = useState(false);

    /* ── Fetch all data on mount ───────────────────────────────────────── */
    useEffect(() => {
        (async () => {
            const [c, ex, del] = await Promise.allSettled([
                complianceService.getConsentStatus(),
                complianceService.getMyExports(),
                complianceService.getMyDeletions(),
            ]);
            if (c.status === 'fulfilled') setConsentStatus(c.value.data);
            if (ex.status === 'fulfilled') setExports(ex.value.data.results || ex.value.data);
            if (del.status === 'fulfilled') setDeletions(del.value.data.results || del.value.data);
            setLoading(false);
        })();
    }, []);

    /* ── Consent actions ──────────────────────────────────────────────── */
    const toggleConsent = async (policyId, isConsented) => {
        try {
            if (isConsented) {
                await complianceService.withdrawConsent(policyId);
                addToast('Consent withdrawn.', 'success');
            } else {
                await complianceService.grantConsent([policyId]);
                addToast('Consent granted.', 'success');
            }
            const { data } = await complianceService.getConsentStatus();
            setConsentStatus(data);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to update consent.'), 'error');
        }
    };

    /* ── Export actions ────────────────────────────────────────────────── */
    const handleRequestExport = async () => {
        setExportRequesting(true);
        try {
            await complianceService.requestExport();
            addToast("Data export requested — you'll receive an email when it's ready.", 'success');
            const { data } = await complianceService.getMyExports();
            setExports(data.results || data);
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        } finally {
            setExportRequesting(false);
        }
    };

    const handleDownload = async (token) => {
        try {
            const { data } = await complianceService.downloadExport(token);
            const url = window.URL.createObjectURL(new Blob([data], { type: 'application/zip' }));
            const a = document.createElement('a');
            a.href = url; a.download = 'talentorbit-data-export.zip'; a.click();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Download failed.'), 'error');
        }
    };

    /* ── Deletion actions ─────────────────────────────────────────────── */
    const handleRequestDeletion = async ({ password, reason }) => {
        setSubmitting(true);
        try {
            await complianceService.requestDeletion({ password, reason });
            addToast('Deletion requested — check your email to confirm.', 'success');
            setModalOpen(false);
            const { data } = await complianceService.getMyDeletions();
            setDeletions(data.results || data);
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancelDeletion = async (token) => {
        try {
            await complianceService.cancelDeletion(token);
            addToast('Deletion cancelled — your data is safe.', 'success');
            const { data } = await complianceService.getMyDeletions();
            setDeletions(data.results || data);
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        }
    };

    /* ── Helpers ──────────────────────────────────────────────────────── */
    const policies = consentStatus?.policies || [];
    const pendingCount = policies.filter(p => !p.has_consent).length;
    const activeDeletion = deletions.find(d => ['pending', 'cooling_off'].includes(d.status));

    const fmt = (d) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }) : '—';

    const pillStyle = (status) => {
        const base = { ...s.statusPill };
        if (status === 'completed') return { ...base, background: '#e3f2fd', borderColor: '#2196f3' };
        if (status === 'processing') return { ...base, background: '#fff3e0', borderColor: '#ef6c00' };
        if (status === 'expired') return { ...base, opacity: 0.5 };
        if (status === 'failed') return { ...base, background: '#ffebee', borderColor: '#c62828' };
        return { ...base, background: '#f5f5f5', borderColor: '#999' };
    };

    return (
        <>
            <a href="#main-content" className="skip-link">Skip to content</a>
            <TapeBar title="Privacy Center" status="Security Protocol: Active" info={`Auth: ${user?.email || ''}`} />
            <div className="app-container" style={{ gridTemplateColumns: '280px 1fr auto' }}>
                <Sidebar />
                <main id="main-content" className="main-content" tabIndex={-1}>
                    {/* ── Pending Banner ──────────────────────────────── */}
                    {pendingCount > 0 && (
                        <div style={s.pendingBanner}>
                            <span>Action Required: You have {pendingCount} pending policy update{pendingCount > 1 ? 's' : ''} to review.</span>
                            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Review Now</span>
                        </div>
                    )}

                    {/* ── Header ──────────────────────────────────────── */}
                    <header className="content-header">
                        <h1 className="page-title">Privacy<br />Center</h1>
                        <div>
                            <h3 style={{ fontFamily: "'Bodoni Moda', serif", fontSize: '14px', textTransform: 'uppercase' }}>Compliance</h3>
                            <p style={{ fontSize: '12px', opacity: 0.7 }}>GDPR / CCPA / DPA</p>
                        </div>
                    </header>

                    {loading ? (
                        <div style={{ padding: '80px 40px', textAlign: 'center', opacity: 0.5, fontFamily: "'Inter', sans-serif", fontSize: '14px', textTransform: 'uppercase' }}>
                            Loading compliance data…
                        </div>
                    ) : (
                        <>
                            {/* ── 01 // Consent Management ───────────────── */}
                            <section style={s.sectionContainer}>
                                <h2 style={s.sectionTitle}>01 // Consent Management</h2>
                                <div style={s.cardGrid}>
                                    {policies.map((policy) => {
                                        const isConsented = policy.has_consent;
                                        return (
                                            <div key={policy.id} style={s.policyCard}>
                                                <div style={s.policyHeader}>
                                                    <span style={s.policyName}>{policy.title || policy.type.toUpperCase()}</span>
                                                    <span style={s.policyVersion}>v{policy.version}</span>
                                                </div>
                                                <span style={isConsented ? s.badgeConsented : s.badgePending}>
                                                    {isConsented ? 'Consented' : 'Pending Review'}
                                                </span>
                                                <button
                                                    style={isConsented ? s.btnSm : s.btnSmFilled}
                                                    onClick={() => toggleConsent(policy.id, isConsented)}
                                                    onMouseEnter={(e) => { if (isConsented) { e.currentTarget.style.background = '#000000'; e.currentTarget.style.color = '#E6E2D8'; } }}
                                                    onMouseLeave={(e) => { if (isConsented) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#000000'; } }}
                                                >
                                                    {isConsented ? 'Withdraw Consent' : 'Grant Consent'}
                                                </button>
                                            </div>
                                        );
                                    })}
                                    {policies.length === 0 && (
                                        <p style={{ fontFamily: "'Inter', sans-serif", fontSize: '13px', opacity: 0.5 }}>
                                            No active policies require consent.
                                        </p>
                                    )}
                                </div>
                            </section>

                            {/* ── 02 // GDPR Data Export ─────────────────── */}
                            <section style={s.sectionContainer}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '24px' }}>
                                    <h2 style={{ ...s.sectionTitle, marginBottom: 0 }}>02 // GDPR Data Export</h2>
                                    <button
                                        style={{ ...s.btnSm, width: 'auto', padding: '10px 24px', marginTop: 0, opacity: exportRequesting ? 0.6 : 1 }}
                                        onClick={handleRequestExport}
                                        disabled={exportRequesting}
                                        onMouseEnter={(e) => { e.currentTarget.style.background = '#000000'; e.currentTarget.style.color = '#E6E2D8'; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#000000'; }}
                                    >
                                        {exportRequesting ? 'Requesting…' : 'Request New Export'}
                                    </button>
                                </div>
                                <table style={s.dataTable}>
                                    <thead>
                                        <tr>
                                            <th style={s.tableTh}>Request Date</th>
                                            <th style={s.tableTh}>Data Scope</th>
                                            <th style={s.tableTh}>Status</th>
                                            <th style={s.tableTh}>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {exports.length === 0 ? (
                                            <tr>
                                                <td colSpan={4} style={{ ...s.tableTd, textAlign: 'center', opacity: 0.5 }}>No export requests yet.</td>
                                            </tr>
                                        ) : exports.map((exp) => (
                                            <tr key={exp.id}>
                                                <td style={s.tableTd}>{fmt(exp.requested_at)}</td>
                                                <td style={s.tableTd}>Full Profile &amp; Activity Log</td>
                                                <td style={s.tableTd}>
                                                    <span style={pillStyle(exp.status)}>
                                                        {exp.status.charAt(0).toUpperCase() + exp.status.slice(1)}
                                                    </span>
                                                </td>
                                                <td style={s.tableTd}>
                                                    {exp.is_downloadable ? (
                                                        <a
                                                            href="#"
                                                            onClick={(e) => { e.preventDefault(); handleDownload(exp.download_token); }}
                                                            style={{ color: 'black', fontWeight: 700, fontSize: '11px' }}
                                                        >
                                                            DOWNLOAD .ZIP
                                                        </a>
                                                    ) : exp.status === 'processing' ? (
                                                        <span style={{ opacity: 0.4 }}>Preparing...</span>
                                                    ) : (
                                                        <span style={{ opacity: 0.4 }}>Unavailable</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </section>

                            {/* ── 03 // Danger Zone ──────────────────────── */}
                            <section style={s.sectionContainerLast}>
                                <h2 style={s.sectionTitle}>03 // Danger Zone</h2>
                                <div style={s.dangerZone}>
                                    <div>
                                        <h4 style={s.dangerH4}>Account Deletion Request</h4>
                                        <p style={s.dangerP}>
                                            Requesting account deletion will initiate a 14-day cooling-off period.
                                            After this window, all personal data will be purged from TalentOrbit's
                                            active systems according to our retention policy.
                                        </p>
                                        <div style={{ marginTop: '16px' }}>
                                            <span style={{ ...s.formLabel, marginBottom: '4px' }}>Active Countdown:</span>
                                            <span style={s.countdown}>
                                                {activeDeletion && activeDeletion.status === 'cooling_off' && activeDeletion.cooling_off_ends_at
                                                    ? `DELETION ON ${fmt(activeDeletion.cooling_off_ends_at).toUpperCase()}`
                                                    : activeDeletion && activeDeletion.status === 'pending'
                                                        ? 'AWAITING CONFIRMATION'
                                                        : 'NO PENDING REQUEST'}
                                            </span>
                                        </div>
                                        {activeDeletion && activeDeletion.is_cancellable && (
                                            <button
                                                style={{ ...s.btnSm, marginTop: '12px', width: 'auto', padding: '8px 16px', borderColor: '#C4342D', color: '#C4342D' }}
                                                onClick={() => handleCancelDeletion(activeDeletion.cancellation_token)}
                                            >
                                                Cancel Deletion
                                            </button>
                                        )}
                                    </div>
                                    <button style={s.btnDanger} onClick={() => setModalOpen(true)}>
                                        Request Deletion
                                    </button>
                                </div>
                            </section>
                        </>
                    )}
                </main>
                <div style={s.verticalTag}>Legal Compliance // 2026</div>
            </div>

            <DeleteModal
                isOpen={modalOpen}
                onClose={() => setModalOpen(false)}
                onSubmit={handleRequestDeletion}
                submitting={submitting}
            />
        </>
    );
};

export default PrivacyCenter;
