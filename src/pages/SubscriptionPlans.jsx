import React, { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';
import Skeleton from '../components/Skeleton';

/* ─── fallback data used when the API hasn't returned plans yet ─── */
const FALLBACK_PLANS = [
  {
    id: 'free',
    name: 'Free',
    monthly_price: 0,
    annual_price: 0,
    is_current: false,
    cta: 'Downgrade',
    cta_style: 'secondary',
    features: [
      { label: 'Basic Analytics', included: true },
      { label: 'Up to 3 Active Jobs', included: true },
      { label: 'Standard Support', included: true },
      { label: 'Custom Branding', included: false },
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    monthly_price: 186,
    annual_price: 149,
    is_current: true,
    cta: 'Manage Billing',
    cta_style: 'dashed',
    features: [
      { label: 'Advanced Analytics', included: true },
      { label: 'Unlimited Jobs', included: true },
      { label: 'Priority Support', included: true },
      { label: 'Custom Branding', included: true },
    ],
  },
  {
    id: 'scale',
    name: 'Scale',
    monthly_price: null,
    annual_price: null,
    is_current: false,
    cta: 'Contact Sales',
    cta_style: 'primary',
    features: [
      { label: 'Dedicated Account Mgr', included: true },
      { label: 'SSO & Security Suite', included: true },
      { label: 'Custom Workflows', included: true },
      { label: 'API Access', included: true },
    ],
  },
];

/* ─── inline styles (CSS‑variable aware) ─── */
const customStyles = {
  mainContent: {
    backgroundColor: 'var(--bg-beige)',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
  },
  contentHeader: {
    padding: '60px 40px 40px 40px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    borderBottom: '1px solid var(--text-black)',
  },
  pageTitle: {
    fontFamily: 'var(--font-display)',
    fontSize: '96px',
    textTransform: 'uppercase',
    lineHeight: 0.8,
    letterSpacing: '-1px',
  },
  billingToggle: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    border: '1px solid var(--text-black)',
    padding: '4px',
    marginBottom: '10px',
  },
  toggleBtnInactive: {
    padding: '8px 16px',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    border: 'none',
    cursor: 'pointer',
    background: 'transparent',
    color: 'var(--text-black)',
  },
  toggleBtnActive: {
    padding: '8px 16px',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    border: 'none',
    cursor: 'pointer',
    background: 'var(--bg-dark)',
    color: 'var(--bg-beige)',
  },
  plansGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    borderBottom: '1px solid var(--text-black)',
  },
  planColumn: {
    padding: '40px',
    borderRight: '1px solid var(--text-black)',
    display: 'flex',
    flexDirection: 'column',
  },
  planColumnCurrent: {
    padding: '40px',
    borderRight: '1px solid var(--text-black)',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(0,0,0,0.03)',
  },
  planColumnLast: {
    padding: '40px',
    display: 'flex',
    flexDirection: 'column',
  },
  planTag: {
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    background: 'var(--bg-dark)',
    color: 'var(--bg-beige)',
    padding: '4px 8px',
    alignSelf: 'flex-start',
    marginBottom: '16px',
  },
  planName: {
    fontFamily: 'var(--font-display)',
    fontSize: '48px',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  planPrice: {
    fontFamily: 'var(--font-serif)',
    fontSize: '32px',
    marginBottom: '24px',
  },
  planPriceSpan: {
    fontSize: '14px',
    fontFamily: 'var(--font-sans)',
    opacity: 0.6,
  },
  featureMatrix: {
    marginTop: '40px',
    width: '100%',
  },
  matrixRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '12px 0',
    borderBottom: '1px solid rgba(0,0,0,0.1)',
    fontSize: '13px',
  },
  matrixRowFaded: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '12px 0',
    borderBottom: '1px solid rgba(0,0,0,0.1)',
    fontSize: '13px',
    opacity: 0.3,
  },
  matrixRowLast: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '12px 0',
    fontSize: '13px',
  },
  featureLabel: {
    fontFamily: 'var(--font-sans)',
    fontWeight: 500,
  },
  featureCheck: {
    fontFamily: 'var(--font-sans)',
    fontWeight: 700,
  },
  ctaContainer: {
    marginTop: 'auto',
    paddingTop: '40px',
  },
  btnAction: {
    width: '100%',
    padding: '16px',
    background: 'var(--bg-dark)',
    color: 'var(--bg-beige)',
    border: '1px solid var(--text-black)',
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  btnActionSecondary: {
    width: '100%',
    padding: '16px',
    background: 'transparent',
    color: 'var(--text-black)',
    border: '1px solid var(--text-black)',
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  btnActionSecondaryDashed: {
    width: '100%',
    padding: '16px',
    background: 'transparent',
    color: 'var(--text-black)',
    border: '1px dashed var(--text-black)',
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'opacity 0.2s',
  },
  footerInfo: {
    padding: '40px',
    display: 'flex',
    justifyContent: 'space-between',
    background: '#DEDAD0',
    borderTop: '1px solid var(--text-black)',
  },
  prorationPreview: {
    maxWidth: '400px',
  },
  prorationTitle: {
    fontFamily: 'var(--font-serif)',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  prorationText: {
    fontSize: '12px',
    opacity: 0.7,
    lineHeight: 1.5,
  },
  statBlockH3: {
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '1px',
    marginBottom: '4px',
    opacity: 0.6,
  },
  statBlockP: {
    fontFamily: 'var(--font-serif)',
    fontSize: '16px',
  },
  verticalLabel: {
    writingMode: 'vertical-rl',
    textOrientation: 'mixed',
    transform: 'rotate(180deg)',
    fontFamily: 'var(--font-display)',
    fontSize: '14px',
    textTransform: 'uppercase',
    height: '60px',
    padding: '0 20px',
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    gap: '16px',
    textAlign: 'center',
  },
  emptyContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    gap: '8px',
    textAlign: 'center',
    opacity: 0.6,
  },
};

/* ─── sub‑components ─── */
const PlanFeatureRow = ({ label, value, faded, last }) => {
  let rowStyle = customStyles.matrixRow;
  if (faded) rowStyle = customStyles.matrixRowFaded;
  if (last) rowStyle = customStyles.matrixRowLast;
  return (
    <div style={rowStyle}>
      <span style={customStyles.featureLabel}>{label}</span>
      <span style={customStyles.featureCheck}>{value}</span>
    </div>
  );
};

const PlansLoadingSkeleton = () => (
  <div style={customStyles.plansGrid}>
    {[0, 1, 2].map((i) => (
      <div key={i} style={i < 2 ? customStyles.planColumn : customStyles.planColumnLast}>
        <Skeleton width="120px" height="48px" style={{ marginBottom: '8px' }} />
        <Skeleton width="160px" height="32px" style={{ marginBottom: '24px' }} />
        <div style={customStyles.featureMatrix}>
          {[0, 1, 2, 3].map((j) => (
            <div key={j} style={customStyles.matrixRow}>
              <Skeleton width="60%" height="14px" />
              <Skeleton width="20px" height="14px" />
            </div>
          ))}
        </div>
        <div style={customStyles.ctaContainer}>
          <Skeleton width="100%" height="48px" />
        </div>
      </div>
    ))}
  </div>
);

/* ─── main page component ─── */
const SubscriptionPlans = () => {
  usePageTitle('Subscription Plans', 'Choose the plan that fits your needs.');

  const { plans, plansLoading, fetchPlans } = usePaymentStore();
  const { showToast } = useToast();
  const [billing, setBilling] = useState('annual');
  const [fetchError, setFetchError] = useState(null);
  const [manageBillingHover, setManageBillingHover] = useState(false);
  const [contactSalesHover, setContactSalesHover] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [couponCode, setCouponCode] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // Zod schema
  const { planSelectionSchema } = require('../utils/schemas');

  const loadPlans = useCallback(async () => {
    try {
      setFetchError(null);
      await fetchPlans();
    } catch (err) {
      const msg = getApiErrorMessage(err);
      setFetchError(msg);
      showToast?.({ type: 'error', message: msg });
    }
  }, [fetchPlans, showToast]);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  /* Use API plans when available, otherwise fall back to hardcoded data */
  const displayPlans = plans && plans.length > 0 ? plans : FALLBACK_PLANS;

  /* ─── helpers ─── */
  const formatPrice = (plan) => {
    const price = billing === 'annual' ? plan.annual_price : plan.monthly_price;
    if (price === null || price === undefined) return 'Custom';
    if (price === 0) return '$0';
    return `$${price}`;
  };

  const formatPriceLabel = (plan) => {
    const price = billing === 'annual' ? plan.annual_price : plan.monthly_price;
    if (price === null || price === undefined) return '';
    if (price === 0) return '/ mo';
    return billing === 'annual' ? '/ mo billed annually' : '/ mo';
  };

  const getPlanColumnStyle = (plan, index) => {
    if (plan.is_current) return customStyles.planColumnCurrent;
    if (index === displayPlans.length - 1) return customStyles.planColumnLast;
    return customStyles.planColumn;
  };

  const getCtaButton = (plan) => {
    if (plan.cta_style === 'primary') {
      return (
        <button
          style={{ ...customStyles.btnAction, opacity: contactSalesHover ? 0.8 : 1 }}
          onMouseEnter={() => setContactSalesHover(true)}
          onMouseLeave={() => setContactSalesHover(false)}
        >
          {plan.cta || 'Contact Sales'}
        </button>
      );
    }
    if (plan.cta_style === 'dashed') {
      return (
        <button
          style={{ ...customStyles.btnActionSecondaryDashed, opacity: manageBillingHover ? 0.8 : 1 }}
          onMouseEnter={() => setManageBillingHover(true)}
          onMouseLeave={() => setManageBillingHover(false)}
        >
          {plan.cta || 'Manage Billing'}
        </button>
      );
    }
    /* secondary / default – disabled downgrade */
    return (
      <button
        style={{ ...customStyles.btnActionSecondary, opacity: 0.5, cursor: 'not-allowed' }}
        disabled
      >
        {plan.cta || 'Downgrade'}
      </button>
    );
  };

  /* ─── render ─── */
  const handlePlanSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setSubmitting(true);
    try {
      const result = planSelectionSchema.safeParse({
        planId: selectedPlanId,
        interval: billing,
        couponCode,
      });
      if (!result.success) {
        setFormError(result.error.errors[0]?.message || 'Validation error');
        setSubmitting(false);
        return;
      }
      // TODO: Call API to select plan
      showToast?.({ type: 'success', message: 'Plan selected successfully!' });
      setSubmitting(false);
    } catch (err) {
      setFormError('Unexpected error. Please try again.');
      setSubmitting(false);
    }
  };

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Plans', status: 'Subscription Module' }}
      pageTitleLine1="Plans"
      pageTitleLine2="& Pricing"
    >
      <div style={customStyles.mainContent}>
        <header style={customStyles.contentHeader}>
          <h1 style={customStyles.pageTitle}>Plans<br />&amp; Pricing</h1>
          <div style={{ textAlign: 'right' }}>
            <div style={customStyles.billingToggle}>
              <button
                style={billing === 'monthly' ? customStyles.toggleBtnActive : customStyles.toggleBtnInactive}
                onClick={() => setBilling('monthly')}
              >
                Monthly
              </button>
              <button
                style={billing === 'annual' ? customStyles.toggleBtnActive : customStyles.toggleBtnInactive}
                onClick={() => setBilling('annual')}
              >
                Annual (-20%)
              </button>
            </div>
            <div>
              <h3 style={customStyles.statBlockH3}>Currency</h3>
              <p style={customStyles.statBlockP}>USD ($)</p>
            </div>
          </div>
        </header>

        {/* ─── loading state ─── */}
        {plansLoading && <PlansLoadingSkeleton />}

        {/* ─── error state ─── */}
        {!plansLoading && fetchError && (
          <div style={customStyles.errorContainer}>
            <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px' }}>
              Failed to load plans
            </p>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', opacity: 0.6 }}>
              {fetchError}
            </p>
            <button style={customStyles.btnActionSecondary} onClick={loadPlans}>
              Retry
            </button>
          </div>
        )}

        {/* ─── empty state ─── */}
        {!plansLoading && !fetchError && displayPlans.length === 0 && (
          <div style={customStyles.emptyContainer}>
            <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px' }}>
              No plans available
            </p>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '13px' }}>
              Check back later or contact support.
            </p>
          </div>
        )}

        {/* ─── plans grid with selection form ─── */}
        {!plansLoading && !fetchError && displayPlans.length > 0 && (
          <form onSubmit={handlePlanSubmit} style={{ ...customStyles.plansGrid, gridTemplateColumns: `repeat(${displayPlans.length}, 1fr)` }}>
            {displayPlans.map((plan, index) => (
              <div key={plan.id || index} style={getPlanColumnStyle(plan, index)}>
                {plan.is_current && <span style={customStyles.planTag}>Current Plan</span>}
                <span style={customStyles.planName}>{plan.name}</span>
                <div style={customStyles.planPrice}>
                  {formatPrice(plan)}{' '}
                  {formatPriceLabel(plan) && (
                    <span style={customStyles.planPriceSpan}>{formatPriceLabel(plan)}</span>
                  )}
                </div>
                <div style={customStyles.featureMatrix}>
                  {(plan.features || []).map((feat, fi) => (
                    <PlanFeatureRow
                      key={fi}
                      label={feat.label}
                      value={feat.included ? '✓' : '—'}
                      faded={!feat.included}
                      last={fi === (plan.features || []).length - 1}
                    />
                  ))}
                </div>
                <div style={customStyles.ctaContainer}>
                  <label>
                    <input
                      type="radio"
                      name="planId"
                      value={plan.id}
                      checked={selectedPlanId === plan.id}
                      onChange={() => setSelectedPlanId(plan.id)}
                      disabled={plan.is_current}
                    />{' '}
                    Select
                  </label>
                </div>
              </div>
            ))}
            <div style={{ gridColumn: `span ${displayPlans.length}` }}>
              <label>
                Coupon Code (optional):
                <input
                  type="text"
                  value={couponCode}
                  onChange={e => setCouponCode(e.target.value)}
                  maxLength={50}
                  style={{ marginLeft: '8px' }}
                />
              </label>
              {formError && <div style={{ color: 'red', marginTop: '8px' }}>{formError}</div>}
              <button
                type="submit"
                style={customStyles.btnAction}
                disabled={submitting || !selectedPlanId}
              >
                {submitting ? 'Submitting...' : 'Select Plan'}
              </button>
            </div>
          </form>
        )}

        <footer style={customStyles.footerInfo}>
          <div style={customStyles.prorationPreview}>
            <h4 style={customStyles.prorationTitle}>Proration &amp; Changes</h4>
            <p style={customStyles.prorationText}>
              Upgrading plans takes effect immediately. A prorated credit for your current billing cycle will be applied to the new plan. Downgrades take effect at the end of the current billing period.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '40px', alignItems: 'center' }}>
            <div>
              <h3 style={customStyles.statBlockH3}>Next Invoice</h3>
              <p style={customStyles.statBlockP}>Oct 12, 2024 • $149.00</p>
            </div>
            <div style={customStyles.verticalLabel}>
              Subscription // Audit
            </div>
          </div>
        </footer>
      </div>
    </DashboardLayout>
  );
};

export default SubscriptionPlans;
