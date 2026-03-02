import { useState, useMemo } from 'react';
import TapeBar from '../components/TapeBar';
import { authService, getApiErrorMessage } from '../services/api';
import { useNavigate, useSearchParams } from 'react-router-dom';
import usePageTitle from '../hooks/usePageTitle';
import './PasswordRecovery.css';

const PasswordRecovery = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    usePageTitle('Password Recovery', 'Reset your TalentOrbit password securely via email.');

    // Detect if we're in "confirm" mode (arrived via email link)
    const uid = searchParams.get('uid');
    const token = searchParams.get('token');
    const isConfirmMode = useMemo(() => Boolean(uid && token), [uid, token]);

    // Step 1 — Request reset
    const [email, setEmail] = useState('');
    const [step1Sent, setStep1Sent] = useState(false);
    const [step1Loading, setStep1Loading] = useState(false);
    const [step1Error, setStep1Error] = useState('');

    // Step 2 — Confirm reset
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [step2Loading, setStep2Loading] = useState(false);
    const [step2Error, setStep2Error] = useState('');
    const [step2Success, setStep2Success] = useState(false);

    const handleRequestReset = async (e) => {
        e.preventDefault();
        setStep1Loading(true);
        setStep1Error('');
        try {
            await authService.requestPasswordReset(email);
            setStep1Sent(true);
        } catch (err) {
            setStep1Error(getApiErrorMessage(err, 'Request failed. Please try again.'));
        } finally {
            setStep1Loading(false);
        }
    };

    const handleConfirmReset = async (e) => {
        e.preventDefault();
        setStep2Error('');
        if (newPassword.length < 8) {
            setStep2Error('Password must be at least 8 characters.');
            return;
        }
        if (newPassword !== confirmPassword) {
            setStep2Error('Passwords do not match.');
            return;
        }
        setStep2Loading(true);
        try {
            await authService.confirmPasswordReset(uid, token, newPassword);
            setStep2Success(true);
        } catch (err) {
            setStep2Error(getApiErrorMessage(err, 'Reset failed. The link may have expired.'));
        } finally {
            setStep2Loading(false);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
            <TapeBar
                title="TalentOrbit // Password Recovery"
                status="System Status: Operational"
                info="Security Protocol: Active"
            />

            <div className="recovery-app-container">
                <aside className="recovery-sidebar">
                    <div className="recovery-brand">Talent<br />Orbit</div>
                    <div style={{ marginTop: 'auto', fontSize: '10px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', opacity: 0.4 }}>
                        Secure Recovery<br />Protocol 02
                    </div>
                </aside>

                <main className="recovery-main">
                    <header className="recovery-header">
                        <h1 className="recovery-title">Access<br />Reset</h1>
                        <div style={{ textAlign: 'right' }}>
                            <span style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase', fontSize: '14px' }}>
                                {isConfirmMode ? 'SET NEW PASSWORD' : 'RECOVERY PROTOCOL'}
                            </span>
                            <p style={{ fontSize: '11px', opacity: 0.6, textTransform: 'uppercase' }}>
                                {isConfirmMode ? 'Enter your new credentials below' : 'Email-based secure password reset'}
                            </p>
                        </div>
                    </header>

                    <div className="recovery-flow">
                        {/* Step 01 — Email Request */}
                        <div className="flow-section" style={isConfirmMode ? { opacity: 0.3, pointerEvents: 'none' } : {}}>
                            <span className="step-indicator">[ Step 01 / Identity Verification ]</span>
                            <h2 className="section-heading">Email Address</h2>

                            {!step1Sent ? (
                                <form onSubmit={handleRequestReset} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                    <div className="form-group">
                                        <label className="form-label">Registered Email</label>
                                        <p style={{ fontSize: '11px', marginBottom: '12px', textTransform: 'uppercase', opacity: 0.6 }}>
                                            A reset link will be dispatched to this address.
                                        </p>
                                        <input
                                            type="email"
                                            className="recovery-input"
                                            placeholder="YOUR@EMAIL.COM"
                                            value={email}
                                            onChange={e => setEmail(e.target.value)}
                                            required
                                            autoComplete="email"
                                        />
                                    </div>

                                    {step1Error && (
                                        <p style={{ color: '#b00', fontSize: '11px', textTransform: 'uppercase' }}>⚠ {step1Error}</p>
                                    )}

                                    <button
                                        type="submit"
                                        className="btn-action-recovery"
                                        disabled={step1Loading}
                                        style={{ opacity: step1Loading ? 0.6 : 1, cursor: step1Loading ? 'not-allowed' : 'pointer' }}
                                    >
                                        {step1Loading ? 'Dispatching...' : 'Send Reset Link'}
                                    </button>

                                    <div className="security-note">
                                        // WARNING: Multiple failed attempts will result in a 24-hour hardware lockout. System logs all recovery attempts for auditing.
                                    </div>
                                </form>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '20px' }}>
                                    <div style={{ padding: '24px', border: '1px solid var(--border-color)', background: 'rgba(0,80,0,0.04)' }}>
                                        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase', marginBottom: '12px' }}>
                                            ✓ Link Dispatched
                                        </p>
                                        <p style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', lineHeight: 1.6, opacity: 0.7 }}>
                                            If an account exists for <strong>{email}</strong>, a password reset link has been sent. Please check your inbox and spam folder. The link will expire in 15 minutes.
                                        </p>
                                    </div>
                                    <button
                                        className="btn-action-recovery"
                                        onClick={() => { setStep1Sent(false); setEmail(''); }}
                                        style={{ background: 'transparent', color: 'var(--text-black)' }}
                                    >
                                        Try Different Email
                                    </button>
                                </div>
                            )}

                            <div style={{ marginTop: '40px' }}>
                                <span
                                    onClick={() => navigate('/auth')}
                                    style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', textDecoration: 'underline', cursor: 'pointer', opacity: 0.5 }}
                                >
                                    ← Return to Login
                                </span>
                            </div>
                        </div>

                        {/* Step 02 — Confirm New Password */}
                        <div className="right-container">
                            <div className="flow-section" style={{ flex: 1, borderRight: 'none', ...(isConfirmMode ? {} : { opacity: 0.3, pointerEvents: 'none' }) }}>
                                <span className="step-indicator">[ Step 02 / Credential Update ]</span>
                                <h2 className="section-heading">New Cipher</h2>

                                {step2Success ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '20px' }}>
                                        <div style={{ padding: '24px', border: '1px solid var(--border-color)', background: 'rgba(0,80,0,0.04)' }}>
                                            <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase', marginBottom: '12px' }}>
                                                ✓ Password Reset Complete
                                            </p>
                                            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', lineHeight: 1.6, opacity: 0.7 }}>
                                                Your password has been updated. You can now log in with your new credentials.
                                            </p>
                                        </div>
                                        <button className="btn-action-recovery" onClick={() => navigate('/auth')}>
                                            Go to Login
                                        </button>
                                    </div>
                                ) : isConfirmMode ? (
                                    <form onSubmit={handleConfirmReset} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                                        <div className="form-group">
                                            <label className="form-label">New Password</label>
                                            <input
                                                type="password"
                                                className="recovery-input"
                                                placeholder="MIN 8 CHARACTERS"
                                                value={newPassword}
                                                onChange={e => setNewPassword(e.target.value)}
                                                required
                                                minLength={8}
                                                autoComplete="new-password"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label className="form-label">Confirm Password</label>
                                            <input
                                                type="password"
                                                className="recovery-input"
                                                placeholder="RE-ENTER PASSWORD"
                                                value={confirmPassword}
                                                onChange={e => setConfirmPassword(e.target.value)}
                                                required
                                                minLength={8}
                                                autoComplete="new-password"
                                            />
                                        </div>

                                        {step2Error && (
                                            <p style={{ color: '#b00', fontSize: '11px', textTransform: 'uppercase' }}>⚠ {step2Error}</p>
                                        )}

                                        <button
                                            type="submit"
                                            className="btn-action-recovery"
                                            disabled={step2Loading}
                                            style={{ opacity: step2Loading ? 0.6 : 1, cursor: step2Loading ? 'not-allowed' : 'pointer' }}
                                        >
                                            {step2Loading ? 'Resetting...' : 'Set New Password'}
                                        </button>
                                    </form>
                                ) : (
                                    <div style={{ padding: '32px 0', fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase', lineHeight: 1.8 }}>
                                        This step is completed via the<br />secure link in your email.<br /><br />
                                        Follow the link to set a new password.
                                    </div>
                                )}

                                <div style={{ marginTop: '60px' }}>
                                    <span className="form-label" style={{ fontSize: '10px', opacity: 0.5 }}>Requirements</span>
                                    <ul style={{ listStyle: 'none', fontSize: '11px', textTransform: 'uppercase', marginTop: '10px' }}>
                                        <li style={{ marginBottom: '6px' }}>+ Min 8 Characters</li>
                                        <li style={{ marginBottom: '6px' }}>+ Contains Number or Symbol</li>
                                        <li style={{ marginBottom: '6px' }}>+ No Historical Matches</li>
                                    </ul>
                                </div>
                            </div>

                            <div className="vertical-sidebar">
                                System Recovery // Auth_02
                            </div>
                        </div>
                    </div>
                </main>
            </div>
        </div>
    );
};

export default PasswordRecovery;
