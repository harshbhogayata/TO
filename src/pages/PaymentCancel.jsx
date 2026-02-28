import { useNavigate } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';

const PaymentCancel = () => {
    const navigate = useNavigate();

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Payment Cancelled",
                status: "Transaction: Cancelled",
                info: "No charges were made"
            }}
            pageTitleLine1="Payment"
            pageTitleLine2="Cancelled"
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
                {/* X circle */}
                <div style={{
                    width: '80px', height: '80px', borderRadius: '50%',
                    border: '2px solid #999',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '32px', color: '#999',
                }}>
                    ✕
                </div>

                <div>
                    <p style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#999', marginBottom: '8px' }}>
                        Payment Cancelled
                    </p>
                    <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 'clamp(28px, 4vw, 48px)', lineHeight: 1.1, marginBottom: '16px' }}>
                        No charges made
                    </h2>
                    <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', opacity: 0.6, maxWidth: '420px' }}>
                        You cancelled the checkout. Your card was not charged.
                        You can upgrade any time from the Pricing page.
                    </p>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
                    <button className="btn-black" style={{ padding: '14px 32px' }} onClick={() => navigate('/pricing')}>
                        Back to Pricing
                    </button>
                    <button className="btn-outline" style={{ padding: '14px 32px' }} onClick={() => navigate(-1)}>
                        ← Go Back
                    </button>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default PaymentCancel;
