import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

/* ── Styles (content-level only — layout chrome lives in DashboardLayout) ── */
const styles = {
  kpiStrip: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    borderBottom: '1px solid var(--text-black)',
  },
  kpiItem: {
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  kpiItemBorder: {
    padding: '20px',
    borderRight: '1px solid var(--text-black)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  kpiLabel: {
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    opacity: 0.6,
  },
  kpiValue: {
    fontFamily: 'var(--font-display)',
    fontSize: '24px',
  },
  chartsRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr',
    borderBottom: '1px solid var(--text-black)',
  },
  chartLeft: {
    padding: '32px',
    borderRight: '1px solid var(--text-black)',
  },
  chartRight: {
    padding: '32px',
  },
  chartTitle: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: 'var(--font-serif)',
    fontSize: '14px',
    textTransform: 'uppercase',
    marginBottom: '24px',
  },
  chartBox: {
    width: '100%',
    height: '200px',
    background: 'linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.02) 100%)',
    border: '1px solid var(--text-black)',
    position: 'relative',
    overflow: 'hidden',
  },
  sectionTitle: {
    padding: '24px 32px',
    borderBottom: '1px solid var(--text-black)',
    fontFamily: 'var(--font-display)',
    fontSize: '28px',
    textTransform: 'uppercase',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    textAlign: 'left',
    padding: '12px 32px',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    textTransform: 'uppercase',
    borderBottom: '1px solid var(--text-black)',
    background: 'rgba(0,0,0,0.03)',
  },
  td: {
    padding: '16px 32px',
    borderBottom: '1px solid var(--text-black)',
    fontFamily: 'var(--font-serif)',
    fontSize: '15px',
  },
  verticalLabel: {
    writingMode: 'vertical-rl',
    transform: 'rotate(180deg)',
    padding: '20px',
    fontFamily: 'var(--font-display)',
    fontSize: '20px',
    borderLeft: '1px solid var(--text-black)',
    textTransform: 'uppercase',
  },
  emptyState: {
    padding: '80px 40px',
    textAlign: 'center',
    fontFamily: 'var(--font-serif)',
    fontSize: '18px',
    opacity: 0.5,
    textTransform: 'uppercase',
  },
  errorState: {
    padding: '60px 40px',
    textAlign: 'center',
  },
  errorTitle: {
    fontFamily: 'var(--font-display)',
    fontSize: '28px',
    textTransform: 'uppercase',
    marginBottom: '12px',
  },
  errorMsg: {
    fontFamily: 'var(--font-sans)',
    fontSize: '13px',
    opacity: 0.6,
  },
};

/* ── Loading skeleton ───────────────────────────────────────────────────── */

const RevenueSkeleton = () => (
  <>
    <div style={styles.kpiStrip}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={i < 4 ? styles.kpiItemBorder : styles.kpiItem}>
          <Skeleton width="50%" height={10} style={{ marginBottom: 6 }} />
          <Skeleton width="40%" height={24} />
        </div>
      ))}
    </div>
    <div style={styles.chartsRow}>
      <div style={styles.chartLeft}>
        <Skeleton width="60%" height={14} style={{ marginBottom: 24 }} />
        <Skeleton height={200} />
      </div>
      <div style={styles.chartRight}>
        <Skeleton width="50%" height={14} style={{ marginBottom: 24 }} />
        <Skeleton height={150} />
      </div>
    </div>
    <div style={{ padding: '24px 32px', borderBottom: '1px solid var(--text-black)' }}>
      <Skeleton width="40%" height={28} />
    </div>
    {[0, 1, 2].map(i => (
      <div key={i} style={{ display: 'flex', gap: 32, padding: '16px 32px', borderBottom: '1px solid var(--text-black)' }}>
        <Skeleton width="25%" height={15} />
        <Skeleton width="15%" height={15} />
        <Skeleton width="15%" height={15} />
        <Skeleton width="20%" height={15} />
        <Skeleton width="10%" height={15} />
      </div>
    ))}
  </>
);

/* ── Main component ─────────────────────────────────────────────────────── */

const RevenueDashboard = () => {
  usePageTitle('Revenue Dashboard', 'Platform financial metrics and analytics.');

  const {
    revenueMetrics,
    revenueTrend,
    revenueLoading,
    fetchRevenueMetrics,
    fetchRevenueTrend,
  } = usePaymentStore();

  const { addToast } = useToast();
  const [error, setError] = useState(null);

  /* Fetch data on mount */
  useEffect(() => {
    Promise.all([fetchRevenueMetrics(), fetchRevenueTrend()])
      .catch(err => {
        const msg = getApiErrorMessage(err);
        setError(msg);
        addToast(msg, 'error');
      });
  }, [fetchRevenueMetrics, fetchRevenueTrend, addToast]);

  /* Fallback / demo data */
  const kpis = revenueMetrics
    ? [
        { label: 'Churn Rate', value: revenueMetrics.churn_rate || '2.4%' },
        { label: 'Avg LTV', value: revenueMetrics.avg_ltv || '$12.8k' },
        { label: 'ARPU', value: revenueMetrics.arpu || '$342' },
        { label: 'Payment Fail', value: revenueMetrics.payment_fail || '0.8%' },
        { label: 'Refund Rate', value: revenueMetrics.refund_rate || '0.12%' },
      ]
    : [
        { label: 'Churn Rate', value: '2.4%' },
        { label: 'Avg LTV', value: '$12.8k' },
        { label: 'ARPU', value: '$342' },
        { label: 'Payment Fail', value: '0.8%' },
        { label: 'Refund Rate', value: '0.12%' },
      ];

  const arr = revenueMetrics?.arr || '$4,284,000';

  const accounts = [
    { company: 'Global Brands Inc.', plan: 'Enterprise', mrr: '$12,500', since: 'Oct 2021', status: 'Active' },
    { company: 'TechFlow Solutions', plan: 'Enterprise', mrr: '$8,200', since: 'Jan 2022', status: 'Active' },
    { company: 'Volume One Studios', plan: 'Pro', mrr: '$2,400', since: 'Mar 2023', status: 'Active' },
    { company: 'BuildIt Construction', plan: 'Pro', mrr: '$1,800', since: 'Dec 2022', status: 'Active' },
  ];

  const cohortRows = [
    [{ val: 100, h: 'h-1' }, { val: 98, h: 'h-1' }, { val: 92, h: 'h-2' }, { val: 88, h: 'h-2' }, { val: 82, h: 'h-3' }, { val: 79, h: 'h-3' }, { val: 72, h: 'h-4' }, { val: 68, h: 'h-4' }, { val: 62, h: 'h-5' }, { val: 58, h: 'h-5' }, { val: 55, h: 'h-5' }, { val: 52, h: 'h-5' }, { val: 50, h: 'h-5' }],
    [{ val: 100, h: 'h-1' }, { val: 96, h: 'h-1' }, { val: 91, h: 'h-2' }, { val: 85, h: 'h-2' }, { val: 80, h: 'h-3' }, { val: 75, h: 'h-3' }, { val: 69, h: 'h-4' }, { val: 65, h: 'h-4' }, { val: 60, h: 'h-5' }, { val: 55, h: 'h-5' }, { val: 51, h: 'h-5' }, { val: 48, h: 'h-5' }, { val: null, h: '' }],
    [{ val: 100, h: 'h-1' }, { val: 97, h: 'h-1' }, { val: 93, h: 'h-2' }, { val: 89, h: 'h-2' }, { val: 84, h: 'h-3' }, { val: 81, h: 'h-3' }, { val: 76, h: 'h-4' }, { val: 72, h: 'h-4' }, { val: 67, h: 'h-5' }, { val: 63, h: 'h-5' }, { val: 60, h: 'h-5' }, { val: null, h: '' }, { val: null, h: '' }],
    [{ val: 100, h: 'h-1' }, { val: 95, h: 'h-1' }, { val: 90, h: 'h-2' }, { val: 84, h: 'h-2' }, { val: 78, h: 'h-3' }, { val: 73, h: 'h-3' }, { val: 67, h: 'h-4' }, { val: 62, h: 'h-4' }, { val: 57, h: 'h-5' }, { val: 53, h: 'h-5' }, { val: null, h: '' }, { val: null, h: '' }, { val: null, h: '' }],
  ];

  /* Header right content */
  const headerRight = (
    <div style={{ textAlign: 'right' }}>
      <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase' }}>Total Annual Run Rate</p>
      <p style={{ fontFamily: 'var(--font-display)', fontSize: '48px' }}>{arr}</p>
    </div>
  );

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Revenue', status: 'Admin Finance' }}
      pageTitleLine1="Rev"
      pageTitleLine2="enue"
      headerRightContent={headerRight}
    >
      {/* ── Error state ────────────────────────────────────────────── */}
      {error && !revenueLoading && (
        <div style={styles.errorState}>
          <div style={styles.errorTitle}>Revenue Data Unavailable</div>
          <div style={styles.errorMsg}>{error}</div>
        </div>
      )}

      {/* ── Loading state ──────────────────────────────────────────── */}
      {revenueLoading && <RevenueSkeleton />}

      {/* ── Empty state ────────────────────────────────────────────── */}
      {!revenueLoading && !error && !revenueMetrics && (
        <div style={styles.emptyState}>No revenue data available yet.</div>
      )}

      {/* ── Loaded state ───────────────────────────────────────────── */}
      {!revenueLoading && !error && (
        <>
          {/* KPI strip */}
          <div style={styles.kpiStrip}>
            {kpis.map((s, i) => (
              <div key={i} style={i < 4 ? styles.kpiItemBorder : styles.kpiItem}>
                <span style={styles.kpiLabel}>{s.label}</span>
                <span style={styles.kpiValue}>{s.value}</span>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div style={styles.chartsRow}>
            <div style={styles.chartLeft}>
              <div style={styles.chartTitle}>
                <span>MRR / ARR Growth (12M)</span>
                <span style={{ opacity: 0.5 }}>+14.2% YoY</span>
              </div>
              <div style={styles.chartBox}>
                <svg style={{ width: '100%', height: '100%' }} viewBox="0 0 600 200" preserveAspectRatio="none">
                  <path d="M0,180 L50,160 L100,165 L150,140 L200,130 L250,110 L300,90 L350,95 L400,70 L450,60 L500,50 L600,30 L600,200 L0,200 Z" fill="rgba(0,0,0,0.1)" />
                  <polyline fill="none" stroke="var(--text-black)" strokeWidth="2" points="0,180 50,160 100,165 150,140 200,130 250,110 300,90 350,95 400,70 450,60 500,50 600,30" />
                </svg>
              </div>
            </div>
            <div style={styles.chartRight}>
              <div style={{ fontFamily: 'var(--font-serif)', fontSize: '14px', textTransform: 'uppercase', marginBottom: '24px' }}>Plan Breakdown</div>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '20px', height: '150px', marginTop: '20px' }}>
                {[{ h: '30%', l: 'Free' }, { h: '85%', l: 'Pro' }, { h: '55%', l: 'Ent.' }].map((b, i) => (
                  <div key={i} style={{ flex: 1, background: 'var(--bg-dark)', height: b.h, position: 'relative' }}>
                    <div style={{ position: 'absolute', bottom: '-20px', width: '100%', textAlign: 'center', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase' }}>{b.l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Top Revenue Accounts */}
          <div style={styles.sectionTitle}>Top Revenue Accounts</div>
          <table style={styles.table}>
            <thead>
              <tr>
                {['Company Name', 'Plan', 'MRR', 'Customer Since', 'Status'].map((h, i) => (
                  <th key={i} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {accounts.map((acc, i) => (
                <tr key={i}>
                  <td style={styles.td}>{acc.company}</td>
                  <td style={styles.td}>{acc.plan}</td>
                  <td style={styles.td}>{acc.mrr}</td>
                  <td style={styles.td}>{acc.since}</td>
                  <td style={styles.td}>{acc.status}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Cohort Retention Heatmap */}
          <div style={{ display: 'flex' }}>
            <div style={{ flex: 1 }}>
              <div style={styles.sectionTitle}>Cohort Retention Heatmap</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(13, 1fr)', gap: '2px', padding: '32px', background: 'var(--text-black)' }}>
                {cohortRows.map((row, ri) =>
                  row.map((cell, ci) => {
                    const bgMap = { 'h-1': '#000', 'h-2': '#333', 'h-3': '#666', 'h-4': '#999', 'h-5': '#ccc' };
                    const colorMap = { 'h-1': '#fff', 'h-2': '#fff', 'h-3': '#fff', 'h-4': '#000', 'h-5': '#000' };
                    return (
                      <div key={`${ri}-${ci}`} style={{ aspectRatio: '1', background: cell.h ? (bgMap[cell.h] || 'var(--bg-beige)') : 'var(--bg-beige)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 600, color: cell.h ? (colorMap[cell.h] || 'var(--text-black)') : 'var(--text-black)' }}>
                        {cell.val !== null ? cell.val : ''}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
            <div style={styles.verticalLabel}>Fiscal Stability // 2024</div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
};

export default RevenueDashboard;
