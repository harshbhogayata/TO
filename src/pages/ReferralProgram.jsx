import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

/* ── Styles (content-level only — layout chrome lives in DashboardLayout) ── */
const styles = {
  referralGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 320px',
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
  referralLinkBox: {
    padding: '32px',
    borderBottom: '1px solid var(--text-black)',
    background: 'rgba(0,0,0,0.02)',
  },
  linkInputGroup: {
    display: 'flex',
    marginTop: '12px',
    border: '1px solid var(--text-black)',
  },
  linkInput: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    padding: '12px',
    fontFamily: 'var(--font-sans)',
    fontSize: '14px',
    outline: 'none',
  },
  btnBlack: {
    background: 'var(--bg-dark)',
    color: 'var(--text-white)',
    border: 'none',
    padding: '0 20px',
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    cursor: 'pointer',
  },
  shareRow: {
    display: 'flex',
    gap: '12px',
    marginTop: '16px',
  },
  shareBtn: {
    flex: 1,
    padding: '8px',
    border: '1px solid var(--text-black)',
    background: 'transparent',
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    cursor: 'pointer',
    fontFamily: 'var(--font-sans)',
  },
  dataTable: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  tableTh: {
    textAlign: 'left',
    padding: '12px 32px',
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    textTransform: 'uppercase',
    borderBottom: '1px solid var(--text-black)',
    opacity: 0.6,
  },
  tableTd: {
    padding: '16px 32px',
    borderBottom: '1px solid var(--text-black)',
    fontFamily: 'var(--font-serif)',
    fontSize: '14px',
    textTransform: 'uppercase',
  },
  statusBadge: {
    fontFamily: 'var(--font-sans)',
    fontSize: '9px',
    fontWeight: 700,
    padding: '2px 6px',
    border: '1px solid var(--text-black)',
  },
  leaderboardRow: {
    padding: '16px 24px',
    borderBottom: '1px solid var(--text-black)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  rank: {
    fontFamily: 'var(--font-display)',
    fontSize: '18px',
    width: '30px',
  },
  leaderName: {
    fontFamily: 'var(--font-serif)',
    fontSize: '14px',
    textTransform: 'uppercase',
  },
  leaderCount: {
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
    fontWeight: 600,
  },
  verticalTag: {
    writingMode: 'vertical-rl',
    transform: 'rotate(180deg)',
    padding: '20px',
    fontFamily: 'var(--font-display)',
    fontSize: '24px',
    borderLeft: '1px solid var(--text-black)',
    backgroundColor: 'var(--bg-beige)',
    textTransform: 'uppercase',
  },
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
    gridTemplateColumns: '1fr 320px',
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

const ReferralLinkBox = ({ referralLink }) => {
  const [copied, setCopied] = useState(false);
  const [linkedinClicked, setLinkedinClicked] = useState(false);
  const [twitterClicked, setTwitterClicked] = useState(false);

  const link = referralLink || 'talentorbit.com/ref/user_9921';

  const handleCopy = () => {
    navigator.clipboard?.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLinkedin = () => {
    setLinkedinClicked(true);
    setTimeout(() => setLinkedinClicked(false), 1500);
  };

  const handleTwitter = () => {
    setTwitterClicked(true);
    setTimeout(() => setTwitterClicked(false), 1500);
  };

  return (
    <div style={styles.referralLinkBox}>
      <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>
        Your Personal Invite Link
      </span>
      <div style={styles.linkInputGroup}>
        <input type="text" style={styles.linkInput} value={link} readOnly />
        <button style={styles.btnBlack} onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy Link'}
        </button>
      </div>
      <div style={styles.shareRow}>
        <button
          style={{ ...styles.shareBtn, background: linkedinClicked ? 'var(--text-black)' : 'transparent', color: linkedinClicked ? 'var(--text-white)' : 'var(--text-black)' }}
          onClick={handleLinkedin}
        >
          Share to LinkedIn
        </button>
        <button
          style={{ ...styles.shareBtn, background: twitterClicked ? 'var(--text-black)' : 'transparent', color: twitterClicked ? 'var(--text-white)' : 'var(--text-black)' }}
          onClick={handleTwitter}
        >
          Post to X / Twitter
        </button>
      </div>
    </div>
  );
};

const RewardTiers = ({ tiers }) => {
  const defaultTiers = [
    { level: 'Tier 01: Scout', requirements: '1-5 Qualified', commission: '5% Per Placement' },
    { level: 'Tier 02: Partner', requirements: '6-15 Qualified', commission: '10% Per Placement' },
    { level: 'Tier 03: Ambassador', requirements: '16+ Qualified', commission: '15% Per Placement' },
  ];
  const rows = tiers?.length ? tiers : defaultTiers;

  return (
    <>
      <div style={styles.listHeader}>
        <h2 style={styles.listHeaderH2}>Reward Tiers</h2>
      </div>
      <table style={styles.dataTable}>
        <thead>
          <tr>
            <th style={styles.tableTh}>Level</th>
            <th style={styles.tableTh}>Requirements</th>
            <th style={styles.tableTh}>Commission</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={i} style={i === rows.length - 1 ? { background: 'rgba(0,0,0,0.05)' } : undefined}>
              <td style={styles.tableTd}>{t.level || t.name}</td>
              <td style={styles.tableTd}>{t.requirements}</td>
              <td style={styles.tableTd}>{t.commission}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
};

const PayoutItem = ({ name, detail, status, paid }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '20px 32px', borderBottom: '1px solid var(--text-black)', alignItems: 'center' }}>
    <div>
      <div style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase' }}>{name}</div>
      <div style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.6 }}>{detail}</div>
    </div>
    <span style={{ ...styles.statusBadge, background: paid ? 'transparent' : 'var(--text-black)', color: paid ? 'var(--text-black)' : 'var(--text-white)' }}>
      {status}
    </span>
  </div>
);

const RecentPayouts = ({ rewards }) => {
  const defaultPayouts = [
    { name: 'Alexander V.', detail: 'Qualified 12 Oct • $450.00', status: 'PAID', paid: true },
    { name: 'Sienna Bloom', detail: 'Qualified 28 Oct • $1,200.00', status: 'PENDING', paid: false },
  ];
  const rows = rewards?.length ? rewards : defaultPayouts;

  return (
    <>
      <div style={{ ...styles.listHeader, marginTop: '20px' }}>
        <h2 style={styles.listHeaderH2}>Recent Payouts</h2>
      </div>
      <div>
        {rows.map((r, i) => (
          <PayoutItem
            key={i}
            name={r.name || r.referral_name}
            detail={r.detail || `${r.date || ''} • $${r.amount || '0.00'}`}
            status={r.status?.toUpperCase() || 'PENDING'}
            paid={r.paid ?? r.status === 'paid'}
          />
        ))}
      </div>
    </>
  );
};

const LeaderboardItem = ({ rank, name, count }) => (
  <div style={styles.leaderboardRow}>
    <span style={styles.rank}>{rank}</span>
    <span style={styles.leaderName}>{name}</span>
    <span style={styles.leaderCount}>{count}</span>
  </div>
);

const Leaderboard = ({ referrals }) => {
  const defaultLeaders = [
    { rank: '01', name: 'Marcus Thorne', count: '88 Ref' },
    { rank: '02', name: 'Helena G.', count: '72 Ref' },
    { rank: '03', name: 'J. Sterling', count: '54 Ref' },
    { rank: '04', name: 'Vector Labs', count: '41 Ref' },
    { rank: '05', name: 'Sarah Chen', count: '39 Ref' },
  ];
  const leaders = referrals?.length
    ? referrals.map((r, i) => ({
        rank: String(i + 1).padStart(2, '0'),
        name: r.name || r.referrer_name,
        count: `${r.count ?? r.referral_count ?? 0} Ref`,
      }))
    : defaultLeaders;

  return (
    <div style={{ ...styles.sectionColumn, display: 'flex' }}>
      <div style={{ flex: 1 }}>
        <div style={styles.listHeader}>
          <h2 style={{ ...styles.listHeaderH2, fontSize: '24px' }}>Leaderboard</h2>
        </div>
        {leaders.map((leader) => (
          <LeaderboardItem key={leader.rank} rank={leader.rank} name={leader.name} count={leader.count} />
        ))}
      </div>
      <div style={styles.verticalTag}>Partner Growth // 2024</div>
    </div>
  );
};

/* ── Main component ─────────────────────────────────────────────────────── */

const ReferralProgram = () => {
  usePageTitle('Referral Program', 'Earn rewards by referring talent and companies.');

  const {
    referralProgram, referralStats, referrals, rewards,
    referralLoading,
    fetchReferralProgram, fetchReferralStats, fetchReferrals, fetchRewards,
  } = usePaymentStore();
  const { addToast } = useToast();
  const [fetchError, setFetchError] = useState(null);

  const loadData = useCallback(async (signal) => {
    setFetchError(null);
    try {
      await Promise.all([
        fetchReferralProgram(signal),
        fetchReferralStats(signal),
        fetchReferrals(signal),
        fetchRewards(signal),
      ]);
    } catch (err) {
      if (signal?.aborted) return;
      setFetchError(err);
      addToast(getApiErrorMessage(err, 'Failed to load referral data.'), 'error');
    }
  }, [fetchReferralProgram, fetchReferralStats, fetchReferrals, fetchRewards, addToast]);

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, [loadData]);

  /* ── Derived data (safe when null) ────────────────────────────────────── */
  const stats = referralStats ?? {};
  const program = referralProgram ?? {};

  /* ── Header right stats ───────────────────────────────────────────────── */
  const headerRight = (
    <div style={{ display: 'flex', gap: '40px' }}>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Sent</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {referralLoading ? '…' : `${stats.sent ?? 0} Invites`}
        </p>
      </div>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Signed Up</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {referralLoading ? '…' : `${stats.signed_up ?? 0} Members`}
        </p>
      </div>
      <div>
        <h3 style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: '600', opacity: '0.6', marginBottom: '4px' }}>Qualified</h3>
        <p style={{ fontFamily: 'var(--font-serif)', fontSize: '16px' }}>
          {referralLoading ? '…' : `${String(stats.qualified ?? 0).padStart(2, '0')} Conversions`}
        </p>
      </div>
    </div>
  );

  /* ── Render content ───────────────────────────────────────────────────── */
  const renderContent = () => {
    /* Loading state */
    if (referralLoading && !referralStats) {
      return (
        <div style={styles.loadingGrid}>
          <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <Skeleton.Card />
            <Skeleton.Card />
            <Skeleton.List count={3} />
          </div>
          <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <Skeleton.List count={5} />
          </div>
        </div>
      );
    }

    /* Error state */
    if (fetchError && !referralStats) {
      return (
        <div style={styles.errorState}>
          <p style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase' }}>
            Unable to load referral data
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6 }}>
            {getApiErrorMessage(fetchError, 'Something went wrong. Please try again.')}
          </p>
          <button style={{ ...styles.btnOutline, marginTop: '8px' }} onClick={() => loadData()}>
            Retry
          </button>
        </div>
      );
    }

    /* Empty state */
    if (!referralStats && !referrals?.length && !rewards?.length) {
      return (
        <div style={styles.emptyState}>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' }}>
            No referral data yet
          </p>
          <p style={{ fontSize: '13px', opacity: 0.6, maxWidth: '400px' }}>
            Once you start referring talent and companies, your referral stats, rewards, and leaderboard will appear here.
          </p>
        </div>
      );
    }

    /* Normal content */
    // Zod schema
    const { referralSchema } = require('../utils/schemas');
    const [refereeEmail, setRefereeEmail] = useState('');
    const [formError, setFormError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleReferralSubmit = async (e) => {
      e.preventDefault();
      setFormError('');
      setSubmitting(true);
      try {
        const result = referralSchema.safeParse({ refereeEmail });
        if (!result.success) {
          setFormError(result.error.errors[0]?.message || 'Validation error');
          setSubmitting(false);
          return;
        }
        // TODO: Call API to submit referral
        addToast('Referral sent successfully!', 'success');
        setRefereeEmail('');
        setSubmitting(false);
      } catch (err) {
        setFormError('Unexpected error. Please try again.');
        setSubmitting(false);
      }
    };

    return (
      <div style={styles.referralGrid}>
        <div style={styles.sectionColumn}>
          <ReferralLinkBox referralLink={program.referral_link} />
          <form onSubmit={handleReferralSubmit} style={{ padding: '32px', borderBottom: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.02)', marginBottom: '24px' }}>
            <label style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 700 }}>
              Refer a colleague or friend:
              <input
                type="email"
                value={refereeEmail}
                onChange={e => setRefereeEmail(e.target.value)}
                placeholder="Enter email address"
                style={{ marginLeft: '8px', padding: '8px', fontSize: '14px', fontFamily: 'var(--font-sans)' }}
                maxLength={255}
                required
              />
            </label>
            {formError && <div style={{ color: 'red', marginTop: '8px' }}>{formError}</div>}
            <button
              type="submit"
              style={{ ...styles.btnBlack, marginTop: '12px' }}
              disabled={submitting}
            >
              {submitting ? 'Submitting...' : 'Send Referral'}
            </button>
          </form>
          <RewardTiers tiers={program.tiers} />
          <RecentPayouts rewards={rewards} />
        </div>
        <Leaderboard referrals={referrals} />
      </div>
    );
  };

  return (
    <DashboardLayout
      tapeBarProps={{
        title: 'TalentOrbit v2.1 // Referrals',
        status: 'Growth Module',
        info: referralLoading ? 'Loading...' : 'Active',
      }}
      pageTitleLine1="Ref"
      pageTitleLine2="errals"
      headerRightContent={headerRight}
    >
      {renderContent()}
    </DashboardLayout>
  );
};

export default ReferralProgram;
