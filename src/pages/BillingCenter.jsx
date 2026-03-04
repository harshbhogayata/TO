import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

/* ── Styles (content-level only — layout chrome lives in DashboardLayout) ── */
const styles = {
  billingGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 400px',
    height: '100%',
  },
  sectionColumn: {
    borderRight: '1px solid var(--text-black)',
  },
  listHeader: {
    padding: '24px 32px',
    borderBottom: '1px solid var(--text-black)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  listHeaderH2: {
    fontFamily: 'var(--font-display)',
    fontSize: '32px',
    textTransform: 'uppercase',
  },
  billingCard: {
    padding: '32px',
    borderBottom: '1px solid var(--text-black)',
  },
  planHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '24px',
  },
  planName: {
    fontFamily: 'var(--font-serif)',
    fontSize: '24px',
    textTransform: 'uppercase',
  },
  planPrice: {
    fontFamily: 'var(--font-display)',
    fontSize: '32px',
  },
  usageSection: {
    marginTop: '32px',
  },
  usageItem: {
    marginBottom: '20px',
  },
  usageLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    textTransform: 'uppercase',
    marginBottom: '6px',
    fontWeight: '600',
  },
  progressBarBg: {
    height: '4px',
    background: 'rgba(0,0,0,0.1)',
    width: '100%',
  },
  progressBarFill: {
    height: '100%',
    background: 'var(--text-black)',
  },
  invoiceTable: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  invoiceTh: {
    textAlign: 'left',
    padding: '16px 32px',
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    textTransform: 'uppercase',
    borderBottom: '1px solid var(--text-black)',
    opacity: '0.6',
  },
  invoiceTd: {
    padding: '16px 32px',
    fontFamily: 'var(--font-sans)',
    fontSize: '13px',
    borderBottom: '1px solid var(--text-black)',
  },
  statusPill: {
    fontSize: '10px',
    padding: '2px 8px',
    border: '1px solid var(--text-black)',
    textTransform: 'uppercase',
    fontWeight: '600',
  },
  btnOutline: {
    padding: '10px 16px',
    background: 'transparent',
    border: '1px solid var(--text-black)',
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    fontWeight: '700',
    textTransform: 'uppercase',
    cursor: 'pointer',
  },
  paymentMethod: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 0',
    borderBottom: '1px solid rgba(0,0,0,0.1)',
  },
  verticalLabel: {
    writingMode: 'vertical-rl',
    textOrientation: 'mixed',
    transform: 'rotate(180deg)',
    padding: '20px',
    fontFamily: 'var(--font-display)',
    fontSize: '24px',
    borderLeft: '1px solid var(--text-black)',
    backgroundColor: 'var(--bg-beige)',
    height: '100%',
    textTransform: 'uppercase',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    textAlign: 'center',
    gap: '16px',
  },
  errorState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    textAlign: 'center',
    gap: '16px',
  },
  loadingGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 400px',
    gap: '0',
    height: '100%',
  },
};

/* ── Sub-components ─────────────────────────────────────────────────────── */

const UsageBar = ({ label, used, total, percentage }) => (
  <div style={styles.usageItem}>
    <div style={styles.usageLabels}>
      <span>{label}</span>
      <span>{used} / {total}</span>
    </div>
    <div style={styles.progressBarBg}>
      <div style={{ ...styles.progressBarFill, width: `${percentage}%` }} />
    </div>
  </div>
);

const InvoiceRow = ({ date, amount, status }) => {
  const [hovered, setHovered] = useState(false);
  return (
    <tr>
      <td style={styles.invoiceTd}>{date}</td>
      <td style={styles.invoiceTd}>{amount}</td>
      <td style={styles.invoiceTd}>
        <span style={styles.statusPill}>{status}</span>
      </td>
      <td style={{ ...styles.invoiceTd, textAlign: 'right' }}>
        <button
          style={{
            ...styles.btnOutline,
            background: hovered ? 'var(--text-black)' : 'transparent',
            color: hovered ? 'var(--bg-beige)' : 'var(--text-black)',
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          PDF
        </button>
      </td>
    </tr>
  );
};

const PaymentMethodItem = ({ cardName, expiry, isDefault }) => (
  <div style={styles.paymentMethod}>
    <div>
      <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>{cardName}</p>
      <p style={{ fontSize: '11px', opacity: '0.6', textTransform: 'uppercase' }}>
        {expiry}{isDefault ? ' • Default' : ''}
      </p>
    </div>
    <button style={{ fontSize: '10px', border: 'none', background: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
      Edit
    </button>
  </div>
);

/* ── Main Component ─────────────────────────────────────────────────────── */

const BillingCenter = () => {
  usePageTitle('Billing Center', 'Manage your subscription, invoices, and payment methods.');

  const { billing, billingLoading, fetchBilling } = usePaymentStore();
  const { addToast } = useToast();
  const [fetchError, setFetchError] = useState(null);
  const [addMethodHovered, setAddMethodHovered] = useState(false);

  const loadBilling = useCallback(async (signal) => {
    setFetchError(null);
    try {
      await fetchBilling(signal);
    } catch (err) {
      if (signal?.aborted) return;
      setFetchError(err);
      addToast(getApiErrorMessage(err, 'Failed to load billing data.'), 'error');
    }
  }, [fetchBilling, addToast]);

  useEffect(() => {
    const controller = new AbortController();
    loadBilling(controller.signal);
    return () => controller.abort();
  }, [loadBilling]);

  /* ── Derived data (safe when billing is null) ─────────────────────────── */
  const plan = billing?.plan ?? {};
  const usage = billing?.usage ?? [];
  const invoices = billing?.invoices ?? [];
  const paymentMethods = billing?.payment_methods ?? [];
  const upcomingCharge = billing?.upcoming_charge ?? {};

  /* ── Header right stats ───────────────────────────────────────────────── */
  const headerRight = (
    <div style={{ display: 'flex', gap: '40px' }}>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Current Plan</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {billingLoading ? '…' : plan.name || 'N/A'}
        </p>
      </div>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Next Invoice</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {billingLoading ? '…' : plan.next_invoice_date || 'N/A'}
        </p>
      </div>
    </div>
  );

  /* ── Render ───────────────────────────────────────────────────────────── */
  const renderContent = () => {
    /* Loading state */
    if (billingLoading && !billing) {
      return (
        <div style={styles.loadingGrid}>
          <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <Skeleton.Card />
            <Skeleton.Card />
            <Skeleton.List count={3} />
          </div>
          <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <Skeleton.Card />
            <Skeleton.Text lines={4} />
          </div>
        </div>
      );
    }

    /* Error state */
    if (fetchError && !billing) {
      return (
        <div style={styles.errorState}>
          <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase' }}>
            Unable to load billing data
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6 }}>
            {getApiErrorMessage(fetchError, 'Something went wrong. Please try again.')}
          </p>
          <button
            style={{ ...styles.btnOutline, marginTop: '8px' }}
            onClick={() => loadBilling()}
          >
            Retry
          </button>
        </div>
      );
    }

    /* Empty state */
    if (!billing || (!usage.length && !invoices.length && !paymentMethods.length)) {
      return (
        <div style={styles.emptyState}>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' }}>
            No billing data yet
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6, maxWidth: '400px' }}>
            Once you subscribe to a plan, your billing information, invoices, and payment methods will appear here.
          </p>
        </div>
      );
    }

    /* Data state */
    return (
      <div style={styles.billingGrid}>
        <div style={styles.sectionColumn}>
          {/* Plan & Usage */}
          <div style={styles.listHeader}>
            <h2 style={styles.listHeaderH2}>Plan &amp; Usage</h2>
          </div>

          <div style={styles.billingCard}>
            <div style={styles.planHeader}>
              <div>
                <h3 style={styles.planName}>{plan.name || 'Subscription'}</h3>
                <p style={{ fontSize: '12px', opacity: '0.7', marginTop: '4px' }}>
                  {plan.description || 'Your current active plan.'}
                </p>
              </div>
              <div style={styles.planPrice}>
                ${plan.price ?? '—'}
                <span style={{ fontSize: '14px', fontFamily: 'var(--font-sans)' }}>/MO</span>
              </div>
            </div>

            <div style={styles.usageSection}>
              {usage.map((item, idx) => (
                <UsageBar
                  key={idx}
                  label={item.label}
                  used={item.used}
                  total={item.total}
                  percentage={item.total > 0 ? Math.round((item.used / item.total) * 100) : 0}
                />
              ))}
            </div>
          </div>

          {/* Invoice History */}
          <div style={styles.listHeader}>
            <h2 style={styles.listHeaderH2}>Invoice History</h2>
          </div>
          <table style={styles.invoiceTable}>
            <thead>
              <tr>
                <th style={styles.invoiceTh}>Date</th>
                <th style={styles.invoiceTh}>Amount</th>
                <th style={styles.invoiceTh}>Status</th>
                <th style={{ ...styles.invoiceTh, textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv, idx) => (
                <InvoiceRow
                  key={inv.id ?? idx}
                  date={inv.date}
                  amount={inv.amount}
                  status={inv.status}
                />
              ))}
            </tbody>
          </table>
        </div>

        {/* Right column — Payment Methods & Upcoming Charge */}
        <div style={{ display: 'flex' }}>
          <div style={{ flex: 1, padding: '32px' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '24px', textTransform: 'uppercase', marginBottom: '24px' }}>
              Payment Methods
            </h2>

            {paymentMethods.map((pm, idx) => (
              <PaymentMethodItem
                key={pm.id ?? idx}
                cardName={pm.card_name || pm.display}
                expiry={pm.expiry}
                isDefault={pm.is_default}
              />
            ))}

            <button
              style={{
                ...styles.btnOutline,
                width: '100%',
                marginTop: '24px',
                background: addMethodHovered ? 'var(--text-black)' : 'transparent',
                color: addMethodHovered ? 'var(--bg-beige)' : 'var(--text-black)',
              }}
              onMouseEnter={() => setAddMethodHovered(true)}
              onMouseLeave={() => setAddMethodHovered(false)}
            >
              Add New Method
            </button>

            <div style={{ marginTop: '60px', padding: '24px', border: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)' }}>
              <h3 style={{ fontFamily: 'var(--font-sans)', fontSize: '10px', textTransform: 'uppercase', marginBottom: '16px', opacity: '0.6' }}>
                Upcoming Charge Preview
              </h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px' }}>{upcomingCharge.base_label || 'Base'}</span>
                <span style={{ fontWeight: '600' }}>${upcomingCharge.base_amount ?? '0.00'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--text-black)', paddingBottom: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '14px' }}>Overages ({upcomingCharge.overage_count ?? 0})</span>
                <span style={{ fontWeight: '600' }}>${upcomingCharge.overage_amount ?? '0.00'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-display)', fontSize: '18px' }}>
                <span>Total Est.</span>
                <span>${upcomingCharge.total ?? '0.00'}</span>
              </div>
            </div>
          </div>
          <div style={styles.verticalLabel}>Financial Architecture // Orbit</div>
        </div>
      </div>
    );
  };

  return (
    <DashboardLayout
      tapeBarProps={{
        title: 'TalentOrbit v2.1 // Billing Terminal',
        status: 'Payments Module',
        info: billingLoading ? 'Loading...' : 'Active',
      }}
      pageTitleLine1="Bill"
      pageTitleLine2="Ing"
      headerRightContent={headerRight}
    >
      {renderContent()}
    </DashboardLayout>
  );
};

export default BillingCenter;
