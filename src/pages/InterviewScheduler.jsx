import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useAIStore } from '../store/aiStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

const styles = {
  stageTabs: { display: 'flex', borderBottom: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)' },
  stageTab: { padding: '14px 28px', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', cursor: 'pointer', background: 'transparent', border: 'none', borderRight: '1px solid var(--text-black)' },
  stageTabActive: { padding: '14px 28px', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', cursor: 'pointer', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', borderRight: '1px solid var(--text-black)' },
  bodyGrid: { display: 'grid', gridTemplateColumns: '1fr 340px', flex: 1, overflow: 'hidden' },
  calendarSection: { borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column' },
  calendarHeader: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  calendarTitle: { fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' },
  navBtn: { padding: '6px 14px', background: 'transparent', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, cursor: 'pointer' },
  weekRow: { display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', borderBottom: '1px solid var(--text-black)' },
  dayHeader: { padding: '10px', fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', textAlign: 'center', borderRight: '1px solid var(--text-black)' },
  dayCell: { minHeight: '100px', padding: '8px', borderRight: '1px solid var(--text-black)', borderBottom: '1px solid var(--text-black)', position: 'relative' },
  dayNumber: { fontFamily: 'var(--font-display)', fontSize: '16px', marginBottom: '6px' },
  eventBlock: { padding: '4px 6px', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', marginBottom: '4px', cursor: 'pointer', fontFamily: 'var(--font-body)' },
  eventDark: { background: 'var(--text-black)', color: 'var(--bg-beige)', border: '1px solid var(--text-black)' },
  eventLight: { background: 'transparent', border: '1px solid var(--text-black)', color: 'var(--text-black)' },
  sidePanel: { display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  sidePanelHeader: { padding: '20px 24px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  sidePanelTitle: { fontFamily: 'var(--font-display)', fontSize: '22px', textTransform: 'uppercase' },
  candidateItem: { padding: '16px 24px', borderBottom: '1px solid var(--text-black)', cursor: 'pointer', transition: 'background 0.15s' },
  candidateName: { fontFamily: 'var(--font-serif)', fontSize: '16px', textTransform: 'uppercase', fontWeight: 600, display: 'block' },
  candidateMeta: { fontFamily: 'var(--font-body)', fontSize: '11px', opacity: 0.6, marginTop: '4px', display: 'block' },
  candidateTime: { fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, marginTop: '6px', display: 'block' },
  statusDot: { display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', marginRight: '6px' },
  errorBox: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackCalendarEvents = {
  3: [{ name: 'Elena V. \u2014 Technical', style: 'dark' }],
  5: [{ name: 'Marc J. \u2014 System Design', style: 'dark' }, { name: 'Alex R. \u2014 Portfolio', style: 'light' }],
  8: [{ name: 'Sarah C. \u2014 Culture Fit', style: 'light' }],
  10: [{ name: 'Jordan S. \u2014 Final Panel', style: 'dark' }],
  12: [{ name: 'Team Debrief', style: 'light' }],
};

const fallbackCandidates = [
  { name: 'Elena Vance', role: 'Creative Director', time: 'Today, 2:00 PM', status: 'var(--text-black)' },
  { name: 'Marc Johnson', role: 'Frontend Lead', time: 'Wed, 10:30 AM', status: 'var(--text-black)' },
  { name: 'Alex Rivera', role: 'Sr. Product Designer', time: 'Wed, 3:00 PM', status: '#999' },
  { name: 'Sarah Chen', role: 'UX Researcher', time: 'Next Mon, 11:00 AM', status: '#999' },
  { name: 'Jordan Smith', role: 'Python Architect', time: 'Next Thu, 9:00 AM', status: 'var(--text-black)' },
];

const InterviewScheduler = () => {
    // Zod validation for scheduling interview slots
    const { interviewSlotSchema } = require('../utils/schemas');
    const [candidateEmail, setCandidateEmail] = useState('');
    const [slotTime, setSlotTime] = useState('');
    const [slotStage, setSlotStage] = useState(stages[0]);
    const [formError, setFormError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleScheduleSubmit = async (e) => {
      e.preventDefault();
      setFormError('');
      setSubmitting(true);
      try {
        const result = interviewSlotSchema.safeParse({
          candidateEmail,
          slotTime,
          slotStage,
        });
        if (!result.success) {
          setFormError(result.error.errors[0]?.message || 'Validation error');
          setSubmitting(false);
          return;
        }
        // TODO: Call API to schedule interview slot
        addToast('Interview slot scheduled!', 'success');
        setCandidateEmail('');
        setSlotTime('');
        setSlotStage(stages[0]);
        setSubmitting(false);
      } catch (err) {
        setFormError('Unexpected error. Please try again.');
        setSubmitting(false);
      }
    };
  usePageTitle('Interview Scheduler', 'Manage interview pipeline and calendar.');
  const { interviewSlots, slotsLoading, slotsError, fetchInterviewSlots } = useAIStore();
  const { addToast } = useToast();
  const [activeStage, setActiveStage] = useState('Technical');
  const stages = ['Phone Screen', 'Technical', 'Culture Fit', 'Final Round', 'Debrief'];
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  const loadSlots = useCallback(async () => {
    try {
      await fetchInterviewSlots({ stage: activeStage });
    } catch (err) {
      addToast(getApiErrorMessage(err, 'Failed to load interview slots.'), 'error');
    }
  }, [activeStage, fetchInterviewSlots, addToast]);

  useEffect(() => { loadSlots(); }, [loadSlots]);

  const candidates = interviewSlots.length > 0
    ? interviewSlots.map(s => ({ name: s.candidate_name || s.name, role: s.role || 'Candidate', time: s.time || s.scheduled_at || 'TBD', status: s.confirmed ? 'var(--text-black)' : '#999' }))
    : fallbackCandidates;

  const calendarDays = [];
  for (let i = 1; i <= 28; i++) calendarDays.push(i);

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Scheduler', status: 'Recruiting Module', info: slotsLoading ? 'Loading...' : 'Ready' }}
      pageTitleLine1="Inter"
      pageTitleLine2="views"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>This Week</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{candidates.length} Scheduled</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Pending</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{candidates.filter(c => c.status === '#999').length} Unconfirmed</p>
          </div>
        </div>
      }
    >
      {/* Example scheduling form for demo purposes */}
      <form onSubmit={handleScheduleSubmit} style={{ padding: '24px', borderBottom: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)', marginBottom: '16px' }}>
        <label style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 700 }}>
          Candidate Email:
          <input
            type="email"
            value={candidateEmail}
            onChange={e => setCandidateEmail(e.target.value)}
            placeholder="Enter email address"
            style={{ marginLeft: '8px', padding: '8px', fontSize: '14px', fontFamily: 'var(--font-sans)' }}
            maxLength={255}
            required
          />
        </label>
        <label style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 700, marginLeft: '16px' }}>
          Slot Time:
          <input
            type="text"
            value={slotTime}
            onChange={e => setSlotTime(e.target.value)}
            placeholder="e.g. 2026-03-10 14:00"
            style={{ marginLeft: '8px', padding: '8px', fontSize: '14px', fontFamily: 'var(--font-sans)' }}
            required
          />
        </label>
        <label style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', fontWeight: 700, marginLeft: '16px' }}>
          Stage:
          <select value={slotStage} onChange={e => setSlotStage(e.target.value)} style={{ marginLeft: '8px', padding: '8px', fontSize: '14px', fontFamily: 'var(--font-sans)' }} required>
            {stages.map(stage => <option key={stage} value={stage}>{stage}</option>)}
          </select>
        </label>
        {formError && <div style={{ color: 'red', marginTop: '8px' }}>{formError}</div>}
        <button type="submit" style={{ marginLeft: '16px', padding: '8px 20px', fontFamily: 'var(--font-sans)', fontWeight: 700 }} disabled={submitting}>
          {submitting ? 'Scheduling...' : 'Schedule Interview'}
        </button>
      </form>
      <div style={styles.stageTabs}>
        {stages.map((stage) => (
          <button key={stage} style={activeStage === stage ? styles.stageTabActive : styles.stageTab} onClick={() => setActiveStage(stage)}>{stage}</button>
        ))}
      </div>

      {slotsError && (
        <div style={styles.errorBox}>
          <p style={styles.errorText}>{slotsError}</p>
          <button style={styles.retryBtn} onClick={loadSlots}>Retry</button>
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={styles.bodyGrid}>
          <div style={styles.calendarSection}>
            <div style={styles.calendarHeader}>
              <h2 style={styles.calendarTitle}>April 2025</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button style={styles.navBtn}>{'\u2190'} Prev</button>
                <button style={styles.navBtn}>Next {'\u2192'}</button>
              </div>
            </div>
            <div style={styles.weekRow}>
              {days.map((d) => <div key={d} style={styles.dayHeader}>{d}</div>)}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', flex: 1, overflowY: 'auto' }}>
              {calendarDays.map((day) => (
                <div key={day} style={styles.dayCell}>
                  <div style={styles.dayNumber}>{day}</div>
                  {fallbackCalendarEvents[day] && fallbackCalendarEvents[day].map((evt, i) => (
                    <div key={i} style={{ ...styles.eventBlock, ...(evt.style === 'dark' ? styles.eventDark : styles.eventLight) }}>{evt.name}</div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div style={styles.sidePanel}>
            <div style={styles.sidePanelHeader}>
              <h2 style={styles.sidePanelTitle}>Upcoming</h2>
              <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 }}>{activeStage} Stage</span>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {slotsLoading ? <div style={{ padding: '24px' }}><Skeleton.List count={5} /></div> : candidates.map((c, i) => (
                <div key={i} style={styles.candidateItem} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
                  <span style={styles.candidateName}>{c.name}</span>
                  <span style={styles.candidateMeta}>{c.role}</span>
                  <span style={styles.candidateTime}><span style={{ ...styles.statusDot, background: c.status }} />{c.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default InterviewScheduler;
