import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { useNavigate } from 'react-router-dom';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';
import './Settings.css';

const Settings = () => {
    usePageTitle('Settings', 'Manage your TalentOrbit account settings, security, and preferences.');
    const { addToast } = useToast();
    const navigate = useNavigate();
    const { logout, refreshToken, user } = useAuthStore();
    const [pwForm, setPwForm] = useState({ old_password: '', new_password: '', new_password_confirm: '' });
    const [pwMsg, setPwMsg] = useState('');
    const [pwSaving, setPwSaving] = useState(false);

    // Profile state for billing display
    const [profile, setProfile] = useState(null);

    // UI Functional States
    const [config2fa, setConfig2fa] = useState('none');

    // 2FA Auth State Hook
    const [qrCode, setQrCode] = useState('');
    const [token2fa, setToken2fa] = useState('');

    // Fetch actual profile to show real subscription data
    useEffect(() => {
        const fetchProfile = async () => {
            try {
                if (user?.role === 'TALENT') {
                    const { data } = await authService.getMe();
                    setProfile(data.profile);
                } else if (user?.role === 'COMPANY') {
                    const { data } = await authService.getMe();
                    setProfile(data.profile);
                }
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load profile data.'), 'error');
            }
        };
        fetchProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user]);

    // Fetch actual 2FA status on mount so the toggle reflects reality
    useEffect(() => {
        authService.getMe().then(({ data }) => {
            const u = data;
            if (u.is_2fa_enabled) {
                setConfig2fa('done');
            }
        }).catch(() => { /* silent */ });
    }, []);

    const handleSetup2FA = async () => {
        try {
            const { data } = await authService.setup2FA();
            setQrCode(data.qr_code);
            setConfig2fa(data.is_enabled ? 'done' : 'open');
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to initialize 2FA setup.'), 'error');
        }
    };

    const handleDisable2FA = async () => {
        const pw = window.prompt('Enter your current password to disable 2FA:');
        if (!pw) return;
        try {
            await authService.disable2FA(pw);
            setConfig2fa('none');
            setQrCode('');
            addToast('Two-factor authentication disabled.', 'success');
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to disable 2FA. Check your password.'), 'error');
        }
    };

    const handleVerify2FA = async () => {
        try {
            await authService.verify2FA(token2fa);
            setConfig2fa('done');
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Invalid code. Please try again.'), 'error');
        }
    };

    const handleDeactivate = async () => {
        if (!window.confirm('Are you sure you want to deactivate your account? This action cannot be undone.')) return;
        const pw = window.prompt('Enter your current password to confirm:');
        if (!pw) return;
        try {
            await authService.deactivateAccount(pw);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Deactivation failed. Check your password.'), 'error');
            return; // Don't proceed with local cleanup if the backend rejected it
        }
        try {
            await authService.logout(refreshToken);
        } catch { /* swallow */ }
        logout();
        navigate('/');
    };

    const handlePasswordChange = async (e) => {
        e.preventDefault();
        if (pwForm.new_password !== pwForm.new_password_confirm) {
            setPwMsg('Passwords do not match.');
            return;
        }
        setPwSaving(true);
        setPwMsg('');
        try {
            await authService.changePassword(pwForm);
            setPwMsg('Password changed successfully.');
            setPwForm({ old_password: '', new_password: '', new_password_confirm: '' });
        } catch (err) {
            setPwMsg(getApiErrorMessage(err, 'Failed. Check current password.'));
        } finally {
            setPwSaving(false);
        }
    };
    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Settings",
                status: "Security Protocol: Active",
                info: "Account Configuration"
            }}
            pageTitleLine1="Set"
            pageTitleLine2="tings"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Current Plan</h3>
                        <p>{profile?.subscription_tier ? profile.subscription_tier.charAt(0).toUpperCase() + profile.subscription_tier.slice(1) : 'Free'}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Status</h3>
                        <p>Active</p>
                    </div>
                </div>
            }
        >
            <div className="settings-grid">
                <div className="settings-column border-right">

                    <div className="list-header"><h2>Billing & Subscription</h2></div>
                    <div className="plan-card">
                        <div className="plan-header">
                            <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: '#666' }}>Current Active Plan</span>
                            <div className="plan-tier">{profile?.subscription_tier ? profile.subscription_tier.charAt(0).toUpperCase() + profile.subscription_tier.slice(1) + ' Tier' : 'Free Tier'}</div>
                        </div>
                        <button className="btn-outline" style={{ width: '100%' }} onClick={() => navigate('/pricing')}>Upgrade Plan</button>
                    </div>

                    <div className="list-header" style={{ borderTop: '1px solid var(--border-color)' }}><h2>Invoice History</h2></div>
                    <div style={{ padding: '24px 32px', fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>
                        {profile?.subscription_tier && profile.subscription_tier !== 'free'
                            ? 'Invoice history is available via Stripe customer portal.'
                            : 'No invoices — currently on Free plan.'}
                    </div>

                    <div className="list-header" style={{ borderTop: '1px solid var(--border-color)' }}><h2>Payment Methods</h2></div>
                    <div className="setting-row">
                        <div className="setting-info">
                            <span className="setting-label">Managed by Stripe</span>
                            <span className="setting-desc">Payment methods are configured during checkout</span>
                        </div>
                        <button className="btn-outline" onClick={() => navigate('/pricing')}>Manage</button>
                    </div>
                </div>

                <div className="settings-column" style={{ display: 'flex' }}>
                    <div style={{ flex: 1 }}>
                        <div className="list-header"><h2>Account Security</h2></div>
                        <div className="setting-row" style={{ alignItems: 'flex-start' }}>
                            <div className="setting-info" style={{ width: '100%' }}>
                                <span className="setting-label">Two-Factor Auth</span>
                                <span className="setting-desc">Status: {config2fa === 'done' ? 'Enabled' : 'Disabled'}</span>
                                {config2fa === 'open' && (
                                    <div style={{ marginTop: '16px', padding: '16px', border: '1px dashed #000', background: '#f5f5f5' }}>
                                        <p style={{ fontSize: '12px', marginBottom: '12px', fontWeight: 600 }}>Scan with Google Authenticator:</p>
                                        <div style={{ width: '150px', height: '150px', margin: '0 0 16px 0', border: '1px solid #ddd', background: '#fff' }}>
                                            {qrCode ? <img src={qrCode} alt="2FA QR Code" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> : 'Loading...'}
                                        </div>
                                        <input type="text" placeholder="Enter 6-digit code" aria-label="Two-factor authentication code" className="form-input" style={{ marginBottom: '12px', background: '#fff' }} value={token2fa} onChange={e => setToken2fa(e.target.value)} />
                                        <button className="btn-black-full" onClick={handleVerify2FA}>Verify & Enable</button>
                                    </div>
                                )}
                            </div>
                            {config2fa !== 'open' && (
                                <button className="btn-outline" onClick={() => config2fa === 'done' ? handleDisable2FA() : handleSetup2FA()}>
                                    {config2fa === 'done' ? 'Disable' : 'Configure'}
                                </button>
                            )}
                        </div>

                        <div className="list-header" style={{ borderTop: '1px solid var(--border-color)', marginTop: '20px' }}><h2>Change Password</h2></div>
                        <form onSubmit={handlePasswordChange} style={{ padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {pwMsg && <p style={{ fontSize: '11px', color: pwMsg.includes('success') ? '#060' : '#b00', textTransform: 'uppercase' }}>{pwMsg}</p>}
                            <input type="password" className="form-input" placeholder="Current Password" aria-label="Current Password" value={pwForm.old_password} onChange={e => setPwForm(p => ({ ...p, old_password: e.target.value }))} required />
                            <input type="password" className="form-input" placeholder="New Password" aria-label="New Password" value={pwForm.new_password} onChange={e => setPwForm(p => ({ ...p, new_password: e.target.value }))} required />
                            <input type="password" className="form-input" placeholder="Confirm New Password" aria-label="Confirm New Password" value={pwForm.new_password_confirm} onChange={e => setPwForm(p => ({ ...p, new_password_confirm: e.target.value }))} required />
                            <button type="submit" className="btn-outline" disabled={pwSaving} style={{ opacity: pwSaving ? 0.6 : 1 }}>{pwSaving ? 'Updating...' : 'Update Password'}</button>
                        </form>

                        <div className="list-header" style={{ borderTop: '1px solid var(--border-color)' }}><h2>Notifications</h2></div>
                        <div style={{ padding: '12px 32px', fontSize: '10px', opacity: 0.45, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            Email notification preferences — coming soon
                        </div>
                        <div className="setting-row" style={{ opacity: 0.45, pointerEvents: 'none' }}>
                            <div className="setting-info">
                                <span className="setting-label">System Alerts</span>
                                <span className="setting-desc">Immediate email for security events</span>
                            </div>
                            <div style={{ width: '40px', height: '20px', border: '1px solid #000', background: 'transparent', position: 'relative' }}>
                                <div style={{ width: '14px', height: '14px', background: '#000', position: 'absolute', left: '2px', top: '2px' }}></div>
                            </div>
                        </div>
                        <div className="setting-row" style={{ opacity: 0.45, pointerEvents: 'none' }}>
                            <div className="setting-info">
                                <span className="setting-label">Weekly Report</span>
                                <span className="setting-desc">Summary of talent acquisition flow</span>
                            </div>
                            <div style={{ width: '40px', height: '20px', border: '1px solid #000', background: 'transparent', position: 'relative' }}>
                                <div style={{ width: '14px', height: '14px', background: '#000', position: 'absolute', left: '2px', top: '2px' }}></div>
                            </div>
                        </div>

                        <div style={{ padding: '40px 32px' }}>
                            <button className="btn-outline" style={{ borderColor: '#900', color: '#900', width: '100%' }} onClick={handleDeactivate}>Deactivate Account</button>
                        </div>
                    </div>
                    <div className="vertical-label-settings">System Prefs // Configuration</div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Settings;
