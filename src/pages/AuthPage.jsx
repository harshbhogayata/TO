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

    // 2FA state
    const [twoFARequired, setTwoFARequired] = useState(false);
    const [tempToken, setTempToken] = useState('');
    const [totpCode, setTotpCode] = useState('');

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

    const redirectAfterLogin = (role) => {
        const from = location.state?.from?.pathname;
        const dashboardMap = { TALENT: '/user', COMPANY: '/company', ADMIN: '/admin' };
        navigate(from || dashboardMap[role] || '/', { replace: true });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const { data } = await authService.loginUser(email, password);

            // Check if 2FA is required
            if (data.requires_2fa) {
                setTempToken(data.temp_token);
                setTwoFARequired(true);
                return;
            }

            setAuth(data.user, data.access, data.refresh);
            redirectAfterLogin(data.user.role);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Invalid credentials. Please try again.'));
        } finally {
            setIsLoading(false);
        }
    };

    const handle2FASubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const { data } = await authService.login2FA(tempToken, totpCode);
            setAuth(data.user, data.access, data.refresh);
            redirectAfterLogin(data.user.role);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Invalid 2FA code. Please try again.'));
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

                    <form onSubmit={twoFARequired ? handle2FASubmit : handleSubmit}>
                        {!twoFARequired ? (
                            <>
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
                            </>
                        ) : (
                            <div className="form-group">
                                <label className="form-label">2FA Verification Code</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    placeholder="Enter 6-digit code..."
                                    value={totpCode}
                                    onChange={(e) => setTotpCode(e.target.value)}
                                    required
                                    autoComplete="one-time-code"
                                    maxLength={6}
                                    inputMode="numeric"
                                    pattern="[0-9]*"
                                />
                                <p style={{ fontSize: '10px', opacity: 0.5, marginTop: '8px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase' }}>
                                    Enter the code from your authenticator app
                                </p>
                            </div>
                        )}

                        <button
                            type="submit"
                            className="login-btn"
                            disabled={isLoading}
                            style={{ opacity: isLoading ? 0.7 : 1, cursor: isLoading ? 'not-allowed' : 'pointer' }}
                        >
                            {isLoading ? 'Authenticating...' : twoFARequired ? 'Verify Code' : 'Authenticate'}
                        </button>
                    </form>

                    <div className="form-footer">
                        {twoFARequired ? (
                            <span
                                className="link-text"
                                onClick={() => { setTwoFARequired(false); setTempToken(''); setTotpCode(''); setError(''); }}
                                style={{ cursor: 'pointer' }}
                            >
                                ← Back to Login
                            </span>
                        ) : (
                            <span
                                className="link-text"
                                onClick={() => navigate('/recovery')}
                                style={{ cursor: 'pointer' }}
                            >
                                Forgot Credentials?
                            </span>
                        )}
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
