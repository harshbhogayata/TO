import { useState } from 'react';
import TapeBar from '../components/TapeBar';
import { authService, getApiErrorMessage } from '../services/api';
import { useNavigate } from 'react-router-dom';
import './PasswordRecovery.css';

const PasswordRecovery = () => {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [step1Sent, setStep1Sent] = useState(false);
    const [step1Loading, setStep1Loading] = useState(false);
    const [step1Error, setStep1Error] = useState('');

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
                                NOT YET AVAILABLE
                            </span>
                            <p style={{ fontSize: '11px', opacity: 0.6, textTransform: 'uppercase' }}>
                                Email-based password reset coming soon
                            </p>
                        </div>
                    </header>

                    <div style={{ padding: '16px 32px', background: 'rgba(180,120,0,0.06)', borderBottom: '1px solid rgba(180,120,0,0.2)', fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', color: '#886600' }}>
                        ⚠ Password reset via email is not yet active. To change your password, log in and visit Settings → Change Password. For locked accounts, contact support.
                    </div>

                    <div className="recovery-flow">
                        {/* Step 01 — Email Request */}
                        <div className="flow-section">
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

                        {/* Step 02 — Placeholder */}
                        <div className="right-container">
                            <div className="flow-section" style={{ flex: 1, borderRight: 'none' }}>
                                <span className="step-indicator">[ Step 02 / Credential Update ]</span>
                                <h2 className="section-heading">New Cipher</h2>

                                <div style={{ padding: '32px 0', fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase', lineHeight: 1.8 }}>
                                    This step is completed via the<br />secure link in your email.<br /><br />
                                    Follow the link to set a new password.
                                </div>

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
