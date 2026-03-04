import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useToast } from '../contexts/ToastContext';
import { searchService, getApiErrorMessage } from '../services/api';

const styles = {
  featuredHero: { display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--text-black)', minHeight: '220px' },
  heroLeft: { padding: '40px', borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', justifyContent: 'center' },
  heroLabel: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '12px', opacity: 0.5 },
  heroCompanyName: { fontFamily: 'var(--font-display)', fontSize: '48px', textTransform: 'uppercase', lineHeight: 0.9, marginBottom: '12px' },
  heroDescription: { fontFamily: 'var(--font-body)', fontSize: '13px', lineHeight: 1.6, opacity: 0.7, maxWidth: '400px' },
  heroRight: { background: 'var(--text-black)', color: 'var(--bg-beige)', padding: '40px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '20px' },
  heroStat: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' },
  heroStatLabel: { fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase', opacity: 0.6 },
  heroStatValue: { fontFamily: 'var(--font-display)', fontSize: '28px' },
  filterBar: { display: 'flex', borderBottom: '1px solid var(--text-black)', background: 'rgba(0,0,0,0.03)' },
  filterTab: { padding: '14px 24px', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', cursor: 'pointer', background: 'transparent', border: 'none', borderRight: '1px solid var(--text-black)' },
  filterTabActive: { padding: '14px 24px', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', cursor: 'pointer', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', borderRight: '1px solid var(--text-black)' },
  bodyGrid: { display: 'grid', gridTemplateColumns: '1fr 320px' },
  companyGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0' },
  companyCard: { padding: '24px', borderRight: '1px solid var(--text-black)', borderBottom: '1px solid var(--text-black)', cursor: 'pointer', transition: 'background 0.15s' },
  companyLogo: { width: '48px', height: '48px', background: 'var(--text-black)', color: 'var(--bg-beige)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontSize: '20px', marginBottom: '16px' },
  companyName: { fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: '4px' },
  companyIndustry: { fontFamily: 'var(--font-body)', fontSize: '11px', opacity: 0.6, textTransform: 'uppercase', display: 'block', marginBottom: '12px' },
  companyMeta: { display: 'flex', gap: '16px', marginTop: '8px' },
  metaItem: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.5 },
  companyRating: { fontFamily: 'var(--font-display)', fontSize: '14px', marginTop: '8px', display: 'block' },
  leaderboard: { borderLeft: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column' },
  leaderboardHeader: { padding: '20px 24px', borderBottom: '1px solid var(--text-black)', fontFamily: 'var(--font-display)', fontSize: '22px', textTransform: 'uppercase' },
  leaderboardItem: { padding: '16px 24px', borderBottom: '1px solid var(--text-black)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  leaderboardRank: { fontFamily: 'var(--font-display)', fontSize: '24px', marginRight: '16px', opacity: 0.3 },
  leaderboardName: { fontFamily: 'var(--font-serif)', fontSize: '14px', textTransform: 'uppercase', fontWeight: 600 },
  leaderboardScore: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 800, border: '1px solid var(--text-black)', padding: '2px 6px' },
  errorBox: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackCompanies = [
  { initials: 'VO', name: 'Volume One Studios', industry: 'Creative Agency', jobs: '12 Open', size: '200-500', rating: '4.8' },
  { initials: 'TF', name: 'TechFlow Solutions', industry: 'Enterprise SaaS', jobs: '24 Open', size: '1000+', rating: '4.5' },
  { initials: 'GB', name: 'Global Brands Inc.', industry: 'Marketing & Advertising', jobs: '8 Open', size: '500-1000', rating: '4.2' },
  { initials: 'BC', name: 'BuildIt Construction', industry: 'PropTech', jobs: '6 Open', size: '100-200', rating: '4.6' },
  { initials: 'DC', name: 'Design Collective', industry: 'UX Consultancy', jobs: '4 Open', size: '50-100', rating: '4.9' },
  { initials: 'NV', name: 'Nova Ventures', industry: 'Venture Capital', jobs: '3 Open', size: '20-50', rating: '4.7' },
  { initials: 'PX', name: 'PixelForge', industry: 'Game Studio', jobs: '18 Open', size: '200-500', rating: '4.4' },
  { initials: 'CL', name: 'CloudLayer', industry: 'Cloud Infrastructure', jobs: '32 Open', size: '1000+', rating: '4.3' },
  { initials: 'HB', name: 'HealthBridge', industry: 'HealthTech', jobs: '15 Open', size: '500-1000', rating: '4.1' },
];

const fallbackLeaderboard = [
  { rank: '01', name: 'Design Collective', score: '4.9' },
  { rank: '02', name: 'Volume One Studios', score: '4.8' },
  { rank: '03', name: 'Nova Ventures', score: '4.7' },
  { rank: '04', name: 'BuildIt Construction', score: '4.6' },
  { rank: '05', name: 'TechFlow Solutions', score: '4.5' },
];

const fallbackFeatured = {
  name: 'Volume One Studios', description: 'Award-winning creative agency building digital experiences for global brands. Known for bold design, experimental interfaces, and a culture that puts craft first.',
  positions: 12, avgSalary: '$145k', rating: '4.8/5', teamSize: 320,
};

const CompanyDirectory = () => {
  usePageTitle('Company Directory', 'Explore companies and employer profiles.');
  const { addToast } = useToast();
  const [activeFilter, setActiveFilter] = useState('All');
  const filters = ['All', 'Technology', 'Design', 'Finance', 'Healthcare', 'Startup'];
  const [companies, setCompanies] = useState([]);
  const [featured, setFeatured] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [compRes, featRes] = await Promise.all([
        searchService.getCompanyDirectory({ industry: activeFilter !== 'All' ? activeFilter : undefined }),
        searchService.getFeaturedEmployers(),
      ]);
      const compData = Array.isArray(compRes.data) ? compRes.data : compRes.data?.results || [];
      setCompanies(compData);
      const featData = Array.isArray(featRes.data) ? featRes.data[0] : featRes.data;
      setFeatured(featData || null);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to load company directory.'));
      addToast(getApiErrorMessage(err, 'Failed to load companies.'), 'error');
    } finally {
      setLoading(false);
    }
  }, [activeFilter, addToast]);

  useEffect(() => { loadData(); }, [loadData]);

  const displayCompanies = companies.length > 0
    ? companies.map(c => ({
        initials: (c.name || 'C').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(),
        name: c.name || 'Company',
        industry: c.industry || 'N/A',
        jobs: (c.open_jobs || c.jobs || 0) + ' Open',
        size: c.size || c.employee_count || 'N/A',
        rating: c.rating || 'N/A',
      }))
    : fallbackCompanies;

  const displayFeatured = featured ? {
    name: featured.name || fallbackFeatured.name,
    description: featured.description || fallbackFeatured.description,
    positions: featured.open_jobs || featured.positions || fallbackFeatured.positions,
    avgSalary: featured.avg_salary || fallbackFeatured.avgSalary,
    rating: featured.rating || fallbackFeatured.rating,
    teamSize: featured.team_size || featured.employee_count || fallbackFeatured.teamSize,
  } : fallbackFeatured;

  const leaderboard = companies.length > 0
    ? [...companies].sort((a, b) => (b.rating || 0) - (a.rating || 0)).slice(0, 5).map((c, i) => ({ rank: String(i + 1).padStart(2, '0'), name: c.name, score: String(c.rating || 'N/A') }))
    : fallbackLeaderboard;

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Directory', status: 'Employer Module', info: loading ? 'Loading...' : 'Ready' }}
      pageTitleLine1="Comp"
      pageTitleLine2="anies"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Listed</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>{displayCompanies.length > 9 ? displayCompanies.length.toLocaleString() : '2,400'} Companies</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Hiring Now</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>680 Active</p>
          </div>
        </div>
      }
    >
      {error && (
        <div style={styles.errorBox}>
          <p style={styles.errorText}>{error}</p>
          <button style={styles.retryBtn} onClick={loadData}>Retry</button>
        </div>
      )}

      {loading ? (
        <div style={{ padding: '40px' }}><Skeleton height={200} style={{ marginBottom: '24px' }} /><Skeleton.List count={6} /></div>
      ) : (
        <>
          <div style={styles.featuredHero}>
            <div style={styles.heroLeft}>
              <span style={styles.heroLabel}>{'\u2605'} Featured Company</span>
              <h2 style={styles.heroCompanyName}>{displayFeatured.name.split(' ').slice(0, 2).join(' ')}<br />{displayFeatured.name.split(' ').slice(2).join(' ')}</h2>
              <p style={styles.heroDescription}>{displayFeatured.description}</p>
            </div>
            <div style={styles.heroRight}>
              <div style={styles.heroStat}><span style={styles.heroStatLabel}>Open Positions</span><span style={styles.heroStatValue}>{displayFeatured.positions}</span></div>
              <div style={styles.heroStat}><span style={styles.heroStatLabel}>Avg. Salary</span><span style={styles.heroStatValue}>{displayFeatured.avgSalary}</span></div>
              <div style={styles.heroStat}><span style={styles.heroStatLabel}>Employee Rating</span><span style={styles.heroStatValue}>{displayFeatured.rating}</span></div>
              <div style={styles.heroStat}><span style={styles.heroStatLabel}>Team Size</span><span style={styles.heroStatValue}>{displayFeatured.teamSize}</span></div>
            </div>
          </div>

          <div style={styles.filterBar}>
            {filters.map((f) => (
              <button key={f} style={activeFilter === f ? styles.filterTabActive : styles.filterTab} onClick={() => setActiveFilter(f)}>{f}</button>
            ))}
          </div>

          <div style={{ display: 'flex' }}>
            <div style={{ flex: 1 }}>
              <div style={styles.bodyGrid}>
                <div style={styles.companyGrid}>
                  {displayCompanies.map((c, i) => (
                    <div key={i} style={styles.companyCard} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)'; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
                      <div style={styles.companyLogo}>{c.initials}</div>
                      <span style={styles.companyName}>{c.name}</span>
                      <span style={styles.companyIndustry}>{c.industry}</span>
                      <div style={styles.companyMeta}><span style={styles.metaItem}>{c.jobs}</span><span style={styles.metaItem}>{c.size}</span></div>
                      <span style={styles.companyRating}>{'\u2605'} {c.rating}</span>
                    </div>
                  ))}
                </div>
                <div style={styles.leaderboard}>
                  <div style={styles.leaderboardHeader}>Top Rated</div>
                  {leaderboard.map((item, i) => (
                    <div key={i} style={styles.leaderboardItem}>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <span style={styles.leaderboardRank}>{item.rank}</span>
                        <span style={styles.leaderboardName}>{item.name}</span>
                      </div>
                      <span style={styles.leaderboardScore}>{item.score}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
};

export default CompanyDirectory;
