import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';

/**
 * VerifyEmail — handles email verification via link params.
 * URL: /verify-email?uid=xxx&token=xxx
 */
const VerifyEmail = () => {
    usePageTitle('Verify Email', 'Confirm your TalentOrbit email address to unlock all features.');
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { user } = useAuthStore();
    const uid = searchParams.get('uid');
    const token = searchParams.get('token');

    const [status, setStatus] = useState('verifying'); // verifying | success | error | missing
    const [message, setMessage] = useState('');
    const calledRef = useRef(false);

    useEffect(() => {
        if (calledRef.current) return;
        calledRef.current = true;

        if (!uid || !token) {
            setStatus('missing');
            setMessage('Invalid verification link. Please check your email and try again.');
            return;
        }

        (async () => {
            try {
                const { data } = await authService.verifyEmail(uid, token);
                setStatus('success');
                setMessage(data.message || 'Email verified successfully!');
            } catch (err) {
                setStatus('error');
                setMessage(getApiErrorMessage(err, 'Verification failed. The link may have expired.'));
            }
        })();
    }, [uid, token]);

    const iconMap = {
        verifying: '◌',
        success: '✓',
        error: '✕',
        missing: '?',
    };

    return (
        <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100vh', width: '100vw',
            background: 'var(--bg-cream, #f5f0eb)', color: 'var(--text-black, #1a1a1a)',
            fontFamily: 'var(--font-sans, monospace)',
        }}>
            <div style={{
                maxWidth: '480px', width: '90%', border: '1px solid var(--border-color, #d4c9b8)',
                padding: '48px', textAlign: 'center',
            }}>
                <div style={{
                    fontSize: '48px', marginBottom: '24px',
                    fontFamily: 'var(--font-display, "Anton", sans-serif)',
                    animation: status === 'verifying' ? 'spin 1s linear infinite' : 'none',
                }}>
                    {iconMap[status]}
                </div>

                <h1 style={{
                    fontFamily: 'var(--font-display, "Anton", sans-serif)',
                    fontSize: '24px', textTransform: 'uppercase', letterSpacing: '2px',
                    marginBottom: '16px',
                }}>
                    {status === 'verifying' && 'Verifying...'}
                    {status === 'success' && 'Email Verified'}
                    {status === 'error' && 'Verification Failed'}
                    {status === 'missing' && 'Invalid Link'}
                </h1>

                <p style={{
                    fontSize: '13px', lineHeight: 1.7, opacity: 0.7,
                    textTransform: 'uppercase', marginBottom: '32px',
                }}>
                    {message}
                </p>

                {status !== 'verifying' && (
                    <button
                        onClick={() => {
                            if (status === 'success') {
                                const dashMap = { COMPANY: '/company', ADMIN: '/admin' };
                                navigate(dashMap[user?.role] || '/user');
                            } else {
                                navigate('/auth');
                            }
                        }}
                        style={{
                            padding: '14px 32px', border: '1px solid var(--text-black, #1a1a1a)',
                            background: status === 'success' ? 'var(--text-black, #1a1a1a)' : 'transparent',
                            color: status === 'success' ? 'var(--bg-cream, #f5f0eb)' : 'var(--text-black, #1a1a1a)',
                            fontFamily: 'var(--font-sans, monospace)',
                            fontSize: '11px', textTransform: 'uppercase', letterSpacing: '2px',
                            cursor: 'pointer',
                        }}
                    >
                        {status === 'success' ? 'Go to Dashboard' : 'Go to Login'}
                    </button>
                )}
            </div>

            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
};

export default VerifyEmail;
