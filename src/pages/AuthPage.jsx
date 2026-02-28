import { useState, useEffect } from 'react';
import TapeBar from '../components/TapeBar';
import VerticalLabel from '../components/VerticalLabel';
import { useNavigate, useLocation } from 'react-router-dom';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import './AuthPage.css';

const AuthPage = () => {
    const [registerAsCompany, setRegisterAsCompany] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const navigate = useNavigate();
    const location = useLocation();
    const { setAuth, user, isAuthenticated } = useAuthStore();

    // If already authenticated, redirect to correct dashboard
    useEffect(() => {
        if (isAuthenticated && user) {
            const dashboardMap = { TALENT: '/user', COMPANY: '/company', ADMIN: '/admin' };
            navigate(dashboardMap[user.role] || '/', { replace: true });
        }
    }, [isAuthenticated, user, navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const { data } = await authService.loginUser(email, password);
            setAuth(data.user, data.access, data.refresh);

            // Navigate to the page they originally tried to access, or their dashboard
            const from = location.state?.from?.pathname;
            const dashboardMap = { TALENT: '/user', COMPANY: '/company', ADMIN: '/admin' };
            navigate(from || dashboardMap[data.user.role] || '/', { replace: true });
        } catch (err) {
            setError(getApiErrorMessage(err, 'Invalid credentials. Please try again.'));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <TapeBar
                title="TalentOrbit Auth Portal v2.1"
                status="Security: Encrypted"
                info="Access Point: Node_01"
            />
            <div className="login-layout">
                <div className="login-branding">
                    <div className="brand-large">
                        Talent<br />Orbit
                    </div>

                    <div className="footer-branding">
                        <div>
                            <div className="brand-sub">The Future of Workforce</div>
                            <div style={{ fontSize: '10px', marginTop: '8px', opacity: 0.6, fontFamily: 'var(--font-sans)', textTransform: 'uppercase' }}>
                                © {new Date().getFullYear()} TalentOrbit Infrastructure
                            </div>
                        </div>
                        <VerticalLabel text="System_Interface_Access" />
                    </div>
                </div>

                <div className="login-form-container">
                    <div className="login-header">
                        <h2>User<br />Access</h2>
                    </div>

                    <div className="role-selector">
                        <button
                            type="button"
                            className={`role-btn ${!registerAsCompany ? 'active' : ''}`}
                            onClick={() => setRegisterAsCompany(false)}
                        >Talent / User</button>
                        <button
                            type="button"
                            className={`role-btn ${registerAsCompany ? 'active' : ''}`}
                            onClick={() => setRegisterAsCompany(true)}
                        >Company</button>
                    </div>

                    {error && (
                        <div style={{
                            background: 'rgba(200,0,0,0.08)',
                            border: '1px solid rgba(200,0,0,0.3)',
                            padding: '12px 16px',
                            marginBottom: '16px',
                            fontFamily: 'var(--font-sans)',
                            fontSize: '11px',
                            color: '#b00',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                        }}>
                            ⚠ {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label className="form-label">Identification / Email</label>
                            <input
                                type="email"
                                className="form-input"
                                placeholder="Enter credentials..."
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                autoComplete="email"
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Security Key / Password</label>
                            <input
                                type="password"
                                className="form-input"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                autoComplete="current-password"
                            />
                        </div>

                        <button
                            type="submit"
                            className="login-btn"
                            disabled={isLoading}
                            style={{ opacity: isLoading ? 0.7 : 1, cursor: isLoading ? 'not-allowed' : 'pointer' }}
                        >
                            {isLoading ? 'Authenticating...' : 'Authenticate'}
                        </button>
                    </form>

                    <div className="form-footer">
                        <span
                            className="link-text"
                            onClick={() => navigate('/recovery')}
                            style={{ cursor: 'pointer' }}
                        >
                            Forgot Credentials?
                        </span>
                        <span>
                            Request Access — <span
                                className="link-text"
                                style={{ cursor: 'pointer' }}
                                onClick={() => registerAsCompany ? navigate('/register/company') : navigate('/register/user')}
                            >
                                Register
                            </span>
                        </span>
                    </div>
                </div>
            </div>
        </>
    );
};

export default AuthPage;
