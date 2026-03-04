import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage, paymentsService } from '../services/api';

/* ── Styles (content-level only — layout chrome lives in DashboardLayout) ── */
const styles = {
  analyticsStrip: {
    display: 'flex',
    borderBottom: '1px solid var(--text-black)',
    background: 'rgba(0,0,0,0.03)',
  },
  analyticsItem: {
    flex: 1,
    padding: '12px 24px',
    borderRight: '1px solid var(--text-black)',
    display: 'flex',
    flexDirection: 'column',
  },
  analyticsItemLast: {
    flex: 1,
    padding: '12px 24px',
    display: 'flex',
    flexDirection: 'column',
  },
  analyticsLabel: {
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    opacity: 0.6,
  },
  analyticsValue: {
    fontFamily: 'var(--font-serif)',
    fontSize: '16px',
    fontWeight: 600,
  },
  bulkActionBar: {
    padding: '12px 40px',
    borderBottom: '1px solid var(--text-black)',
    background: 'var(--bg-dark)',
    color: 'var(--text-white)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  pipelineContainer: {
    display: 'flex',
    overflowX: 'auto',
    flex: 1,
    background: '#DEDAD0',
  },
  pipelineColumn: {
    minWidth: '280px',
    flex: 1,
    borderRight: '1px solid var(--text-black)',
    display: 'flex',
    flexDirection: 'column',
  },
  pipelineColumnLast: {
    minWidth: '280px',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  columnHeader: {
    padding: '16px',
    background: 'var(--bg-beige)',
    borderBottom: '1px solid var(--text-black)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  columnTitle: {
    fontFamily: 'var(--font-display)',
    fontSize: '20px',
    textTransform: 'uppercase',
  },
  columnCount: {
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    fontWeight: 800,
    background: 'var(--text-black)',
    color: 'var(--text-white)',
    padding: '2px 6px',
  },
  cardsList: {
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    overflowY: 'auto',
  },
  candidateCard: {
    background: 'var(--bg-beige)',
    border: '1px solid var(--text-black)',
    padding: '16px',
    cursor: 'grab',
    transition: 'transform 0.1s',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '8px',
  },
  candidateName: {
    fontFamily: 'var(--font-serif)',
    fontSize: '16px',
    textTransform: 'uppercase',
    fontWeight: 600,
  },
  matchScore: {
    fontFamily: 'var(--font-sans)',
    fontSize: '10px',
    fontWeight: 800,
    border: '1px solid var(--text-black)',
    padding: '2px 4px',
  },
  candidateRole: {
    fontFamily: 'var(--font-sans)',
    fontSize: '11px',
    opacity: 0.7,
    textTransform: 'uppercase',
    marginBottom: '12px',
  },
  badgeRow: {
    display: 'flex',
    gap: '8px',
  },
  assessmentBadge: {
    fontSize: '9px',
    fontWeight: 700,
    textTransform: 'uppercase',
    padding: '2px 6px',
    border: '1px solid rgba(0,0,0,0.2)',
  },
  assessmentBadgeDark: {
    fontSize: '9px',
    fontWeight: 700,
    textTransform: 'uppercase',
    padding: '2px 6px',
    border: '1px solid rgba(0,0,0,0.2)',
    background: 'var(--text-black)',
    color: 'var(--text-white)',
  },
  btnSm: {
    padding: '4px 12px',
    fontSize: '10px',
    fontFamily: 'var(--font-sans)',
    fontWeight: 700,
    textTransform: 'uppercase',
    border: '1px solid var(--text-white)',
    background: 'transparent',
    color: 'var(--text-white)',
    cursor: 'pointer',
  },
  btnSmLight: {
    padding: '4px 12px',
    fontSize: '10px',
    fontFamily: 'var(--font-sans)',
    fontWeight: 700,
    textTransform: 'uppercase',
    border: '1px solid var(--text-black)',
    background: 'var(--bg-beige)',
    color: 'var(--text-black)',
    cursor: 'pointer',
  },
  verticalLabel: {
    writingMode: 'vertical-rl',
    textOrientation: 'mixed',
    transform: 'rotate(180deg)',
    padding: '20px',
    fontFamily: 'var(--font-display)',
    fontSize: '18px',
    borderLeft: '1px solid var(--text-black)',
    background: 'var(--bg-beige)',
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

/* ── Sub-components ─────────────────────────────────────────────────────── */

const CandidateCard = ({ name, score, role, badge, badgeDark, highlighted }) => {
  const [hovered, setHovered] = useState(false);
  const cardStyle = {
    ...styles.candidateCard,
    ...(highlighted ? { borderLeft: '4px solid var(--text-black)' } : {}),
    ...(hovered ? { transform: 'translateY(-2px)', boxShadow: '4px 4px 0px rgba(0,0,0,1)' } : {}),
  };

  return (
    <div style={cardStyle} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div style={styles.cardHeader}>
        <span style={styles.candidateName}>{name}</span>
        <span style={styles.matchScore}>{score}</span>
      </div>
      <div style={styles.candidateRole}>{role}</div>
      <div style={styles.badgeRow}>
        <span style={badgeDark ? styles.assessmentBadgeDark : styles.assessmentBadge}>{badge}</span>
      </div>
    </div>
  );
};

const PipelineColumn = ({ title, count, cards, isLast }) => (
  <div style={isLast ? styles.pipelineColumnLast : styles.pipelineColumn}>
    <div style={styles.columnHeader}>
      <span style={styles.columnTitle}>{title}</span>
      <span style={styles.columnCount}>{count}</span>
    </div>
    <div style={styles.cardsList}>
      {cards.map((card, idx) => (
        <CandidateCard key={card.id || idx} {...card} />
      ))}
    </div>
  </div>
);

/* ── Loading skeleton ───────────────────────────────────────────────────── */

const PipelineSkeleton = () => (
  <>
    <div style={styles.analyticsStrip}>
      {[0, 1, 2, 3].map(i => (
        <div key={i} style={i < 3 ? styles.analyticsItem : styles.analyticsItemLast}>
          <Skeleton width="60%" height={10} style={{ marginBottom: 6 }} />
          <Skeleton width="80%" height={16} />
        </div>
      ))}
    </div>
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={{ ...styles.pipelineColumn, padding: '16px' }}>
          <Skeleton width="50%" height={20} style={{ marginBottom: 16 }} />
          <Skeleton height={80} style={{ marginBottom: 12 }} />
          <Skeleton height={80} style={{ marginBottom: 12 }} />
        </div>
      ))}
    </div>
  </>
);

/* ── Main component ─────────────────────────────────────────────────────── */

const CRMPipeline = () => {
  usePageTitle('CRM Pipeline', 'Manage your talent pipeline and track candidates.');

  const {
    pipelines,
    pipelinesLoading,
    activePipeline,
    setActivePipeline,
    candidates,
    candidatesLoading,
    fetchPipelines,
    fetchCandidates,
  } = usePaymentStore();

  const { addToast } = useToast();
  const [error, setError] = useState(null);

  /* Fetch pipelines on mount */
  useEffect(() => {
    fetchPipelines().catch(err => setError(getApiErrorMessage(err)));
  }, [fetchPipelines]);

  /* Auto-select first pipeline; fetch candidates when active pipeline changes */
  useEffect(() => {
    if (!activePipeline && pipelines.length > 0) {
      setActivePipeline(pipelines[0]);
    }
  }, [pipelines, activePipeline, setActivePipeline]);

  useEffect(() => {
    if (activePipeline?.id) {
      fetchCandidates(activePipeline.id).catch(err =>
        setError(getApiErrorMessage(err)),
      );
    }
  }, [activePipeline, fetchCandidates]);

  /* Optimistic card move */
  const { moveCandidateSchema } = require('../utils/schemas');
  const [moveCandidateId, setMoveCandidateId] = useState('');
  const [moveStageId, setMoveStageId] = useState('');
  const [moveError, setMoveError] = useState('');
  const [moveSubmitting, setMoveSubmitting] = useState(false);
  const moveCard = useCallback(async (candidateId, newStageId) => {
    setMoveError('');
    setMoveSubmitting(true);
    const previous = candidates;
    // Validate with Zod
    const result = moveCandidateSchema.safeParse({ candidateId, stageId: newStageId });
    if (!result.success) {
      setMoveError(result.error.errors[0]?.message || 'Validation error');
      setMoveSubmitting(false);
      return;
    }
    // optimistic: update local list so UI feels instant
    usePaymentStore.setState({
      candidates: candidates.map(c =>
        c.id === candidateId ? { ...c, stage_id: newStageId } : c,
      ),
    });
    try {
      await paymentsService.moveCandidate(candidateId, newStageId);
      setMoveCandidateId('');
      setMoveStageId('');
      setMoveSubmitting(false);
    } catch (err) {
      // rollback
      usePaymentStore.setState({ candidates: previous });
      setMoveError('Failed to move candidate. Reverted.');
      setMoveSubmitting(false);
    }
  }, [candidates, addToast]);
  // Example move candidate form (for demo, should be placed in UI as needed)
  /*
  <form onSubmit={e => { e.preventDefault(); moveCard(moveCandidateId, moveStageId); }} style={{ margin: '16px 0' }}>
    <input
      type="text"
      placeholder="Candidate ID"
      value={moveCandidateId}
      onChange={e => setMoveCandidateId(e.target.value)}
      required
      style={{ marginRight: '8px' }}
    />
    <input
      type="text"
      placeholder="Stage ID"
      value={moveStageId}
      onChange={e => setMoveStageId(e.target.value)}
      required
      style={{ marginRight: '8px' }}
    />
    <button type="submit" disabled={moveSubmitting}>
      {moveSubmitting ? 'Moving...' : 'Move Candidate'}
    </button>
    {moveError && <span style={{ color: 'red', marginLeft: '8px' }}>{moveError}</span>}
  </form>
  */

  /* Derive columns from pipeline stages + candidates */
  const fallbackColumns = [
    { title: 'Sourced', count: '12', cards: [
      { name: 'Alex Rivera', score: '94%', role: 'Senior Product Designer', badge: 'Portfolio Passed' },
      { name: 'Sarah Chen', score: '88%', role: 'Lead UX Researcher', badge: 'External Referral' },
    ]},
    { title: 'Screening', count: '05', cards: [
      { name: 'Marc J.', score: '91%', role: 'Frontend Lead', badge: 'Top Tier', badgeDark: true },
    ]},
    { title: 'Interview', count: '08', cards: [
      { name: 'Elena Vance', score: '97%', role: 'Creative Director', badge: 'Technical Round 2', highlighted: true },
    ]},
    { title: 'Offer', count: '02', cards: [
      { name: 'Jordan Smith', score: '92%', role: 'Python Architect', badge: 'Negotiation' },
    ]},
    { title: 'Hired', count: '14', cards: [] },
    { title: 'Rejected', count: '45', cards: [] },
  ];

  const columns = activePipeline?.stages
    ? activePipeline.stages.map((stage, idx, arr) => {
        const stageCards = candidates.filter(c => c.stage_id === stage.id);
        return {
          title: stage.name,
          count: String(stageCards.length).padStart(2, '0'),
          cards: stageCards.map(c => ({
            id: c.id,
            name: c.name || c.candidate_name || 'Unknown',
            score: c.match_score ? `${c.match_score}%` : '—',
            role: c.role || c.position || '',
            badge: c.badge || c.status || '',
            badgeDark: c.badge_dark || false,
            highlighted: c.highlighted || false,
          })),
          isLast: idx === arr.length - 1,
        };
      })
    : fallbackColumns;

  const isLoading = pipelinesLoading || candidatesLoading;

  /* Header right content */
  const headerRight = (
    <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
      <div>
        <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Open Positions</h3>
        <p style={{ fontSize: '11px', opacity: 0.7 }}>
          {pipelines.length ? `${pipelines.length} Active Leads` : '—'}
        </p>
      </div>
      <div>
        <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Avg. Cycle</h3>
        <p style={{ fontSize: '11px', opacity: 0.7 }}>14 Days to Hire</p>
      </div>
    </div>
  );

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // CRM', status: 'Pipeline Module' }}
      pageTitleLine1="CRM"
      pageTitleLine2="Pipeline"
      headerRightContent={headerRight}
    >
      {/* ── Error state ────────────────────────────────────────────── */}
      {error && !isLoading && (
        <div style={styles.errorState}>
          <div style={styles.errorTitle}>Pipeline Unavailable</div>
          <div style={styles.errorMsg}>{error}</div>
        </div>
      )}

      {/* ── Loading state ──────────────────────────────────────────── */}
      {isLoading && <PipelineSkeleton />}

      {/* ── Empty state ────────────────────────────────────────────── */}
      {!isLoading && !error && pipelines.length === 0 && (
        <div style={styles.emptyState}>No pipelines configured yet.</div>
      )}

      {/* ── Loaded state ───────────────────────────────────────────── */}
      {!isLoading && !error && columns.length > 0 && (
        <>
          {/* Analytics strip */}
          <div style={styles.analyticsStrip}>
            <div style={styles.analyticsItem}>
              <span style={styles.analyticsLabel}>Conversion Rate</span>
              <span style={styles.analyticsValue}>18.4% Stage-to-Stage</span>
            </div>
            <div style={styles.analyticsItem}>
              <span style={styles.analyticsLabel}>Sourced to Screen</span>
              <span style={styles.analyticsValue}>42% Drop-off</span>
            </div>
            <div style={styles.analyticsItem}>
              <span style={styles.analyticsLabel}>Interview to Offer</span>
              <span style={styles.analyticsValue}>1:4 Ratio</span>
            </div>
            <div style={styles.analyticsItemLast}>
              <span style={styles.analyticsLabel}>Hired vs Target</span>
              <span style={styles.analyticsValue}>82% On Track</span>
            </div>
          </div>

          {/* Bulk action bar */}
          <div style={styles.bulkActionBar}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>3 Candidates Selected</span>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button style={styles.btnSm} onMouseEnter={e => { e.currentTarget.style.background = 'var(--text-white)'; e.currentTarget.style.color = 'var(--bg-dark)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-white)'; }}>Move Stage</button>
              <button style={styles.btnSm} onMouseEnter={e => { e.currentTarget.style.background = 'var(--text-white)'; e.currentTarget.style.color = 'var(--bg-dark)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-white)'; }}>Bulk Email</button>
              <button style={styles.btnSmLight} onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-dark)'; e.currentTarget.style.color = 'var(--text-white)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-beige)'; e.currentTarget.style.color = 'var(--text-black)'; }}>Archive</button>
            </div>
          </div>

          {/* Pipeline columns */}
          <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
            <div style={styles.pipelineContainer}>
              {columns.map((col, idx) => (
                <PipelineColumn key={col.title || idx} title={col.title} count={col.count} cards={col.cards} isLast={col.isLast} />
              ))}
            </div>
            <div style={styles.verticalLabel}>CRM WORKFLOW // PIPELINE VIEW</div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
};

export default CRMPipeline;
