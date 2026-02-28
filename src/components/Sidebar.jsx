import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authService } from '../services/api';

const defaultTalentNav = [
    [
        { num: '01', label: 'My Dashboard', path: '/user' },
        { num: '02', label: 'Job Search', path: '/jobs' },
        { num: '03', label: 'Skill Hub', path: '/skills' },
        { num: '04', label: 'Applications', path: '/applications' },
        { num: '05', label: 'Saved Jobs', path: '/saved' },
        { num: '06', label: 'Messages', path: '/inbox' }
    ],
    [
        { num: '07', label: 'Notifications', path: '/notifications' },
        { num: '08', label: 'Profile', path: '/profile' },
        { num: '09', label: 'Settings', path: '/settings' }
    ]
];

const defaultCompanyNav = [
    [
        { num: '01', label: 'Company Hub', path: '/company' },
        { num: '02', label: 'Post a Job', path: '/company/post-job' },
        { num: '03', label: 'Job Board', path: '/jobs' },
        { num: '04', label: 'Company Profile', path: '/company/profile' },
        { num: '05', label: 'Messages', path: '/inbox' }
    ],
    [
        { num: '06', label: 'Notifications', path: '/notifications' },
        { num: '07', label: 'Settings', path: '/settings' }
    ]
];

const defaultAdminNav = [
    [
        { num: '01', label: 'Admin Console', path: '/admin' },
        { num: '02', label: 'Job Board', path: '/jobs' },
        { num: '03', label: 'Messages', path: '/inbox' },
        { num: '04', label: 'Notifications', path: '/notifications' },
        { num: '05', label: 'About', path: '/about' }
    ],
    [
        { num: '06', label: 'Settings', path: '/settings' }
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

            <aside className={`sidebar ${mobileOpen ? 'sidebar-mobile-open' : ''}`} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div
                    className="brand"
                    style={{ cursor: 'pointer' }}
                    onClick={() => { navigate('/'); setMobileOpen(false); }}
                >
                    Talent<br />Orbit
                </div>

                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {activeNav && activeNav.map((group, gIndex) => (
                        <nav key={gIndex} className="nav-group">
                            {group.map((item, index) => {
                                const isActive = location.pathname === item.path;
                                return (
                                    <div
                                        key={index}
                                        className={`nav-item ${isActive ? 'active' : ''}`}
                                        onClick={() => { navigate(item.path); setMobileOpen(false); }}
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
