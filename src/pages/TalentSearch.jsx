import { useState, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useToast } from '../contexts/ToastContext';
import { searchService, getApiErrorMessage } from '../services/api';

const styles = {
  searchBar: { padding: '20px 40px', borderBottom: '1px solid var(--text-black)', display: 'flex', gap: '12px' },
  searchInput: { flex: 1, padding: '14px 16px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '14px' },
  searchBtn: { padding: '14px 32px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  bodyGrid: { display: 'grid', gridTemplateColumns: '260px 1fr', flex: 1, overflow: 'hidden' },
  filterSidebar: { borderRight: '1px solid var(--text-black)', overflowY: 'auto', padding: '0' },
  filterSection: { borderBottom: '1px solid var(--text-black)', padding: '20px' },
  filterTitle: { fontFamily: 'var(--font-display)', fontSize: '16px', textTransform: 'uppercase', marginBottom: '12px' },
  filterOption: { display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', fontFamily: 'var(--font-body)', fontSize: '12px', cursor: 'pointer' },
  checkbox: { width: '14px', height: '14px', border: '1px solid var(--text-black)', background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', cursor: 'pointer' },
  checkboxActive: { width: '14px', height: '14px', border: '1px solid var(--text-black)', background: 'var(--text-black)', color: 'var(--bg-beige)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', cursor: 'pointer' },
  resultsArea: { overflowY: 'auto', padding: '0' },
  resultsHeader: { padding: '16px 24px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.03)' },
  resultsCount: { fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.6 },
  sortSelect: { padding: '6px 12px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '11px' },
  candidateCard: { padding: '24px', borderBottom: '1px solid var(--text-black)', display: 'grid', gridTemplateColumns: '48px 1fr auto', gap: '16px', alignItems: 'start', cursor: 'pointer', transition: 'background 0.15s' },
  avatar: { width: '48px', height: '48px', background: 'var(--text-black)', color: 'var(--bg-beige)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontSize: '18px' },
  candidateName: { fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase', fontWeight: 600, display: 'block' },
  candidateRole: { fontFamily: 'var(--font-body)', fontSize: '12px', opacity: 0.7, marginTop: '2px', display: 'block' },
  candidateLocation: { fontFamily: 'var(--font-body)', fontSize: '11px', opacity: 0.5, marginTop: '2px', display: 'block' },
  tagRow: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '10px' },
  tag: { padding: '3px 8px', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)' },
  tagDark: { padding: '3px 8px', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', border: '1px solid var(--text-black)', background: 'var(--text-black)', color: 'var(--bg-beige)', fontFamily: 'var(--font-body)' },
  matchScore: { fontFamily: 'var(--font-display)', fontSize: '24px', textAlign: 'right' },
  matchLabel: { fontFamily: 'var(--font-body)', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5, textAlign: 'right', display: 'block' },
  applyFiltersBtn: { width: '100%', padding: '12px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
  errorBox: { padding: '20px 24px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackCandidates = [
  { initials: 'AR', name: 'Alex Rivera', role: 'Senior Product Designer', location: 'San Francisco, CA \u2022 Remote', score: '94%', tags: ['Figma', 'Design Systems', 'Prototyping'], featured: true },
  { initials: 'SC', name: 'Sarah Chen', role: 'Lead UX Researcher', location: 'New York, NY \u2022 Hybrid', score: '91%', tags: ['User Testing', 'Analytics', 'Workshop Facilitation'], featured: false },
  { initials: 'MJ', name: 'Marc Johnson', role: 'Frontend Engineer', location: 'Austin, TX \u2022 Remote', score: '88%', tags: ['React', 'TypeScript', 'CSS Architecture'], featured: true },
  { initials: 'EV', name: 'Elena Vance', role: 'Creative Director', location: 'Los Angeles, CA \u2022 On-site', score: '97%', tags: ['Brand Strategy', 'Team Leadership', 'Art Direction'], featured: true },
  { initials: 'JS', name: 'Jordan Smith', role: 'Python Architect', location: 'Seattle, WA \u2022 Remote', score: '92%', tags: ['Django', 'System Design', 'ML/AI'], featured: false },
  { initials: 'LK', name: 'Lisa Kim', role: 'Product Manager', location: 'Chicago, IL \u2022 Hybrid', score: '86%', tags: ['Roadmapping', 'Stakeholders', 'Agile'], featured: false },
];

const TalentSearch = () => {
  usePageTitle('Talent Search', 'Search and discover top talent profiles.');
  const { addToast } = useToast();
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({ remote: true, fullTime: true, senior: false, designSkills: true, engineeringSkills: false });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggleFilter = (key) => setFilters(prev => ({ ...prev, [key]: !prev[key] }));

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { q: query };
      if (filters.remote) params.remote = true;
      if (filters.fullTime) params.type = 'full-time';
      if (filters.senior) params.seniority = 'senior';
      if (filters.designSkills) params.skills = 'design';
      if (filters.engineeringSkills) params.skills = (params.skills ? params.skills + ',engineering' : 'engineering');
      const { data } = await searchService.getTalentProfiles(params);
      setResults(Array.isArray(data) ? data : data.results || []);
      addToast('Search complete!', 'success');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to search talent profiles.'));
      addToast(getApiErrorMessage(err, 'Search failed.'), 'error');
    } finally {
      setLoading(false);
    }
  }, [query, filters, addToast]);

  const candidates = results.length > 0
    ? results.map(r => ({
        initials: (r.name || 'U').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(),
        name: r.name || r.full_name || 'Unknown',
        role: r.role || r.title || 'Candidate',
        location: r.location || 'Location N/A',
        score: r.match_score ? r.match_score + '%' : 'N/A',
        tags: r.skills || r.tags || [],
        featured: r.featured || false,
      }))
    : fallbackCandidates;

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Search', status: 'Discovery Module', info: loading ? 'Searching...' : 'Ready' }}
      pageTitleLine1="Talent"
      pageTitleLine2="Search"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Total Profiles</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>284,000+</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Active Today</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>12,400</p>
          </div>
        </div>
      }
    >
      <div style={styles.searchBar}>
        <input style={styles.searchInput} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by name, role, skill, or keyword..." onKeyDown={e => e.key === 'Enter' && handleSearch()} />
        <button style={styles.searchBtn} onClick={handleSearch} disabled={loading}>{loading ? 'Searching...' : 'Search'}</button>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={styles.bodyGrid}>
          <div style={styles.filterSidebar}>
            <div style={styles.filterSection}>
              <div style={styles.filterTitle}>Work Type</div>
              <div style={styles.filterOption} onClick={() => toggleFilter('remote')}>
                <div style={filters.remote ? styles.checkboxActive : styles.checkbox}>{filters.remote ? '\u2713' : ''}</div>Remote
              </div>
              <div style={styles.filterOption} onClick={() => toggleFilter('fullTime')}>
                <div style={filters.fullTime ? styles.checkboxActive : styles.checkbox}>{filters.fullTime ? '\u2713' : ''}</div>Full-Time
              </div>
            </div>
            <div style={styles.filterSection}>
              <div style={styles.filterTitle}>Seniority</div>
              <div style={styles.filterOption} onClick={() => toggleFilter('senior')}>
                <div style={filters.senior ? styles.checkboxActive : styles.checkbox}>{filters.senior ? '\u2713' : ''}</div>Senior (5+ yrs)
              </div>
            </div>
            <div style={styles.filterSection}>
              <div style={styles.filterTitle}>Skills</div>
              <div style={styles.filterOption} onClick={() => toggleFilter('designSkills')}>
                <div style={filters.designSkills ? styles.checkboxActive : styles.checkbox}>{filters.designSkills ? '\u2713' : ''}</div>Design & Creative
              </div>
              <div style={styles.filterOption} onClick={() => toggleFilter('engineeringSkills')}>
                <div style={filters.engineeringSkills ? styles.checkboxActive : styles.checkbox}>{filters.engineeringSkills ? '\u2713' : ''}</div>Engineering
              </div>
            </div>
            <div style={{ padding: '20px' }}>
              <button style={styles.applyFiltersBtn} onClick={handleSearch} disabled={loading}>Apply Filters</button>
            </div>
          </div>

          <div style={styles.resultsArea}>
            {error && (
              <div style={styles.errorBox}>
                <p style={styles.errorText}>{error}</p>
                <button style={styles.retryBtn} onClick={handleSearch}>Retry</button>
              </div>
            )}
            <div style={styles.resultsHeader}>
              <span style={styles.resultsCount}>{candidates.length} Results Found</span>
              <select style={styles.sortSelect}><option>Sort: Match Score</option><option>Sort: Recent Activity</option><option>Sort: Experience</option></select>
            </div>
            {loading ? (
              <div style={{ padding: '24px' }}><Skeleton.List count={6} /></div>
            ) : (
              candidates.map((c, i) => (
                <div key={i} style={styles.candidateCard} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
                  <div style={styles.avatar}>{c.initials}</div>
                  <div>
                    <span style={styles.candidateName}>{c.name}</span>
                    <span style={styles.candidateRole}>{c.role}</span>
                    <span style={styles.candidateLocation}>{c.location}</span>
                    <div style={styles.tagRow}>
                      {c.tags.map((tag, ti) => <span key={ti} style={c.featured && ti === 0 ? styles.tagDark : styles.tag}>{tag}</span>)}
                    </div>
                  </div>
                  <div>
                    <div style={styles.matchScore}>{c.score}</div>
                    <span style={styles.matchLabel}>Match</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default TalentSearch;
