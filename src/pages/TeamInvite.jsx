import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useToast } from '../contexts/ToastContext';
import TapeBar from '../components/TapeBar';
import { complianceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';

/* ── Design-faithful inline styles (Design 4) ────────────────────────────── */
const s = {
    body: {
        minHeight: '100vh', background: '#E6E2D8', display: 'flex',
        flexDirection: 'column', position: 'relative', overflow: 'hidden',
    },
    container: {
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative', zIndex: 1,
    },
    card: {
        background: '#111111', color: '#F0F0F0', width: '100%', maxWidth: '440px',
        border: '1px solid #333', position: 'relative',
    },
    cardBody: { padding: '48px 40px' },
    logoPlaceholder: {
        width: '48px', height: '48px', border: '1px solid #555',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: "'Anton', sans-serif", fontSize: '18px',
        marginBottom: '32px', color: '#F0F0F0',
    },
    subtitle: {
        fontFamily: "'Bodoni Moda', serif", fontSize: '12px',
        textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.6,
        marginBottom: '8px',
    },
    teamName: {
        fontFamily: "'Anton', sans-serif", fontSize: '42px',
        textTransform: 'uppercase', lineHeight: 1.0, marginBottom: '24px',
    },
    inviterRow: {
        display: 'flex', alignItems: 'center', gap: '12px',
        marginBottom: '16px', paddingBottom: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
    },
    inviterAvatar: {
        width: '36px', height: '36px', borderRadius: '50%',
        border: '1px solid #555', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        fontSize: '14px', fontWeight: 700, color: '#aaa',
        textTransform: 'uppercase',
    },
    inviterName: {
        fontFamily: "'Inter', sans-serif", fontSize: '13px', fontWeight: 600,
    },
    inviterEmail: {
        fontFamily: "'Inter', sans-serif", fontSize: '11px', opacity: 0.5,
    },
    roleBadge: {
        display: 'inline-block', padding: '4px 10px',
        border: '1px solid #555', fontFamily: "'Inter', sans-serif",
        fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
        marginBottom: '32px',
    },
    btnRow: { display: 'flex', gap: '12px' },
    btnPrimary: {
        flex: 1, padding: '14px', background: '#F0F0F0', color: '#111111',
        border: 'none', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer',
        letterSpacing: '1px',
    },
    btnOutline: {
        flex: 1, padding: '14px', background: 'transparent', color: '#F0F0F0',
        border: '1px solid #555', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer',
        letterSpacing: '1px',
    },
    /* Decorative background text */
    bgTextLarge: {
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        fontFamily: "'Anton', sans-serif", fontSize: 'clamp(80px, 15vw, 200px)',
        textTransform: 'uppercase', color: 'rgba(0,0,0,0.03)',
        whiteSpace: 'nowrap', pointerEvents: 'none', zIndex: 0,
        userSelect: 'none',
    },
    bgTextSide: {
        position: 'absolute', right: '32px', top: '50%',
        transform: 'translateY(-50%) rotate(90deg)',
        fontFamily: "'Bodoni Moda', serif", fontSize: '14px',
        textTransform: 'uppercase', letterSpacing: '4px',
        color: 'rgba(0,0,0,0.06)', whiteSpace: 'nowrap',
        pointerEvents: 'none', zIndex: 0, userSelect: 'none',
    },
    /* Error state */
    errorCard: {
        background: '#111111', color: '#F0F0F0', width: '100%', maxWidth: '440px',
        border: '1px solid #C4342D', padding: '48px 40px', textAlign: 'center',
    },
    errorIcon: {
        fontSize: '48px', marginBottom: '24px', opacity: 0.7,
    },
    errorTitle: {
        fontFamily: "'Anton', sans-serif", fontSize: '28px',
        textTransform: 'uppercase', marginBottom: '12px',
    },
    errorP: {
        fontFamily: "'Inter', sans-serif", fontSize: '13px',
        opacity: 0.6, lineHeight: 1.6, marginBottom: '24px',
    },
    /* Loading state */
    loadingCard: {
        background: '#111111', color: '#F0F0F0', width: '100%', maxWidth: '440px',
        border: '1px solid #333', padding: '60px 40px', textAlign: 'center',
    },
    loadingText: {
        fontFamily: "'Inter', sans-serif", fontSize: '12px',
        textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.5,
    },
};

const TeamInvite = () => {
    usePageTitle('Team Invitation', 'Accept or decline a team invitation.');
    const { token } = useParams();
    const navigate = useNavigate();
    const { addToast } = useToast();
    const { isAuthenticated } = useAuthStore();

    const [invite, setInvite] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [acting, setActing] = useState(false);
    const [done, setDone] = useState(null); // 'accepted' | 'declined'

    /* ── Fetch invitation preview ─────────────────────────────────────── */
    useEffect(() => {
        const fetchInvite = async () => {
            try {
                const { data } = await complianceService.previewInvitation(token);
                setInvite(data);
            } catch (err) {
                const status = err.response?.status;
                if (status === 404) {
                    setError('This invitation was not found. It may have been revoked.');
                } else if (status === 410) {
                    setError('This invitation has expired and is no longer valid.');
                } else {
                    setError(getApiErrorMessage(err, 'Unable to load invitation details.'));
                }
            } finally {
                setLoading(false);
            }
        };
        fetchInvite();
    }, [token]);

    /* ── Actions ──────────────────────────────────────────────────────── */
    const handleAccept = async () => {
        if (!isAuthenticated) {
            addToast('Please log in first to accept this invitation.', 'info');
            navigate(`/auth?redirect=/team/invite/${token}`);
            return;
        }
        setActing(true);
        try {
            await complianceService.acceptInvitation(token);
            setDone('accepted');
            addToast('You have joined the team!', 'success');
            setTimeout(() => navigate('/company/team'), 2000);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to accept invitation.'), 'error');
        } finally {
            setActing(false);
        }
    };

    const handleDecline = async () => {
        if (!isAuthenticated) {
            addToast('Please log in first to decline this invitation.', 'info');
            navigate(`/auth?redirect=/team/invite/${token}`);
            return;
        }
        setActing(true);
        try {
            await complianceService.declineInvitation(token);
            setDone('declined');
            addToast('Invitation declined.', 'info');
            setTimeout(() => navigate('/'), 2000);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to decline invitation.'), 'error');
        } finally {
            setActing(false);
        }
    };

    const inviterInitial = invite?.invited_by_name?.[0]?.toUpperCase() || invite?.invited_by_email?.[0]?.toUpperCase() || '?';
    const roleLabel = invite?.role?.charAt(0).toUpperCase() + invite?.role?.slice(1);

    return (
        <div style={s.body}>
            <TapeBar
                title="TalentOrbit Invitation Gateway"
                status="Security Protocol: Active"
                info={invite ? `Reference: #INV-${token.slice(0, 6).toUpperCase()}` : 'Loading…'}
            />

            {/* Decorative background */}
            <div style={s.bgTextLarge}>Join Team</div>
            <div style={s.bgTextSide}>Membership Portal // Credential Exchange</div>

            <div style={s.container}>
                {/* ── Loading ─────────────────────────── */}
                {loading && (
                    <div style={s.loadingCard}>
                        <div style={s.loadingText}>Verifying invitation…</div>
                    </div>
                )}

                {/* ── Error ──────────────────────────── */}
                {!loading && error && (
                    <div style={s.errorCard}>
                        <div style={s.errorIcon}>✕</div>
                        <h2 style={s.errorTitle}>Invitation Invalid</h2>
                        <p style={s.errorP}>{error}</p>
                        <button
                            style={s.btnPrimary}
                            onClick={() => navigate('/')}
                        >
                            Return Home
                        </button>
                    </div>
                )}

                {/* ── Done state ─────────────────────── */}
                {!loading && !error && done && (
                    <div style={s.loadingCard}>
                        <div style={{ fontSize: '48px', marginBottom: '16px' }}>
                            {done === 'accepted' ? '✓' : '—'}
                        </div>
                        <div style={s.loadingText}>
                            {done === 'accepted' ? 'Welcome to the team! Redirecting…' : 'Invitation declined. Redirecting…'}
                        </div>
                    </div>
                )}

                {/* ── Valid invitation ────────────────── */}
                {!loading && !error && !done && invite && (
                    <div style={s.card}>
                        <div style={s.cardBody}>
                            <div style={s.logoPlaceholder}>
                                {(invite.company_name || invite.team_name || 'T')[0].toUpperCase()}
                            </div>
                            <div style={s.subtitle}>You've been invited to join</div>
                            <h1 style={s.teamName}>{invite.team_name || 'Unnamed Team'}</h1>

                            <div style={s.inviterRow}>
                                <div style={s.inviterAvatar}>{inviterInitial}</div>
                                <div>
                                    <div style={s.inviterName}>
                                        {invite.invited_by_name || invite.invited_by_email || 'Team Admin'}
                                    </div>
                                    <div style={s.inviterEmail}>
                                        {invite.invited_by_email || ''}
                                    </div>
                                </div>
                            </div>

                            <div style={s.roleBadge}>Role: {roleLabel || 'Member'}</div>

                            <div style={s.btnRow}>
                                <button
                                    style={{ ...s.btnPrimary, opacity: acting ? 0.6 : 1 }}
                                    onClick={handleAccept}
                                    disabled={acting}
                                >
                                    {acting ? 'Processing…' : 'Join Team'}
                                </button>
                                <button
                                    style={{ ...s.btnOutline, opacity: acting ? 0.6 : 1 }}
                                    onClick={handleDecline}
                                    disabled={acting}
                                >
                                    Decline
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default TeamInvite;
