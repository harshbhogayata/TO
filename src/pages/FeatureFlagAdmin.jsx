import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useToast } from '../contexts/ToastContext';
import { intelligenceService, getApiErrorMessage } from '../services/api';

const styles = {
  statsStrip: { display: 'flex', borderBottom: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)' },
  statsItem: { flex: 1, padding: '14px 24px', borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', gap: '2px' },
  statsLabel: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.6 },
  statsValue: { fontFamily: 'var(--font-serif)', fontSize: '16px', fontWeight: 600 },
  bodyGrid: { display: 'grid', gridTemplateColumns: '1fr 380px', flex: 1 },
  flagList: { borderRight: '1px solid var(--text-black)' },
  flagListHeader: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  flagListTitle: { fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' },
  flagItem: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: '24px', alignItems: 'center' },
  flagName: { fontFamily: 'var(--font-serif)', fontSize: '16px', textTransform: 'uppercase', fontWeight: 600, display: 'block' },
  flagKey: { fontFamily: 'monospace', fontSize: '10px', opacity: 0.5, display: 'block', marginTop: '4px' },
  flagDescription: { fontFamily: 'var(--font-body)', fontSize: '11px', opacity: 0.6, marginTop: '4px', display: 'block' },
  toggleTrack: { width: '44px', height: '22px', borderRadius: '11px', border: '1px solid var(--text-black)', position: 'relative', cursor: 'pointer', transition: 'background 0.2s' },
  toggleThumb: { width: '16px', height: '16px', borderRadius: '50%', position: 'absolute', top: '2px', transition: 'left 0.2s' },
  rolloutBadge: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 800, padding: '3px 8px', border: '1px solid var(--text-black)', textTransform: 'uppercase' },
  envBadge: { fontFamily: 'var(--font-body)', fontSize: '9px', fontWeight: 700, padding: '2px 6px', textTransform: 'uppercase' },
  formPanel: { display: 'flex', flexDirection: 'column' },
  formPanelHeader: { padding: '20px 24px', borderBottom: '1px solid var(--text-black)', fontFamily: 'var(--font-display)', fontSize: '22px', textTransform: 'uppercase' },
  formContainer: { padding: '24px' },
  formGroup: { marginBottom: '20px' },
  formLabel: { display: 'block', fontFamily: 'var(--font-serif)', fontSize: '13px', textTransform: 'uppercase', marginBottom: '8px' },
  formInput: { width: '100%', padding: '12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '13px', boxSizing: 'border-box' },
  formSelect: { width: '100%', padding: '12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '13px', boxSizing: 'border-box' },
  btnSolid: { width: '100%', padding: '14px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  errorBox: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackFlags = [
  { name: 'AI Job Writer V2', key: 'ai_job_writer_v2', description: 'Enhanced AI-powered job description generation with GPT-4', enabled: true, rollout: '100%', env: 'Production' },
  { name: 'Dark Mode Beta', key: 'dark_mode_beta', description: 'Dark theme variant for the platform UI', enabled: true, rollout: '25%', env: 'Staging' },
  { name: 'Video Interviews', key: 'video_interviews', description: 'Built-in video interview recording and playback', enabled: false, rollout: '0%', env: 'Development' },
  { name: 'Smart Matching V3', key: 'smart_matching_v3', description: 'ML-based candidate-to-job matching algorithm', enabled: true, rollout: '50%', env: 'Production' },
  { name: 'Salary Transparency', key: 'salary_transparency', description: 'Display salary ranges on all job listings', enabled: false, rollout: '0%', env: 'Staging' },
  { name: 'Bulk Import API', key: 'bulk_import_api', description: 'CSV/JSON batch import for candidate profiles', enabled: true, rollout: '100%', env: 'Production' },
];

const Toggle = ({ enabled, onToggle }) => (
  <div style={{ ...styles.toggleTrack, background: enabled ? 'var(--text-black)' : 'transparent' }} onClick={onToggle}>
    <div style={{ ...styles.toggleThumb, left: enabled ? '24px' : '2px', background: enabled ? 'var(--bg-beige)' : 'var(--text-black)' }} />
  </div>
);

const FeatureFlagAdmin = () => {
  usePageTitle('Feature Flags', 'Manage feature flags and experiments.');
  const { addToast } = useToast();
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [newFlag, setNewFlag] = useState({ name: '', key: '', description: '', rollout: '0%', env: 'Development' });

  const loadFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await intelligenceService.getFeatureFlags();
      const flagData = Array.isArray(data) ? data : data.results || data.flags || [];
      setFlags(flagData.length > 0 ? flagData : fallbackFlags);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to load feature flags.'));
      setFlags(fallbackFlags);
      addToast(getApiErrorMessage(err, 'Using fallback flag data.'), 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { loadFlags(); }, [loadFlags]);

  const toggleFlag = useCallback(async (index) => {
    const flag = flags[index];
    const updated = { ...flag, enabled: !flag.enabled };
    setFlags(prev => prev.map((f, i) => i === index ? updated : f));
    try {
      if (flag.id) await intelligenceService.updateFeatureFlag(flag.id, { enabled: updated.enabled });
      addToast(updated.name + ' ' + (updated.enabled ? 'enabled' : 'disabled') + '.', 'success');
    } catch (err) {
      setFlags(prev => prev.map((f, i) => i === index ? flag : f));
      addToast(getApiErrorMessage(err, 'Failed to toggle flag.'), 'error');
    }
  }, [flags, addToast]);

  const handleCreate = useCallback(async () => {
    if (!newFlag.name || !newFlag.key) { addToast('Name and key are required.', 'warning'); return; }
    setCreating(true);
    try {
      const { data } = await intelligenceService.createFeatureFlag({ ...newFlag, enabled: false });
      setFlags(prev => [...prev, data || { ...newFlag, enabled: false }]);
      setNewFlag({ name: '', key: '', description: '', rollout: '0%', env: 'Development' });
      addToast('Feature flag created!', 'success');
    } catch (err) {
      addToast(getApiErrorMessage(err, 'Failed to create flag.'), 'error');
    } finally {
      setCreating(false);
    }
  }, [newFlag, addToast]);

  const displayFlags = flags.length > 0 ? flags : fallbackFlags;

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Experiments', status: 'Intelligence Module', info: loading ? 'Loading...' : 'Ready' }}
      pageTitleLine1="Feature"
      pageTitleLine2="Flags"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Total Flags</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{displayFlags.length} Configured</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Live</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{displayFlags.filter(f => f.enabled).length} Active</p>
          </div>
        </div>
      }
    >
      <div style={styles.statsStrip}>
        <div style={styles.statsItem}><span style={styles.statsLabel}>Production</span><span style={styles.statsValue}>{displayFlags.filter(f => f.env === 'Production').length} Flags</span></div>
        <div style={styles.statsItem}><span style={styles.statsLabel}>Staging</span><span style={styles.statsValue}>{displayFlags.filter(f => f.env === 'Staging').length} Flags</span></div>
        <div style={styles.statsItem}><span style={styles.statsLabel}>Development</span><span style={styles.statsValue}>{displayFlags.filter(f => f.env === 'Development').length} Flags</span></div>
        <div style={{ ...styles.statsItem, borderRight: 'none' }}><span style={styles.statsLabel}>Full Rollout</span><span style={styles.statsValue}>{displayFlags.filter(f => f.rollout === '100%').length} Flags</span></div>
      </div>

      {error && (
        <div style={styles.errorBox}>
          <p style={styles.errorText}>{error}</p>
          <button style={styles.retryBtn} onClick={loadFlags}>Retry</button>
        </div>
      )}

      <div style={{ display: 'flex', flex: 1 }}>
        <div style={styles.bodyGrid}>
          <div style={styles.flagList}>
            <div style={styles.flagListHeader}>
              <h2 style={styles.flagListTitle}>Live Flags</h2>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 }}>{displayFlags.length} Total</span>
            </div>
            {loading ? (
              <div style={{ padding: '24px' }}><Skeleton.List count={6} /></div>
            ) : (
              displayFlags.map((flag, i) => (
                <div key={flag.id || i} style={styles.flagItem}>
                  <div>
                    <span style={styles.flagName}>{flag.name}</span>
                    <span style={styles.flagKey}>{flag.key}</span>
                    <span style={styles.flagDescription}>{flag.description}</span>
                  </div>
                  <span style={{ ...styles.envBadge, background: flag.env === 'Production' ? 'var(--text-black)' : 'transparent', color: flag.env === 'Production' ? 'var(--bg-beige)' : 'var(--text-black)', border: '1px solid var(--text-black)' }}>{flag.env}</span>
                  <span style={styles.rolloutBadge}>{flag.rollout}</span>
                  <Toggle enabled={flag.enabled} onToggle={() => toggleFlag(i)} />
                </div>
              ))
            )}
          </div>

          <div style={styles.formPanel}>
            <div style={styles.formPanelHeader}>Configure New</div>
            <div style={styles.formContainer}>
              <div style={styles.formGroup}><label style={styles.formLabel}>Flag Name</label><input style={styles.formInput} value={newFlag.name} onChange={e => setNewFlag({ ...newFlag, name: e.target.value })} placeholder="e.g. Video Interviews" /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Flag Key</label><input style={styles.formInput} value={newFlag.key} onChange={e => setNewFlag({ ...newFlag, key: e.target.value })} placeholder="e.g. video_interviews" /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Description</label><input style={styles.formInput} value={newFlag.description} onChange={e => setNewFlag({ ...newFlag, description: e.target.value })} placeholder="Brief description of the feature" /></div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={styles.formGroup}><label style={styles.formLabel}>Rollout %</label><select style={styles.formSelect} value={newFlag.rollout} onChange={e => setNewFlag({ ...newFlag, rollout: e.target.value })}><option>0%</option><option>10%</option><option>25%</option><option>50%</option><option>75%</option><option>100%</option></select></div>
                <div style={styles.formGroup}><label style={styles.formLabel}>Environment</label><select style={styles.formSelect} value={newFlag.env} onChange={e => setNewFlag({ ...newFlag, env: e.target.value })}><option>Development</option><option>Staging</option><option>Production</option></select></div>
              </div>
              <button style={styles.btnSolid} onClick={handleCreate} disabled={creating}>{creating ? 'Creating...' : 'Create Flag'}</button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default FeatureFlagAdmin;
