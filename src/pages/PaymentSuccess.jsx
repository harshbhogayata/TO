import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import { useAuthStore } from '../store/authStore';

const PaymentSuccess = () => {
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const { user } = useAuthStore();
    const plan = params.get('plan');
    const [count, setCount] = useState(5);

    const dashboardMap = { TALENT: '/user', COMPANY: '/company', ADMIN: '/admin' };
    const dashboardPath = dashboardMap[user?.role] || '/user';

    useEffect(() => {
        if (count <= 0) { navigate(dashboardPath); return; }
        const t = setTimeout(() => setCount(c => c - 1), 1000);
        return () => clearTimeout(t);
    }, [count, navigate, dashboardPath]);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Payment Confirmed",
                status: "Transaction: Successful",
                info: "Stripe Secure Checkout"
            }}
            pageTitleLine1="Payment"
            pageTitleLine2="Success"
            headerRightContent={null}
        >
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                flex: 1,
                padding: '60px 40px',
                textAlign: 'center',
                gap: '24px',
            }}>
                {/* Checkmark circle */}
                <div style={{
                    width: '80px', height: '80px', borderRadius: '50%',
                    border: '2px solid #006400',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '36px', color: '#006400',
                }}>
                    ✓
                </div>

                <div>
                    <p style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#006400', marginBottom: '8px' }}>
                        Payment Confirmed
                    </p>
                    <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 'clamp(28px, 4vw, 48px)', lineHeight: 1.1, marginBottom: '16px' }}>
                        {plan && plan !== 'free' ? `Welcome to ${plan}` : 'You\'re all set'}
                    </h2>
                    <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', opacity: 0.6, maxWidth: '420px' }}>
                        Your subscription is now active. Your dashboard has been updated.
                        Redirecting in {count}s…
                    </p>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                    <button className="btn-black" style={{ padding: '14px 32px' }} onClick={() => navigate(dashboardPath)}>
                        Go to Dashboard
                    </button>
                    <button className="btn-outline" style={{ padding: '14px 32px' }} onClick={() => navigate('/pricing')}>
                        View Plans
                    </button>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default PaymentSuccess;
