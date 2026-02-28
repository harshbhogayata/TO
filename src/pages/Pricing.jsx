import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { paymentsService, authService, getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './Pricing.css';

/* Map plan IDs → backend tier codes */
const PLAN_TO_TIER = {
    'Free Agent': 'free',
    'Premium Pro': 'premium',
    'Starter': 'starter',
    'Professional': 'professional',
    'Enterprise': 'enterprise',
};

const PLANS = [
    {
        tier: 'Talent',
        cards: [
            {
                id: 'Free Agent',
                name: 'Free Agent',
                price: '$0',
                period: '/ month',
                features: ['Basic Profile Builder', '3 Job Applications / month', 'Public Talent Feed'],
                cta: 'Select Free',
                primary: false,
            },
            {
                id: 'Premium Pro',
                name: 'Premium Pro',
                price: '$19',
                period: '/ month',
                badge: 'Popular',
                features: ['Unlimited Applications', 'Priority Feed Placement', 'Skill Verification Quizzes', 'DM Direct to Recruiters'],
                cta: 'Upgrade Now',
                primary: true,
            },
        ],
    },
    {
        tier: 'Corporate',
        cards: [
            {
                id: 'Starter',
                name: 'Starter',
                price: '$99',
                period: '/ month',
                features: ['5 Active Job Posts', 'Standard ATS Integration', 'Basic Analytics'],
                cta: 'Choose Starter',
                primary: false,
            },
            {
                id: 'Professional',
                name: 'Professional',
                price: '$299',
                period: '/ month',
                badge: 'Recommended',
                features: ['Unlimited Job Posts', 'Custom Branding Tools', 'Automated Screening', 'Dedicated Account Lead'],
                cta: 'Choose Professional',
                primary: true,
            },
            {
                id: 'Enterprise',
                name: 'Enterprise',
                price: 'Custom',
                period: '',
                features: ['Full API Access', 'White-label Solutions', '24/7 Priority Support'],
                cta: 'Contact Sales',
                primary: false,
            },
        ],
    },
];

const Pricing = () => {
    const navigate = useNavigate();
    const { isAuthenticated } = useAuthStore();
    usePageTitle('Pricing');
    const [loadingPlan, setLoadingPlan] = useState(null);
    const [error, setError] = useState('');
    const [currentTier, setCurrentTier] = useState('free');

    useEffect(() => {
        if (!isAuthenticated) return;
        authService.getMe()
            .then(({ data }) => {
                const tier = data.profile?.subscription_tier || 'free';
                setCurrentTier(tier);
            })
            .catch(() => { /* tier defaults to free */ });
    }, [isAuthenticated]);

    /* Determine CTA text for a given plan */
    const getCta = (plan) => {
        const planTier = PLAN_TO_TIER[plan.id] || '';
        if (planTier === currentTier) return 'Current Plan';
        return plan.cta;
    };
    const isCurrentPlan = (plan) => (PLAN_TO_TIER[plan.id] || '') === currentTier;

    const handlePlan = async (planId) => {
        if (!isAuthenticated) {
            navigate('/auth');
            return;
        }
        setError('');
        setLoadingPlan(planId);
        try {
            const { data } = await paymentsService.createCheckoutSession(planId);
            if (data?.url) {
                window.location.href = data.url;
            } else {
                setError('Could not initiate checkout. Please try again.');
            }
        } catch (err) {
            setError(getApiErrorMessage(err, 'Something went wrong. Please try again.'));
        } finally {
            setLoadingPlan(null);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Pricing & Plans",
                status: "Secure Checkout via Stripe",
                info: "Billing Cycle: Monthly"
            }}
            pageTitleLine1="Pricing"
            pageTitleLine2="Plans & Tier"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Currency</h3><p>USD ($)</p></div>
                    <div className="stat-block"><h3>Billing</h3><p>Monthly</p></div>
                </div>
            }
        >
            {error && (
                <div style={{ padding: '12px 32px', background: 'rgba(180,0,0,0.05)', borderBottom: '1px solid #b00', color: '#b00', fontFamily: 'var(--font-sans)', fontSize: '11px', textTransform: 'uppercase' }}>
                    ✕ {error}
                </div>
            )}

            <div className="layout-inner">
                {PLANS.map(section => (
                    <div className="tier-section" key={section.tier} style={{ borderRight: section.tier === 'Corporate' ? 'none' : undefined }}>
                        <div className="section-sub-header">
                            <h2>{section.tier} Tiers</h2>
                        </div>

                        {section.cards.map(plan => (
                            <div className={`tier-card ${plan.primary ? 'featured' : ''}`} key={plan.id}>
                                {plan.badge && <div className="badge">{plan.badge}</div>}
                                <div className="tier-name">{plan.name}</div>
                                <div className="tier-price">
                                    {plan.price}
                                    {plan.period && <span>{plan.period}</span>}
                                </div>
                                <ul className="feature-list">
                                    {plan.features.map(f => (
                                        <li className="feature-item" key={f}>{f}</li>
                                    ))}
                                </ul>
                                <button
                                    className={`btn-action ${plan.primary && !isCurrentPlan(plan) ? 'primary' : ''}`}
                                    onClick={() => handlePlan(plan.id)}
                                    disabled={loadingPlan === plan.id || isCurrentPlan(plan)}
                                    style={{ opacity: isCurrentPlan(plan) ? 0.6 : (loadingPlan && loadingPlan !== plan.id ? 0.4 : 1), cursor: isCurrentPlan(plan) ? 'default' : (loadingPlan === plan.id ? 'wait' : 'pointer') }}
                                >
                                    {loadingPlan === plan.id ? (
                                        <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                                            <span style={{ display: 'inline-block', width: '12px', height: '12px', border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                                            Processing...
                                        </span>
                                    ) : getCta(plan)}
                                </button>
                            </div>
                        ))}
                    </div>
                ))}

                <div className="vertical-label pricing-label">
                    Subscription Management // Powered by Stripe
                </div>
            </div>

            <style>{`
                @keyframes spin { to { transform: rotate(360deg); } }
            `}</style>
        </DashboardLayout>
    );
};

export default Pricing;
