import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import Sidebar from '../components/Sidebar';
import TapeBar from '../components/TapeBar';
import { complianceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';

/* ── Design-faithful inline styles (Design 2) ─────────────────────────────── */
const s = {
    tierBadge: {
        display: 'inline-block', padding: '4px 8px', border: '1px solid #000000',
        fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', marginBottom: '12px',
    },
    dashboardGrid: { display: 'grid', gridTemplateColumns: '2fr 1fr', height: '100%' },
    sectionColumn: { borderRight: '1px solid #000000' },
    listHeader: {
        padding: '24px 32px', borderBottom: '1px solid #000000',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    },
    listHeaderH2: { fontFamily: "'Anton', sans-serif", fontSize: '32px', textTransform: 'uppercase' },
    memberRow: {
        display: 'grid', gridTemplateColumns: '48px 1.5fr 1fr 1fr 80px', alignItems: 'center',
        padding: '16px 32px', borderBottom: '1px solid #000000', gap: '16px',
    },
    avatar: {
        width: '32px', height: '32px', background: '#ccc', borderRadius: '50%',
        filter: 'grayscale(100%)', objectFit: 'cover', display: 'flex',
        alignItems: 'center', justifyContent: 'center', fontSize: '14px',
        fontFamily: "'Inter', sans-serif", fontWeight: 700, color: '#555',
        textTransform: 'uppercase', overflow: 'hidden',
    },
    roleBadge: {
        fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', padding: '2px 6px', border: '1px solid #000000', width: 'fit-content',
    },
    inviteSection: { padding: '32px' },
    formGroup: { marginBottom: '20px' },
    formLabel: {
        display: 'block', fontFamily: "'Bodoni Moda', serif", fontSize: '14px',
        textTransform: 'uppercase', marginBottom: '8px',
    },
    inputField: {
        width: '100%', padding: '12px', background: 'transparent',
        border: '1px solid #000000', fontFamily: "'Inter', sans-serif",
        outline: 'none', fontSize: '14px', boxSizing: 'border-box',
    },
    btnBlack: {
        width: '100%', padding: '14px', background: '#111111', color: '#F0F0F0',
        border: 'none', fontFamily: "'Inter', sans-serif", fontSize: '11px',
        fontWeight: 600, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px',
    },
    pendingItem: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 0', borderBottom: '1px solid rgba(0,0,0,0.1)',
    },
    btnSmallText: {
        background: 'none', border: 'none', fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', textDecoration: 'underline', cursor: 'pointer',
        fontFamily: "'Inter', sans-serif",
    },
    verticalLabel: {
        writingMode: 'vertical-rl', textOrientation: 'mixed', transform: 'rotate(180deg)',
        padding: '20px', fontFamily: "'Anton', sans-serif", fontSize: '24px',
        borderLeft: '1px solid #000000', backgroundColor: '#E6E2D8',
        height: '100%', textTransform: 'uppercase',
    },
    /* Role change inline select */
    roleSelect: {
        background: 'transparent', border: '1px solid #000000', padding: '2px 6px',
        fontFamily: "'Inter', sans-serif", fontSize: '10px', fontWeight: 700,
        textTransform: 'uppercase', cursor: 'pointer', outline: 'none',
    },
    /* Empty state card (derived from Design 4 card style) */
    emptyCard: {
        border: '1px solid #000000', padding: '60px 40px', textAlign: 'center',
        maxWidth: '500px', margin: '80px auto',
    },
    emptyTitle: {
        fontFamily: "'Anton', sans-serif", fontSize: '32px', textTransform: 'uppercase',
        marginBottom: '16px',
    },
    emptyP: { fontFamily: "'Inter', sans-serif", fontSize: '13px', opacity: 0.7, lineHeight: 1.6, marginBottom: '24px' },
};

const MemberRow = ({ member, onAction, onRoleChange }) => {
    const [editing, setEditing] = useState(false);
    const [newRole, setNewRole] = useState(member.role);

    // Derive initials from full_name or fall back to email
    const getInitials = () => {
        const name = member.user?.full_name || '';
        if (name.trim()) {
            const parts = name.trim().split(/\s+/);
            return parts.length >= 2
                ? (parts[0][0] + parts[parts.length - 1][0])
                : parts[0][0];
        }
        return member.user?.email?.[0] || '?';
    };
    const initials = getInitials();

    const handleRoleSubmit = () => {
        if (newRole !== member.role) onRoleChange(member.id, newRole);
        setEditing(false);
    };

    return (
        <div style={s.memberRow}>
            <div style={s.avatar}>{initials.toUpperCase()}</div>
            <div>
                <p style={{ fontFamily: "'Bodoni Moda', serif", fontSize: '16px' }}>
                    {member.user?.full_name || member.user?.email || 'Unknown'}
                </p>
                <p style={{ fontSize: '11px', opacity: 0.6 }}>{member.user?.email}</p>
            </div>
            <div>
                {editing && !member.is_owner ? (
                    <select
                        style={s.roleSelect}
                        value={newRole}
                        onChange={(e) => setNewRole(e.target.value)}
                        onBlur={handleRoleSubmit}
                        autoFocus
                    >
                        <option value="admin">Admin</option>
                        <option value="recruiter">Recruiter</option>
                        <option value="viewer">Viewer</option>
                    </select>
                ) : (
                    <div style={s.roleBadge}>
                        {member.role} {member.is_owner && <span style={{ fontSize: '12px', marginLeft: '4px' }}>👑</span>}
                    </div>
                )}
            </div>
            <div style={{ fontSize: '11px', textTransform: 'uppercase' }}>
                {member.joined_at ? new Date(member.joined_at).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }) : '—'}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
                {!member.is_owner && (
                    <>
                        <button style={s.btnSmallText} onClick={() => setEditing(!editing)}>
                            {editing ? 'Save' : 'Edit'}
                        </button>
                        <button style={s.btnSmallText} onClick={() => onAction(member.id)}>Remove</button>
                    </>
                )}
            </div>
        </div>
    );
};

const TeamManagement = () => {
    usePageTitle('Team Management', 'Manage your company team members and invitations.');
    const { addToast } = useToast();
    const { user } = useAuthStore();

    const [loading, setLoading] = useState(true);
    const [team, setTeam] = useState(null);
    const [hasTeam, setHasTeam] = useState(false);
    const [members, setMembers] = useState([]);
    const [pendingInvitations, setPendingInvitations] = useState([]);

    // Invite form
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteRole, setInviteRole] = useState('viewer');
    const [inviteMessage, setInviteMessage] = useState('');
    const [inviteSent, setInviteSent] = useState(false);

    // Create team form
    const [teamName, setTeamName] = useState('');
    const [creating, setCreating] = useState(false);

    /* ── Fetch data ───────────────────────────────────────────────────── */
    const refresh = async () => {
        try {
            const { data } = await complianceService.getTeam();
            setHasTeam(data.has_team);
            setTeam(data.team || null);

            if (data.has_team) {
                const [membersRes, invitesRes] = await Promise.allSettled([
                    complianceService.getTeamMembers(),
                    complianceService.getTeamInvitations(),
                ]);
                if (membersRes.status === 'fulfilled') setMembers(membersRes.value.data.results || membersRes.value.data);
                if (invitesRes.status === 'fulfilled') {
                    const all = invitesRes.value.data.results || invitesRes.value.data;
                    setPendingInvitations(all.filter(i => ['pending', 'expired'].includes(i.status)));
                }
            }
        } catch {
            setHasTeam(false);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { refresh(); }, []);

    /* ── Actions ──────────────────────────────────────────────────────── */
    const handleCreateTeam = async () => {
        setCreating(true);
        try {
            await complianceService.createTeam(teamName || undefined);
            addToast('Team created!', 'success');
            refresh();
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        } finally {
            setCreating(false);
        }
    };

    const handleSendInvitation = async () => {
        if (!inviteEmail) return;
        try {
            await complianceService.inviteMember({ email: inviteEmail, role: inviteRole, message: inviteMessage });
            setInviteSent(true);
            addToast('Invitation sent!', 'success');
            setInviteEmail(''); setInviteMessage(''); setInviteRole('viewer');
            setTimeout(() => setInviteSent(false), 2500);
            refresh();
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        }
    };

    const handleRemoveMember = async (id) => {
        if (!window.confirm('Remove this team member?')) return;
        try {
            await complianceService.removeMember(id);
            addToast('Member removed.', 'success');
            setMembers(prev => prev.filter(m => m.id !== id));
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        }
    };

    const handleRoleChange = async (id, role) => {
        try {
            await complianceService.changeMemberRole(id, role);
            addToast('Role updated.', 'success');
            setMembers(prev => prev.map(m => m.id === id ? { ...m, role } : m));
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        }
    };

    const handleRevoke = async (id) => {
        try {
            await complianceService.revokeInvitation(id);
            addToast('Invitation revoked.', 'success');
            setPendingInvitations(prev => prev.filter(i => i.id !== id));
        } catch (err) {
            addToast(getApiErrorMessage(err), 'error');
        }
    };

    const seatText = team ? `${team.current_seat_count} / ${team.max_seats} Seats Utilized` : '';
    const tierText = user?.subscription_tier || 'Free';

    return (
        <>
            <a href="#main-content" className="skip-link">Skip to content</a>
            <TapeBar
                title="TalentOrbit Admin Console v2.1"
                status={`Auth Session: ${user?.email || ''}`}
                info={team ? `Seats: ${String(team.current_seat_count).padStart(2, '0')} / ${team.max_seats} Active` : 'No Team'}
            />
            <div className="app-container">
                <Sidebar />
                <main id="main-content" className="main-content" tabIndex={-1}>
                    {loading ? (
                        <div style={{ padding: '80px 40px', textAlign: 'center', opacity: 0.5, fontFamily: "'Inter', sans-serif", fontSize: '14px', textTransform: 'uppercase' }}>
                            Loading team data…
                        </div>
                    ) : !hasTeam ? (
                        /* ── Empty state: Create Team ─────────────── */
                        <>
                            <header className="content-header">
                                <h1 className="page-title">Team<br />Studio</h1>
                            </header>
                            <div style={s.emptyCard}>
                                <h2 style={s.emptyTitle}>Create Your Team</h2>
                                <p style={s.emptyP}>
                                    Set up your company team to invite recruiters, admins, and viewers.
                                    Manage access and collaborate on hiring.
                                </p>
                                <div style={s.formGroup}>
                                    <input
                                        style={s.inputField}
                                        placeholder="Team name (optional)"
                                        value={teamName}
                                        onChange={(e) => setTeamName(e.target.value)}
                                    />
                                </div>
                                <button
                                    style={{ ...s.btnBlack, opacity: creating ? 0.6 : 1 }}
                                    onClick={handleCreateTeam}
                                    disabled={creating}
                                >
                                    {creating ? 'Creating…' : 'Create Team'}
                                </button>
                            </div>
                        </>
                    ) : (
                        /* ── Full Team UI ─────────────────────────── */
                        <>
                            <header className="content-header">
                                <div>
                                    <span style={s.tierBadge}>{tierText} Tier</span>
                                    <h1 className="page-title">Team<br />Studio</h1>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <h3 style={{ fontFamily: "'Bodoni Moda', serif", textTransform: 'uppercase', fontSize: '14px' }}>
                                        {team.company_name || team.name}
                                    </h3>
                                    <p style={{ fontSize: '12px', opacity: 0.7 }}>{seatText}</p>
                                </div>
                            </header>

                            <div style={s.dashboardGrid}>
                                {/* ── Left Column: Members ────────── */}
                                <div style={s.sectionColumn}>
                                    <div style={s.listHeader}>
                                        <h2 style={s.listHeaderH2}>Active Members</h2>
                                    </div>
                                    <div>
                                        {members.length === 0 ? (
                                            <div style={{ padding: '32px', opacity: 0.5, fontFamily: "'Inter', sans-serif", fontSize: '13px' }}>
                                                No team members yet.
                                            </div>
                                        ) : members.map(member => (
                                            <MemberRow
                                                key={member.id}
                                                member={member}
                                                onAction={handleRemoveMember}
                                                onRoleChange={handleRoleChange}
                                            />
                                        ))}
                                    </div>
                                </div>

                                {/* ── Right Column: Invite + Pending ── */}
                                <div style={{ borderRight: 'none', display: 'flex' }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={s.listHeader}>
                                            <h2 style={s.listHeaderH2}>Invite</h2>
                                        </div>
                                        <div style={s.inviteSection}>
                                            <div style={s.formGroup}>
                                                <label style={s.formLabel}>Email Address</label>
                                                <input
                                                    type="email"
                                                    style={s.inputField}
                                                    placeholder="colleague@domain.com"
                                                    value={inviteEmail}
                                                    onChange={e => setInviteEmail(e.target.value)}
                                                />
                                            </div>
                                            <div style={s.formGroup}>
                                                <label style={s.formLabel}>Access Role</label>
                                                <select
                                                    style={s.inputField}
                                                    value={inviteRole}
                                                    onChange={e => setInviteRole(e.target.value)}
                                                >
                                                    <option value="viewer">Viewer</option>
                                                    <option value="recruiter">Recruiter</option>
                                                    <option value="admin">Admin</option>
                                                </select>
                                            </div>
                                            <div style={s.formGroup}>
                                                <label style={s.formLabel}>Personal Message (Optional)</label>
                                                <textarea
                                                    style={{ ...s.inputField, height: '80px', resize: 'none' }}
                                                    value={inviteMessage}
                                                    onChange={e => setInviteMessage(e.target.value)}
                                                />
                                            </div>
                                            <button
                                                style={{ ...s.btnBlack, opacity: inviteSent ? 0.7 : 1 }}
                                                onClick={handleSendInvitation}
                                            >
                                                {inviteSent ? 'Invitation Sent ✓' : 'Send Invitation'}
                                            </button>

                                            {/* ── Pending Invitations ──── */}
                                            <div style={{ marginTop: '48px' }}>
                                                <h4 style={{
                                                    fontFamily: "'Bodoni Moda', serif", textTransform: 'uppercase',
                                                    fontSize: '12px', marginBottom: '16px',
                                                    borderBottom: '1px solid #000000', paddingBottom: '8px',
                                                }}>
                                                    Pending Invitations
                                                </h4>
                                                {pendingInvitations.length === 0 ? (
                                                    <p style={{ fontSize: '12px', opacity: 0.5 }}>No pending invitations.</p>
                                                ) : pendingInvitations.map(invite => (
                                                    <div key={invite.id} style={s.pendingItem}>
                                                        <div>
                                                            <p style={{ fontSize: '13px' }}>{invite.email}</p>
                                                            <p style={{
                                                                fontSize: '10px',
                                                                color: invite.status === 'expired' ? '#b71c1c' : 'rgba(0,0,0,0.5)',
                                                                textTransform: 'uppercase',
                                                            }}>
                                                                Status: {invite.status}
                                                            </p>
                                                        </div>
                                                        <button
                                                            style={s.btnSmallText}
                                                            onClick={() => handleRevoke(invite.id)}
                                                        >
                                                            {invite.status === 'expired' ? 'Resend' : 'Revoke'}
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                    <div style={s.verticalLabel}>Management // Access Control</div>
                                </div>
                            </div>
                        </>
                    )}
                </main>
            </div>
        </>
    );
};

export default TeamManagement;
