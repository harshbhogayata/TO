import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authService } from '../services/api';

const defaultTalentNav = [
    [
        { num: '01', label: 'My Dashboard', path: '/user' },
        { num: '02', label: 'Job Search', path: '/jobs' },
        { num: '03', label: 'AI Recommendations', path: '/recommendations' },
        { num: '04', label: 'Skill Hub', path: '/skills' },
        { num: '05', label: 'Applications', path: '/applications' },
        { num: '06', label: 'Saved Jobs', path: '/saved' },
        { num: '07', label: 'Messages', path: '/inbox' }
    ],
    [
        { num: '08', label: 'Courses', path: '/courses' },
        { num: '09', label: 'My Learning', path: '/my-learning' },
        { num: '10', label: 'Assessments', path: '/assessments' },
        { num: '11', label: 'My Assessments', path: '/my-assessments' },
        { num: '12', label: 'Skill Badges', path: '/badges' }
    ],
    [
        { num: '13', label: 'Resume Parser', path: '/resume-parser' },
        { num: '14', label: 'Skill Browser', path: '/skills/taxonomy' },
        { num: '15', label: 'Notifications', path: '/notifications' },
        { num: '16', label: 'Profile', path: '/profile' },
        { num: '17', label: 'Settings', path: '/settings' },
        { num: '18', label: 'Privacy Center', path: '/privacy-center' },
        { num: '19', label: 'Company Reviews', path: '/reviews' }
    ],
    [
        { num: '20', label: 'Billing', path: '/billing' },
        { num: '21', label: 'Plans', path: '/plans' },
        { num: '22', label: 'Referrals', path: '/referrals' },
        { num: '23', label: 'Company Directory', path: '/companies' },
        { num: '24', label: 'Compensation Data', path: '/compensation' }
    ]
];

const defaultCompanyNav = [
    [
        { num: '01', label: 'Company Hub', path: '/company' },
        { num: '02', label: 'Analytics', path: '/company/analytics' },
        { num: '03', label: 'Post a Job', path: '/company/post-job' },
        { num: '04', label: 'Job Board', path: '/jobs' },
        { num: '05', label: 'Company Profile', path: '/company/profile' },
        { num: '06', label: 'Messages', path: '/inbox' }
    ],
    [
        { num: '07', label: 'Assessments', path: '/company/assessments' },
        { num: '08', label: 'Question Banks', path: '/company/question-banks' },
        { num: '09', label: 'Course Catalog', path: '/courses' },
        { num: '10', label: 'Reviews', path: '/reviews' },
        { num: '11', label: 'Developer Portal', path: '/company/developer' },
        { num: '12', label: 'API Keys', path: '/company/api-keys' },
        { num: '13', label: 'Webhooks', path: '/company/webhooks' },
        { num: '14', label: 'OAuth Apps', path: '/company/oauth-apps' },
        { num: '15', label: 'Team', path: '/company/team' },
        { num: '16', label: 'Skill Browser', path: '/skills/taxonomy' },
        { num: '17', label: 'Notifications', path: '/notifications' },
        { num: '18', label: 'Settings', path: '/settings' },
        { num: '19', label: 'Privacy Center', path: '/privacy-center' }
    ],
    [
        { num: '20', label: 'Billing', path: '/billing' },
        { num: '21', label: 'Plans', path: '/plans' },
        { num: '22', label: 'Referrals', path: '/referrals' },
        { num: '23', label: 'Sponsored Posts', path: '/company/sponsored' },
        { num: '24', label: 'CRM Pipeline', path: '/company/crm' },
        { num: '25', label: 'AI Job Writer', path: '/company/ai-job-writer' },
        { num: '26', label: 'Interviews', path: '/company/interviews' },
        { num: '27', label: 'Talent Search', path: '/talent-search' },
        { num: '28', label: 'Compensation Data', path: '/compensation' },
        { num: '29', label: 'Company Directory', path: '/companies' }
    ]
];

const defaultAdminNav = [
    [
        { num: '01', label: 'Admin Console', path: '/admin' },
        { num: '02', label: 'Platform Analytics', path: '/admin/analytics' },
        { num: '03', label: 'Job Board', path: '/jobs' },
        { num: '04', label: 'Messages', path: '/inbox' },
        { num: '05', label: 'Notifications', path: '/notifications' },
        { num: '06', label: 'About', path: '/about' }
    ],
    [
        { num: '07', label: 'Audit Log', path: '/admin/audit-log' },
        { num: '08', label: 'Skill Browser', path: '/skills/taxonomy' },
        { num: '09', label: 'Settings', path: '/settings' },
        { num: '10', label: 'Privacy Center', path: '/privacy-center' }
    ],
    [
        { num: '11', label: 'Revenue Dashboard', path: '/admin/revenue' },
        { num: '12', label: 'Feature Flags', path: '/admin/feature-flags' },
        { num: '13', label: 'Policy Manager', path: '/admin/policies' },
        { num: '14', label: 'Talent Search', path: '/talent-search' },
        { num: '15', label: 'Compensation Data', path: '/compensation' },
        { num: '16', label: 'Company Directory', path: '/companies' }
    ]
];

const Sidebar = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, isAuthenticated, logout, refreshToken } = useAuthStore();
    const [mobileOpen, setMobileOpen] = useState(false);

    let activeNav = null;
    if (user) {
        if (user.role === 'TALENT') activeNav = defaultTalentNav;
        else if (user.role === 'COMPANY') activeNav = defaultCompanyNav;
        else if (user.role === 'ADMIN') activeNav = defaultAdminNav;
    }

    const handleLogout = async () => {
        try {
            if (refreshToken) {
                await authService.logout(refreshToken);
            }
        } catch {
            // Logout API failure is non-critical; proceed with local cleanup
        } finally {
            logout();
            navigate('/auth', { replace: true });
        }
    };

    return (
        <>
            {/* Mobile hamburger */}
            <button
                className="sidebar-hamburger"
                onClick={() => setMobileOpen(v => !v)}
                aria-label="Toggle navigation"
            >
                {mobileOpen ? '✕' : '☰'}
            </button>

            {/* Overlay for mobile */}
            {mobileOpen && (
                <div
                    className="sidebar-overlay"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            <aside className={`sidebar ${mobileOpen ? 'sidebar-mobile-open' : ''}`} role="navigation" aria-label="Main navigation" style={{ display: 'flex', flexDirection: 'column' }}>
                <div
                    className="brand"
                    style={{ cursor: 'pointer' }}
                    onClick={() => { navigate('/'); setMobileOpen(false); }}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate('/'); setMobileOpen(false); } }}
                    tabIndex={0}
                    role="link"
                    aria-label="TalentOrbit home"
                >
                    Talent<br />Orbit
                </div>

                {/* User avatar + name */}
                {user && (
                    <div
                        style={{
                            display: 'flex', alignItems: 'center', gap: '12px',
                            padding: '0 24px 20px', borderBottom: '1px solid var(--border-light)',
                            marginBottom: '8px', cursor: 'pointer',
                        }}
                        onClick={() => { navigate(user.role === 'COMPANY' ? '/company/profile' : '/profile'); setMobileOpen(false); }}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(user.role === 'COMPANY' ? '/company/profile' : '/profile'); setMobileOpen(false); } }}
                        tabIndex={0}
                        role="link"
                        aria-label={`${user.full_name || 'User'} profile`}
                    >
                        <div style={{
                            width: '36px', height: '36px', borderRadius: '50%',
                            border: '1px solid var(--border-light)', overflow: 'hidden',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: 'rgba(255,255,255,0.08)', flexShrink: 0,
                            fontSize: '14px', fontFamily: 'var(--font-serif)', fontWeight: 700,
                            color: 'var(--text-white)', textTransform: 'uppercase',
                        }}>
                            {user.avatar ? (
                                <img src={user.avatar} alt={`${user.full_name || 'User'} avatar`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (user.full_name || user.email || '?').charAt(0).toUpperCase()}
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                            <div style={{
                                fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 700,
                                color: 'var(--text-white)', textTransform: 'uppercase', letterSpacing: '1px',
                                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            }}>
                                {user.full_name || 'User'}
                            </div>
                            <div style={{
                                fontFamily: 'var(--font-sans)', fontSize: '10px',
                                color: 'var(--text-white)', opacity: 0.5,
                                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            }}>
                                {user.role === 'COMPANY' ? 'Company' : user.role === 'ADMIN' ? 'Admin' : 'Talent'}
                            </div>
                        </div>
                    </div>
                )}

                <div className="sidebar-nav-shell">
                    {activeNav && activeNav.map((group, gIndex) => (
                        <nav key={gIndex} className="nav-group" role="list">
                            {group.map((item, index) => {
                                const isActive = item.path === '/'
                                    ? location.pathname === '/'
                                    : location.pathname === item.path || location.pathname.startsWith(item.path + '/');
                                return (
                                    <div
                                        key={index}
                                        className={`nav-item ${isActive ? 'active' : ''}`}
                                        onClick={() => { navigate(item.path); setMobileOpen(false); }}
                                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(item.path); setMobileOpen(false); } }}
                                        tabIndex={0}
                                        role="listitem"
                                        aria-current={isActive ? 'page' : undefined}
                                    >
                                        <span className="nav-num">[{item.num}]</span>
                                        <span className="nav-label">{item.label}</span>
                                    </div>
                                );
                            })}
                        </nav>
                    ))}
                </div>

                {isAuthenticated && (
                    <div style={{ padding: '24px', borderTop: '1px solid var(--border-light)', marginTop: 'auto' }}>
                        <button
                            onClick={handleLogout}
                            style={{
                                background: 'transparent', color: 'var(--text-white)', border: '1px solid var(--border-light)',
                                padding: '12px 24px', fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 700,
                                textTransform: 'uppercase', width: '100%', cursor: 'pointer', letterSpacing: '1px'
                            }}
                        >
                            End Session
                        </button>
                    </div>
                )}
            </aside>
        </>
    );
};

export default Sidebar;
