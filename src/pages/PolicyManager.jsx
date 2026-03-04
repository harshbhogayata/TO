import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useToast } from '../contexts/ToastContext';
import { complianceService, getApiErrorMessage } from '../services/api';

const styles = {
  bodyGrid: { display: 'grid', gridTemplateColumns: '320px 1fr 280px', flex: 1, overflow: 'hidden' },
  policyList: { borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  policyListHeader: { padding: '20px 24px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  policyListTitle: { fontFamily: 'var(--font-display)', fontSize: '22px', textTransform: 'uppercase' },
  policyItem: { padding: '16px 24px', borderBottom: '1px solid var(--text-black)', cursor: 'pointer', transition: 'background 0.15s' },
  policyItemActive: { padding: '16px 24px', borderBottom: '1px solid var(--text-black)', cursor: 'pointer', background: 'rgba(0,0,0,0.06)', borderLeft: '4px solid var(--text-black)' },
  policyName: { fontFamily: 'var(--font-serif)', fontSize: '15px', textTransform: 'uppercase', fontWeight: 600, display: 'block' },
  policyMeta: { fontFamily: 'var(--font-body)', fontSize: '10px', opacity: 0.5, textTransform: 'uppercase', marginTop: '4px', display: 'block' },
  policyStatus: { fontFamily: 'var(--font-body)', fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', padding: '2px 6px', marginTop: '8px', display: 'inline-block' },
  editorSection: { display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  editorHeader: { padding: '16px 32px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  editorTitle: { fontFamily: 'var(--font-display)', fontSize: '22px', textTransform: 'uppercase' },
  toolbar: { padding: '10px 32px', borderBottom: '1px solid var(--text-black)', display: 'flex', gap: '8px', background: 'rgba(0,0,0,0.03)' },
  toolbarBtn: { padding: '6px 14px', background: 'transparent', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
  toolbarBtnActive: { padding: '6px 14px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
  editorArea: { flex: 1, padding: '32px', overflowY: 'auto' },
  editorTextarea: { width: '100%', minHeight: '400px', border: 'none', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '14px', lineHeight: 1.8, resize: 'none', outline: 'none', boxSizing: 'border-box' },
  editorFooter: { padding: '12px 32px', borderTop: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.03)' },
  footerMeta: { fontFamily: 'var(--font-body)', fontSize: '10px', opacity: 0.5, textTransform: 'uppercase' },
  btnSolid: { padding: '10px 24px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  btnOutline: { padding: '10px 24px', background: 'transparent', color: 'var(--text-black)', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  versionPanel: { borderLeft: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  versionHeader: { padding: '20px 20px', borderBottom: '1px solid var(--text-black)', fontFamily: 'var(--font-display)', fontSize: '18px', textTransform: 'uppercase' },
  versionItem: { padding: '14px 20px', borderBottom: '1px solid var(--text-black)', cursor: 'pointer', transition: 'background 0.15s' },
  versionLabel: { fontFamily: 'var(--font-serif)', fontSize: '14px', fontWeight: 600, display: 'block' },
  versionDate: { fontFamily: 'var(--font-body)', fontSize: '10px', opacity: 0.5, marginTop: '4px', display: 'block' },
  versionAuthor: { fontFamily: 'var(--font-body)', fontSize: '10px', opacity: 0.7, marginTop: '2px', display: 'block' },
  versionBadge: { fontFamily: 'var(--font-body)', fontSize: '9px', fontWeight: 800, padding: '2px 6px', border: '1px solid var(--text-black)', textTransform: 'uppercase', marginTop: '6px', display: 'inline-block' },
  errorBox: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackPolicies = [
  { name: 'Terms of Service', category: 'Legal', lastUpdated: 'Mar 01, 2025', status: 'Published' },
  { name: 'Privacy Policy', category: 'Legal', lastUpdated: 'Feb 20, 2025', status: 'Published' },
  { name: 'Cookie Policy', category: 'Compliance', lastUpdated: 'Jan 15, 2025', status: 'Published' },
  { name: 'Anti-Discrimination', category: 'HR Policy', lastUpdated: 'Feb 28, 2025', status: 'Draft' },
  { name: 'Data Retention', category: 'Compliance', lastUpdated: 'Dec 10, 2024', status: 'Review' },
  { name: 'Acceptable Use', category: 'Platform', lastUpdated: 'Nov 05, 2024', status: 'Published' },
  { name: 'Refund Policy', category: 'Billing', lastUpdated: 'Jan 22, 2025', status: 'Published' },
];

const fallbackContent = "1. ACCEPTANCE OF TERMS\n\nBy accessing or using the TalentOrbit platform (\"Service\"), you agree to be bound by these Terms of Service (\"Terms\"). If you do not agree to all of these Terms, you may not access or use the Service.\n\n2. DESCRIPTION OF SERVICE\n\nTalentOrbit provides a talent management and recruitment platform that connects employers with job seekers. The Service includes job posting, candidate management, AI-powered matching, sponsored listings, and related features.\n\n3. USER ACCOUNTS\n\nYou must register for an account to access certain features. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.\n\n4. EMPLOYER RESPONSIBILITIES\n\nEmployers agree to:\n- Post accurate and non-discriminatory job listings\n- Comply with all applicable employment laws\n- Handle candidate data in accordance with our Privacy Policy\n- Not misuse sponsored post features\n\n5. CANDIDATE RIGHTS\n\nCandidates have the right to:\n- Access and delete their personal data\n- Opt out of AI-powered recommendations\n- Report discriminatory listings\n- Withdraw applications at any time";

const fallbackVersions = [
  { label: 'v3.2 \u2014 Current', date: 'Mar 01, 2025', author: 'Legal Team', current: true },
  { label: 'v3.1', date: 'Jan 15, 2025', author: 'Sarah K.', current: false },
  { label: 'v3.0', date: 'Nov 20, 2024', author: 'Legal Team', current: false },
  { label: 'v2.8', date: 'Sep 01, 2024', author: 'Alex M.', current: false },
  { label: 'v2.7', date: 'Jun 15, 2024', author: 'Legal Team', current: false },
  { label: 'v2.5', date: 'Mar 10, 2024', author: 'Sarah K.', current: false },
];

const PolicyManager = () => {
    // Zod validation for policy content editing
    const { policyContentSchema } = require('../utils/schemas');
    const [formError, setFormError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleSaveContent = async (e) => {
      e.preventDefault();
      setFormError('');
      setSubmitting(true);
      try {
        const result = policyContentSchema.safeParse({ content: editorContent });
        if (!result.success) {
          setFormError(result.error.errors[0]?.message || 'Validation error');
          setSubmitting(false);
          return;
        }
        // TODO: Call API to save policy content
        addToast('Policy content saved!', 'success');
        setSubmitting(false);
      } catch (err) {
        setFormError('Unexpected error. Please try again.');
        setSubmitting(false);
      }
    };
  usePageTitle('Policy Manager', 'Manage legal and compliance documents.');
  const { addToast } = useToast();
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activePolicy, setActivePolicy] = useState(0);
  const [editorContent, setEditorContent] = useState(fallbackContent);
  const [contentLoading, setContentLoading] = useState(false);
  const versions = fallbackVersions;

  const loadPolicies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await complianceService.getPolicies();
      const policyData = Array.isArray(data) ? data : data.results || data.policies || [];
      setPolicies(policyData.length > 0 ? policyData : fallbackPolicies);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to load policies.'));
      setPolicies(fallbackPolicies);
      addToast(getApiErrorMessage(err, 'Using fallback policy data.'), 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { loadPolicies(); }, [loadPolicies]);

  const displayPolicies = policies.length > 0 ? policies : fallbackPolicies;

  const loadPolicyContent = useCallback(async (index) => {
    setActivePolicy(index);
    const policy = displayPolicies[index];
    if (policy?.id) {
      setContentLoading(true);
      try {
        const { data } = await complianceService.getPolicy(policy.id);
        setEditorContent(data.content || data.body || data.text || fallbackContent);
      } catch (err) {
        addToast(getApiErrorMessage(err, 'Failed to load policy content.'), 'error');
        setEditorContent(fallbackContent);
      } finally {
        setContentLoading(false);
      }
    } else {
      setEditorContent(fallbackContent);
    }
  }, [displayPolicies, addToast]);

  const currentPolicy = displayPolicies[activePolicy] || displayPolicies[0] || { name: 'Policy', category: 'N/A', status: 'Draft' };

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Compliance', status: 'Governance Module', info: loading ? 'Loading...' : 'Ready' }}
      pageTitleLine1="Policy"
      pageTitleLine2="Manager"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Total Policies</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{displayPolicies.length} Documents</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Last Audit</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>Feb 28, 2025</p>
          </div>
        </div>
      }
    >
      {error && (
        <div style={styles.errorBox}>
          <p style={styles.errorText}>{error}</p>
          <button style={styles.retryBtn} onClick={loadPolicies}>Retry</button>
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={styles.bodyGrid}>
          <div style={styles.policyList}>
            <div style={styles.policyListHeader}>
              <h2 style={styles.policyListTitle}>Documents</h2>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 }}>{displayPolicies.length}</span>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {loading ? (
                <div style={{ padding: '24px' }}><Skeleton.List count={7} /></div>
              ) : (
                displayPolicies.map((policy, i) => (
                  <div key={policy.id || i} style={i === activePolicy ? styles.policyItemActive : styles.policyItem} onClick={() => loadPolicyContent(i)}
                    onMouseEnter={e => { if (i !== activePolicy) e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }}
                    onMouseLeave={e => { if (i !== activePolicy) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <span style={styles.policyName}>{policy.name || policy.title}</span>
                    <span style={styles.policyMeta}>{policy.category || policy.type || 'General'} {'\u2022'} Updated {policy.lastUpdated || policy.updated_at || 'N/A'}</span>
                    <span style={{ ...styles.policyStatus, background: (policy.status || '').toLowerCase() === 'published' ? 'var(--text-black)' : 'transparent', color: (policy.status || '').toLowerCase() === 'published' ? 'var(--bg-beige)' : 'var(--text-black)', border: '1px solid var(--text-black)' }}>{policy.status || 'Draft'}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div style={styles.editorSection}>
            <div style={styles.editorHeader}>
              <h2 style={styles.editorTitle}>{currentPolicy.name || currentPolicy.title}</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button style={styles.btnOutline}>Preview</button>
                <button style={styles.btnSolid}>Publish</button>
              </div>
            </div>
            <div style={styles.toolbar}>
              <button style={styles.toolbarBtnActive}>B</button>
              <button style={styles.toolbarBtn}>I</button>
              <button style={styles.toolbarBtn}>U</button>
              <span style={{ width: '1px', background: 'var(--text-black)', margin: '0 4px' }} />
              <button style={styles.toolbarBtn}>H1</button>
              <button style={styles.toolbarBtn}>H2</button>
              <button style={styles.toolbarBtn}>H3</button>
              <span style={{ width: '1px', background: 'var(--text-black)', margin: '0 4px' }} />
              <button style={styles.toolbarBtn}>{'\u2022'} List</button>
              <button style={styles.toolbarBtn}>1. List</button>
              <button style={styles.toolbarBtn}>Link</button>
            </div>
            <form onSubmit={handleSaveContent}>
              <div style={styles.editorArea}>
                {contentLoading ? <Skeleton.Text lines={12} /> : (
                  <textarea style={styles.editorTextarea} value={editorContent} onChange={e => setEditorContent(e.target.value)} />
                )}
              </div>
              {formError && <div style={{ color: 'red', margin: '8px 0' }}>{formError}</div>}
              <div style={styles.editorFooter}>
                <span style={styles.footerMeta}>{editorContent.split(/\s+/).length} words {'\u2022'} Last saved 2 min ago</span>
                <span style={styles.footerMeta}>Version {versions[0].label}</span>
                <button type="submit" style={styles.btnSolid} disabled={submitting}>
                  {submitting ? 'Saving...' : 'Save Content'}
                </button>
              </div>
            </form>
          </div>

          <div style={styles.versionPanel}>
            <div style={styles.versionHeader}>Version History</div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {versions.map((v, i) => (
                <div key={i} style={styles.versionItem} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
                  <span style={styles.versionLabel}>{v.label}</span>
                  <span style={styles.versionDate}>{v.date}</span>
                  <span style={styles.versionAuthor}>By {v.author}</span>
                  {v.current && <span style={{ ...styles.versionBadge, background: 'var(--text-black)', color: 'var(--bg-beige)' }}>Current</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default PolicyManager;
