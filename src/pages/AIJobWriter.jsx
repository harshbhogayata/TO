import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useAIStore } from '../store/aiStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';
import { jobDescriptionSchema } from '../utils/schemas';

/* == Styles (content-level only) == */
const styles = {
  viewGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1 },
  sectionHeader: { padding: '24px 32px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  sectionTitle: { fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' },
  formContainer: { padding: '32px' },
  formGroup: { marginBottom: '24px' },
  formLabel: { display: 'block', fontFamily: 'var(--font-serif)', fontSize: '14px', textTransform: 'uppercase', marginBottom: '8px' },
  formInput: { width: '100%', padding: '12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '13px', boxSizing: 'border-box' },
  formSelect: { width: '100%', padding: '12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '13px', boxSizing: 'border-box' },
  formTextarea: { width: '100%', padding: '12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '13px', minHeight: '120px', resize: 'vertical', boxSizing: 'border-box' },
  btnSolid: { padding: '16px 32px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  btnOutline: { padding: '16px 32px', background: 'transparent', color: 'var(--text-black)', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  previewPanel: { borderLeft: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column' },
  previewContent: { padding: '32px', flex: 1 },
  previewJobTitle: { fontFamily: 'var(--font-display)', fontSize: '32px', textTransform: 'uppercase', marginBottom: '8px' },
  previewCompany: { fontFamily: 'var(--font-serif)', fontSize: '16px', textTransform: 'uppercase', opacity: 0.7, marginBottom: '24px' },
  previewSection: { marginBottom: '20px' },
  previewSectionLabel: { fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase', fontWeight: 700, marginBottom: '8px', display: 'block' },
  previewText: { fontFamily: 'var(--font-body)', fontSize: '13px', lineHeight: 1.6, opacity: 0.8 },
  tagRow: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' },
  tag: { padding: '4px 10px', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', border: '1px solid var(--text-black)' },
  tagDark: { padding: '4px 10px', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', border: '1px solid var(--text-black)', background: 'var(--text-black)', color: 'var(--bg-beige)' },
  aiSuggestion: { padding: '16px', border: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)', marginBottom: '16px' },
  aiLabel: { fontFamily: 'var(--font-body)', fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px', display: 'block' },
};

const AIJobWriter = () => {
  usePageTitle('AI Job Writer', 'AI-powered job description generation.');
  const { generatedJD, jdLoading, jdError, generateJobDescription, clearGeneratedJD } = useAIStore();
  const { addToast } = useToast();

  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [location, setLocation] = useState('');
  const [type, setType] = useState('Full-Time');
  const [salary, setSalary] = useState('');
  const [description, setDescription] = useState('');
  const [requirements, setRequirements] = useState('');

  useEffect(() => () => clearGeneratedJD(), [clearGeneratedJD]);

  const handleGenerate = useCallback(async () => {
    const parsed = jobDescriptionSchema.safeParse({ title, company, location, type, salary, description, requirements });
    if (!parsed.success) {
      const firstError = parsed.error.issues[0];
      addToast(firstError.message, 'error');
      return;
    }
    try {
      await generateJobDescription(parsed.data);
      addToast('Job description generated!', 'success');
    } catch (err) {
      addToast(getApiErrorMessage(err, 'Failed to generate job description.'), 'error');
    }
  }, [title, company, location, type, salary, description, requirements, generateJobDescription, addToast]);

  const previewTitle = generatedJD?.title || title || 'Job Title';
  const previewCompany = generatedJD?.company || company || 'Company';
  const previewLocation = generatedJD?.location || location || 'Location';
  const previewDesc = generatedJD?.description || description || 'No description yet...';
  const previewReqs = generatedJD?.requirements || requirements || '';

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // AI Composer', status: 'Intelligence Module', info: jdLoading ? 'Generating...' : 'Ready' }}
      pageTitleLine1="AI Job"
      pageTitleLine2="Writer"
      headerRightContent={<button style={styles.btnOutline} onClick={clearGeneratedJD} disabled={!generatedJD}>Clear</button>}
    >
      <div style={styles.viewGrid}>
        <div>
          <div style={styles.sectionHeader}><h2 style={styles.sectionTitle}>Compose</h2></div>
          <div style={styles.formContainer}>
            {jdError && <div style={{ ...styles.aiSuggestion, background: 'rgba(200,0,0,0.06)' }}>⚠ {jdError}</div>}
            <div style={styles.aiSuggestion}>
              <span style={styles.aiLabel}>✦ AI Suggestion</span>
              <p style={{ fontFamily: 'var(--font-body)', fontSize: '12px', lineHeight: 1.5, opacity: 0.8 }}>
                Consider adding &ldquo;collaborative environment&rdquo; and &ldquo;growth opportunities&rdquo; &mdash; posts with these keywords see 32% more applications.
              </p>
            </div>
            <div style={styles.formGroup}><label style={styles.formLabel}>Job Title</label><input style={styles.formInput} value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Senior Product Designer" /></div>
            <div style={styles.formGroup}><label style={styles.formLabel}>Company</label><input style={styles.formInput} value={company} onChange={e => setCompany(e.target.value)} placeholder="e.g. Volume One Studios" /></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div style={styles.formGroup}><label style={styles.formLabel}>Location</label><input style={styles.formInput} value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. Remote / New York" /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Type</label><select style={styles.formSelect} value={type} onChange={e => setType(e.target.value)}><option>Full-Time</option><option>Part-Time</option><option>Contract</option><option>Freelance</option></select></div>
            </div>
            <div style={styles.formGroup}><label style={styles.formLabel}>Salary Range</label><input style={styles.formInput} value={salary} onChange={e => setSalary(e.target.value)} placeholder="e.g. $120,000 - $160,000" /></div>
            <div style={styles.formGroup}><label style={styles.formLabel}>Description</label><textarea style={styles.formTextarea} value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe the role..." /></div>
            <div style={styles.formGroup}><label style={styles.formLabel}>Requirements</label><textarea style={{ ...styles.formTextarea, minHeight: '100px' }} value={requirements} onChange={e => setRequirements(e.target.value)} placeholder="One per line..." /></div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button style={styles.btnSolid} onClick={handleGenerate} disabled={jdLoading}>{jdLoading ? '✦ Generating...' : '✦ AI Enhance & Publish'}</button>
              <button style={styles.btnOutline} disabled={jdLoading}>Save Draft</button>
            </div>
          </div>
        </div>
        <div style={styles.previewPanel}>
          <div style={styles.sectionHeader}><h2 style={styles.sectionTitle}>Live Preview</h2><span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 }}>{generatedJD ? 'AI Generated' : 'Auto-Updating'}</span></div>
          <div style={styles.previewContent}>
            {jdLoading ? <Skeleton.Text lines={10} /> : (<>
              <h2 style={styles.previewJobTitle}>{previewTitle}</h2>
              <p style={styles.previewCompany}>{previewCompany} &bull; {previewLocation}</p>
              <div style={styles.tagRow}><span style={styles.tagDark}>{type}</span><span style={styles.tag}>{salary || 'Salary TBD'}</span><span style={styles.tag}>Remote OK</span></div>
              <div style={{ ...styles.previewSection, marginTop: '28px' }}><span style={styles.previewSectionLabel}>About the Role</span><p style={styles.previewText}>{previewDesc}</p></div>
              <div style={styles.previewSection}><span style={styles.previewSectionLabel}>Requirements</span><div style={styles.previewText}>{previewReqs.split('\n').filter(Boolean).map((line, i) => <p key={i} style={{ marginBottom: '4px' }}>&mdash; {line}</p>)}</div></div>
            </>)}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default AIJobWriter;
