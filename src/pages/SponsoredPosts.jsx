import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage, paymentsService } from '../services/api';

/* ── Styles (content-level only — layout chrome lives in DashboardLayout) ── */
const styles = {
  viewGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 380px',
    height: '100%',
  },
  sectionColumn: { borderRight: '1px solid var(--text-black)' },
  listHeader: {
    padding: '24px 32px',
    borderBottom: '1px solid var(--text-black)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  listHeaderH2: {
    fontFamily: 'var(--font-display)',
    fontSize: '28px',
    textTransform: 'uppercase',
  },
  campaignTable: { width: '100%', borderCollapse: 'collapse' },
  campaignTableTh: {
    textAlign: 'left',
    padding: '12px 32px',
    fontSize: '10px',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    borderBottom: '1px solid var(--text-black)',
    fontWeight: 700,
  },
  campaignTableTd: {
    padding: '20px 32px',
    borderBottom: '1px solid var(--text-black)',
    fontSize: '13px',
  },
  campaignName: {
    fontFamily: 'var(--font-serif)',
    fontSize: '16px',
    textTransform: 'uppercase',
    display: 'block',
  },
  campaignSub: { fontSize: '10px', opacity: 0.6 },
  badgeActive: {
    padding: '4px 8px',
    fontSize: '9px',
    fontWeight: 700,
    textTransform: 'uppercase',
    border: '1px solid var(--text-black)',
    background: 'var(--text-black)',
    color: 'var(--text-white)',
  },
  badgeScheduled: {
    padding: '4px 8px',
    fontSize: '9px',
    fontWeight: 700,
    textTransform: 'uppercase',
    border: '1px solid var(--text-black)',
    background: 'transparent',
    color: 'var(--text-black)',
  },
  formContainer: { padding: '32px' },
  formGroup: { marginBottom: '24px' },
  formLabel: {
    display: 'block',
    fontFamily: 'var(--font-serif)',
    fontSize: '14px',
    textTransform: 'uppercase',
    marginBottom: '8px',
  },
  formInput: {
    width: '100%',
    padding: '12px',
    border: '1px solid var(--text-black)',
    background: 'transparent',
    fontFamily: 'var(--font-sans)',
    fontSize: '13px',
  },
  formSelect: {
    width: '100%',
    padding: '12px',
    border: '1px solid var(--text-black)',
    background: 'transparent',
    fontFamily: 'var(--font-sans)',
    fontSize: '13px',
  },
  btnSolid: {
    width: '100%',
    padding: '16px',
    background: 'var(--bg-dark)',
    color: 'var(--text-white)',
    border: 'none',
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
    letterSpacing: '1px',
  },
  chartContainer: {
    padding: '32px',
    height: '180px',
    display: 'flex',
    alignItems: 'flex-end',
    gap: '8px',
    borderBottom: '1px solid var(--text-black)',
  },
  chartBar: {
    flex: 1,
    background: 'var(--bg-dark)',
    transition: 'height 0.3s',
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
  rightCol: { display: 'flex' },
  btnOutline: {
    padding: '10px 20px',
    border: '1px solid var(--text-black)',
    background: 'transparent',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
  },
  loadingGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 380px',
    height: '100%',
  },
  errorState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    textAlign: 'center',
    gap: '12px',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 40px',
    textAlign: 'center',
    gap: '12px',
  },
};

/* ── Sub-components ─────────────────────────────────────────────────────── */

const CampaignTable = ({ campaigns }) => {
  const defaultCampaigns = [
    { name: 'Senior Art Director', sub: 'Volume One Studios • End: 12/04', status: 'active', impressions: '12.4k', clicks: '842', apps: '45', spend: '$450.00' },
    { name: 'Frontend Lead', sub: 'TechFlow Inc • End: 15/04', status: 'active', impressions: '8.1k', clicks: '510', apps: '22', spend: '$310.00' },
    { name: 'UX Researcher', sub: 'Design Co • Starts: 20/04', status: 'scheduled', impressions: '0', clicks: '0', apps: '0', spend: '$0.00' },
  ];
  const rows = campaigns?.length ? campaigns : defaultCampaigns;

  return (
    <table style={styles.campaignTable}>
      <thead>
        <tr>
          <th style={styles.campaignTableTh}>Campaign / Job</th>
          <th style={styles.campaignTableTh}>Status</th>
          <th style={styles.campaignTableTh}>Impr.</th>
          <th style={styles.campaignTableTh}>Clicks</th>
          <th style={styles.campaignTableTh}>Apps</th>
          <th style={styles.campaignTableTh}>Spend</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c, i) => (
          <tr key={i}>
            <td style={styles.campaignTableTd}>
              <span style={styles.campaignName}>{c.name || c.job_title}</span>
              <span style={styles.campaignSub}>{c.sub || c.description}</span>
            </td>
            <td style={styles.campaignTableTd}>
              <span style={c.status === 'active' ? styles.badgeActive : styles.badgeScheduled}>
                {c.status === 'active' ? 'Active' : 'Scheduled'}
              </span>
            </td>
            <td style={styles.campaignTableTd}>{c.impressions ?? 0}</td>
            <td style={styles.campaignTableTd}>{c.clicks ?? 0}</td>
            <td style={styles.campaignTableTd}>{c.apps ?? c.applications ?? 0}</td>
            <td style={styles.campaignTableTd}>{typeof c.spend === 'number' ? `$${c.spend.toFixed(2)}` : c.spend ?? '$0.00'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const BoostForm = ({ onSuccess }) => {
  const { addToast } = useToast();
  const { boostCampaignSchema } = require('../utils/schemas');
  const [selectedJob, setSelectedJob] = useState('Marketing Strategist - Global Brands');
  const [budget, setBudget] = useState('');
  const [duration, setDuration] = useState('7');
  const [audience, setAudience] = useState('Senior Professionals (5+ yrs)');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    setFormError('');
    setSubmitting(true);
    try {
      const result = boostCampaignSchema.safeParse({
        jobId: selectedJob,
        dailyBudget: Number(budget),
        durationDays: Number(duration),
        targetAudience: audience,
      });
      if (!result.success) {
        setFormError(result.error.errors[0]?.message || 'Validation error');
        setSubmitting(false);
        return;
      }
      await paymentsService.createSponsoredCampaign({
        job_title: selectedJob,
        daily_budget: Number(budget),
        duration: duration,
        target_audience: audience,
      });
      addToast('Campaign initialized successfully!', 'success');
      onSuccess?.();
      setBudget('');
      setDuration('7');
      setAudience('Senior Professionals (5+ yrs)');
      setSelectedJob('Marketing Strategist - Global Brands');
      setSubmitting(false);
    } catch (err) {
      setFormError(getApiErrorMessage(err, 'Failed to create campaign.'));
      setSubmitting(false);
    }
  };

  return (
    <form style={styles.formContainer} onSubmit={handleSubmit}>
      <div style={styles.formGroup}>
        <label style={styles.formLabel}>Select Active Job</label>
        <select style={styles.formSelect} value={selectedJob} onChange={(e) => setSelectedJob(e.target.value)} required>
          <option>Marketing Strategist - Global Brands</option>
          <option>Project Manager - BuildIt</option>
          <option>Junior Designer - Studio 4</option>
        </select>
      </div>
      <div style={styles.formGroup}>
        <label style={styles.formLabel}>Daily Budget (USD)</label>
        <input type="number" style={styles.formInput} placeholder="50.00" value={budget} onChange={(e) => setBudget(e.target.value)} required min={1} max={10000} />
      </div>
      <div style={styles.formGroup}>
        <label style={styles.formLabel}>Duration (Days)</label>
        <select style={styles.formSelect} value={duration} onChange={(e) => setDuration(e.target.value)} required>
          <option value="7">7</option>
          <option value="14">14</option>
          <option value="30">30</option>
          <option value="90">90</option>
        </select>
      </div>
      <div style={styles.formGroup}>
        <label style={styles.formLabel}>Target Audience</label>
        <select style={styles.formSelect} value={audience} onChange={(e) => setAudience(e.target.value)} required>
          <option>Senior Professionals (5+ yrs)</option>
          <option>Regional: North America</option>
          <option>Skill-based: Creative Suite</option>
        </select>
      </div>
      {formError && <div style={{ color: 'red', marginBottom: '8px' }}>{formError}</div>}
      <button
        type="submit"
        style={{ ...styles.btnSolid, ...(submitting ? { background: '#333', opacity: 0.8 } : {}) }}
        disabled={submitting}
      >
        {submitting ? '✓ Campaign Initialized' : 'Initialize Boost Campaign'}
      </button>
    </form>
  );
};

const chartBars = [
  { height: '40%' }, { height: '65%' }, { height: '50%' }, { height: '85%' },
  { height: '70%' }, { height: '95%' }, { height: '60%' },
];

/* ── Main component ─────────────────────────────────────────────────────── */

const SponsoredPosts = () => {
  usePageTitle('Sponsored Posts', 'Boost your job listings with targeted campaigns.');

  const { campaigns, campaignsLoading, fetchCampaigns } = usePaymentStore();
  const { addToast } = useToast();
  const [fetchError, setFetchError] = useState(null);

  const loadCampaigns = useCallback(async (signal) => {
    setFetchError(null);
    try {
      await fetchCampaigns(signal);
    } catch (err) {
      if (signal?.aborted) return;
      setFetchError(err);
      addToast(getApiErrorMessage(err, 'Failed to load campaigns.'), 'error');
    }
  }, [fetchCampaigns, addToast]);

  useEffect(() => {
    const controller = new AbortController();
    loadCampaigns(controller.signal);
    return () => controller.abort();
  }, [loadCampaigns]);

  /* ── Derived stats ────────────────────────────────────────────────────── */
  const totalSpend = campaigns?.reduce((sum, c) => {
    const amount = typeof c.spend === 'number' ? c.spend : parseFloat(String(c.spend).replace(/[^0-9.]/g, '')) || 0;
    return sum + amount;
  }, 0) ?? 0;

  /* ── Header right stats ───────────────────────────────────────────────── */
  const headerRight = (
    <div style={{ display: 'flex', gap: '40px' }}>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Total Spend</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {campaignsLoading ? '…' : `$${totalSpend.toLocaleString('en-US', { minimumFractionDigits: 2 })} MTD`}
        </p>
      </div>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Avg. ROI</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {campaignsLoading ? '…' : '4.2x Yield'}
        </p>
      </div>
    </div>
  );

  /* ── Render content ───────────────────────────────────────────────────── */
  const renderContent = () => {
    /* Loading state */
    if (campaignsLoading && !campaigns?.length) {
      return (
        <div style={styles.loadingGrid}>
          <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <Skeleton height={180} />
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
    if (fetchError && !campaigns?.length) {
      return (
        <div style={styles.errorState}>
          <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase' }}>
            Unable to load campaign data
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6 }}>
            {getApiErrorMessage(fetchError, 'Something went wrong. Please try again.')}
          </p>
          <button style={{ ...styles.btnOutline, marginTop: '8px' }} onClick={() => loadCampaigns()}>
            Retry
          </button>
        </div>
      );
    }

    /* Empty state */
    if (!campaigns?.length) {
      return (
        <div style={styles.emptyState}>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' }}>
            No campaigns yet
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6, maxWidth: '400px' }}>
            Create your first sponsored campaign to boost job visibility and reach targeted talent.
          </p>
        </div>
      );
    }

    /* Normal content */
    return (
      <div style={styles.viewGrid}>
        <div style={styles.sectionColumn}>
          <div style={styles.listHeader}>
            <h2 style={styles.listHeaderH2}>Active Campaigns</h2>
          </div>
          <div style={styles.chartContainer}>
            {chartBars.map((bar, i) => (
              <div key={i} style={{ ...styles.chartBar, height: bar.height }} />
            ))}
          </div>
          <CampaignTable campaigns={campaigns} />
        </div>

        <div style={styles.rightCol}>
          <div style={{ flex: 1 }}>
            <div style={styles.listHeader}>
              <h2 style={styles.listHeaderH2}>Boost Post</h2>
            </div>
            <BoostForm onSuccess={() => loadCampaigns()} />
          </div>
          <div style={styles.verticalLabel}>Ads // Sponsored // Management</div>
        </div>
      </div>
    );
  };

  return (
    <DashboardLayout
      tapeBarProps={{
        title: 'TalentOrbit v2.1 // Sponsored',
        status: 'Ads Module',
        info: campaignsLoading ? 'Loading...' : 'Active',
      }}
      pageTitleLine1="Spons"
      pageTitleLine2="ored"
      headerRightContent={headerRight}
    >
      {renderContent()}
    </DashboardLayout>
  );
};

export default SponsoredPosts;
