import { useCallback, useEffect, useState } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { usePaymentStore } from '../store/paymentStore';
import { getApiErrorMessage, paymentsService } from '../services/api';
import { moveCandidateSchema } from '../utils/schemas';

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

const getStageTitle = (stage = {}) => stage.name || stage.label || stage.id || 'Stage';

const getCandidateName = (candidate = {}) => (
  candidate.name
  || candidate.display_name
  || candidate.user_name
  || candidate.candidate_name
  || candidate.external_name
  || candidate.display_email
  || candidate.external_email
  || 'Unknown'
);

const getCandidateScore = (candidate = {}) => {
  if (candidate.score_display) {
    return candidate.score_display;
  }
  if (candidate.match_score !== undefined && candidate.match_score !== null) {
    return `${candidate.match_score}%`;
  }
  if (candidate.rating !== undefined && candidate.rating !== null) {
    return `${candidate.rating}/5`;
  }
  return '—';
};

const getCandidateBadge = (candidate = {}) => (
  candidate.badge
  || candidate.status
  || candidate.source_label
  || candidate.source
  || ''
);

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
      {cards.map((card, index) => (
        <CandidateCard key={card.id || index} {...card} />
      ))}
    </div>
  </div>
);

const PipelineSkeleton = () => (
  <>
    <div style={styles.analyticsStrip}>
      {[0, 1, 2, 3].map((index) => (
        <div key={index} style={index < 3 ? styles.analyticsItem : styles.analyticsItemLast}>
          <Skeleton width="60%" height={10} style={{ marginBottom: 6 }} />
          <Skeleton width="80%" height={16} />
        </div>
      ))}
    </div>
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      {[0, 1, 2, 3, 4].map((index) => (
        <div key={index} style={{ ...styles.pipelineColumn, padding: '16px' }}>
          <Skeleton width="50%" height={20} style={{ marginBottom: 16 }} />
          <Skeleton height={80} style={{ marginBottom: 12 }} />
          <Skeleton height={80} style={{ marginBottom: 12 }} />
        </div>
      ))}
    </div>
  </>
);

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

  const [error, setError] = useState(null);
  const [moveError, setMoveError] = useState('');
  const [moveSubmitting, setMoveSubmitting] = useState(false);

  useEffect(() => {
    fetchPipelines().catch((fetchError) => setError(getApiErrorMessage(fetchError)));
  }, [fetchPipelines]);

  useEffect(() => {
    if (!activePipeline && pipelines.length > 0) {
      setActivePipeline(pipelines[0]);
    }
  }, [pipelines, activePipeline, setActivePipeline]);

  useEffect(() => {
    if (activePipeline?.id) {
      fetchCandidates(activePipeline.id).catch((fetchError) => setError(getApiErrorMessage(fetchError)));
    }
  }, [activePipeline, fetchCandidates]);

  const moveCard = useCallback(async (candidateId, newStageId) => {
    setMoveError('');
    setMoveSubmitting(true);
    const previous = candidates;
    const result = moveCandidateSchema.safeParse({ candidateId, stageId: newStageId });

    if (!result.success) {
      setMoveError(result.error.errors[0]?.message || 'Validation error');
      setMoveSubmitting(false);
      return;
    }

    usePaymentStore.setState({
      candidates: candidates.map((candidate) => (
        candidate.id === candidateId ? { ...candidate, stage_id: newStageId } : candidate
      )),
    });

    try {
      await paymentsService.moveCandidate(candidateId, newStageId);
      setMoveSubmitting(false);
    } catch {
      usePaymentStore.setState({ candidates: previous });
      setMoveError('Failed to move candidate. Reverted.');
      setMoveSubmitting(false);
    }
  }, [candidates]);

  void moveCard;
  void moveSubmitting;
  void moveError;

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

  const columns = activePipeline?.stages?.length
    ? activePipeline.stages.map((stage, index, list) => {
        const stageCards = candidates.filter((candidate) => candidate.stage_id === stage.id);
        return {
          title: getStageTitle(stage),
          count: String(stageCards.length).padStart(2, '0'),
          cards: stageCards.map((candidate) => ({
            id: candidate.id,
            name: getCandidateName(candidate),
            score: getCandidateScore(candidate),
            role: candidate.role || candidate.position || candidate.headline || '',
            badge: getCandidateBadge(candidate),
            badgeDark: candidate.badge_dark || false,
            highlighted: candidate.highlighted || false,
          })),
          isLast: index === list.length - 1,
        };
      })
    : fallbackColumns;

  const isLoading = pipelinesLoading || candidatesLoading;

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
      {error && !isLoading && (
        <div style={styles.errorState}>
          <div style={styles.errorTitle}>Pipeline Unavailable</div>
          <div style={styles.errorMsg}>{error}</div>
        </div>
      )}

      {isLoading && <PipelineSkeleton />}

      {!isLoading && !error && pipelines.length === 0 && (
        <div style={styles.emptyState}>No pipelines configured yet.</div>
      )}

      {!isLoading && !error && columns.length > 0 && (
        <>
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

          <div style={styles.bulkActionBar}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>3 Candidates Selected</span>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button style={styles.btnSm}>Move Stage</button>
              <button style={styles.btnSm}>Bulk Email</button>
              <button style={styles.btnSmLight}>Archive</button>
            </div>
          </div>

          <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
            <div style={styles.pipelineContainer}>
              {columns.map((column, index) => (
                <PipelineColumn key={column.title || index} title={column.title} count={column.count} cards={column.cards} isLast={column.isLast} />
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
