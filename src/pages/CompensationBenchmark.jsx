import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useAIStore } from '../store/aiStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

const styles = {
  searchBar: { padding: '20px 40px', borderBottom: '1px solid var(--text-black)', display: 'flex', gap: '12px' },
  searchInput: { flex: 1, padding: '14px 16px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '14px' },
  searchBtn: { padding: '14px 32px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  bodyGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: '1px solid var(--text-black)' },
  chartSection: { padding: '32px', borderRight: '1px solid var(--text-black)' },
  chartLabel: { fontFamily: 'var(--font-serif)', fontSize: '14px', textTransform: 'uppercase', marginBottom: '20px', display: 'flex', justifyContent: 'space-between' },
  distributionChart: { height: '200px', display: 'flex', alignItems: 'flex-end', gap: '4px', borderBottom: '1px solid var(--text-black)', paddingBottom: '12px' },
  distBar: { flex: 1, background: 'var(--text-black)', transition: 'height 0.3s', position: 'relative' },
  trendChart: { height: '200px', position: 'relative', border: '1px solid var(--text-black)', overflow: 'hidden', background: 'linear-gradient(180deg, rgba(0,0,0,0.06) 0%, rgba(0,0,0,0.01) 100%)' },
  sectionHeader: { padding: '20px 32px', borderBottom: '1px solid var(--text-black)', fontFamily: 'var(--font-display)', fontSize: '28px', textTransform: 'uppercase' },
  cityGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderBottom: '1px solid var(--text-black)' },
  cityCard: { padding: '24px', borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', gap: '8px' },
  cityName: { fontFamily: 'var(--font-serif)', fontSize: '18px', textTransform: 'uppercase', fontWeight: 600 },
  citySalary: { fontFamily: 'var(--font-display)', fontSize: '28px' },
  cityDelta: { fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700 },
  breakdownGrid: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', borderBottom: '1px solid var(--text-black)' },
  breakdownItem: { padding: '20px', borderRight: '1px solid var(--text-black)', display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'center' },
  breakdownLabel: { fontFamily: 'var(--font-body)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', opacity: 0.6 },
  breakdownValue: { fontFamily: 'var(--font-display)', fontSize: '22px' },
  axisLabels: { display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontFamily: 'var(--font-body)', fontSize: '10px', opacity: 0.5, textTransform: 'uppercase' },
  errorBox: { padding: '20px 40px', borderBottom: '1px solid var(--text-black)', background: 'rgba(200,0,0,0.06)' },
  errorText: { fontFamily: 'var(--font-body)', fontSize: '13px' },
  retryBtn: { marginTop: '8px', padding: '8px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer' },
};

const fallbackDistBars = [
  { h: '15%' }, { h: '25%' }, { h: '40%' }, { h: '60%' }, { h: '85%' },
  { h: '95%' }, { h: '80%' }, { h: '55%' }, { h: '35%' }, { h: '20%' },
  { h: '12%' }, { h: '8%' },
];

const fallbackCities = [
  { name: 'San Francisco', salary: '$185k', delta: '+12% vs avg', up: true },
  { name: 'New York', salary: '$172k', delta: '+8% vs avg', up: true },
  { name: 'London', salary: '$148k', delta: '-2% vs avg', up: false },
  { name: 'Berlin', salary: '$128k', delta: '-14% vs avg', up: false },
];

const fallbackBreakdown = [
  { label: 'Base Salary', value: '$142k' },
  { label: 'Bonus', value: '$18k' },
  { label: 'Equity/RSU', value: '$35k' },
  { label: 'Benefits', value: '$12k' },
  { label: 'Total Comp', value: '$207k' },
];

const CompensationBenchmark = () => {
  usePageTitle('Compensation Benchmark', 'Market salary intelligence and benchmarking.');
  const { compensationData, compensationLoading, compensationError, fetchCompensation, clearCompensation } = useAIStore();
  const { addToast } = useToast();
  const [searchRole, setSearchRole] = useState('Senior Product Designer');

  useEffect(() => () => clearCompensation(), [clearCompensation]);

  const handleSearch = useCallback(async () => {
    if (!searchRole.trim()) { addToast('Please enter a role to benchmark.', 'warning'); return; }
    try {
      await fetchCompensation(searchRole);
      addToast('Compensation data loaded!', 'success');
    } catch (err) {
      addToast(getApiErrorMessage(err, 'Failed to fetch compensation data.'), 'error');
    }
  }, [searchRole, fetchCompensation, addToast]);

  const cities = compensationData?.cities || fallbackCities;
  const breakdown = compensationData?.breakdown || fallbackBreakdown;
  const distBars = compensationData?.distribution || fallbackDistBars;
  const p25 = compensationData?.p25 || '$128k';
  const median = compensationData?.median || '$155k';
  const p75 = compensationData?.p75 || '$185k';
  const yoyGrowth = compensationData?.yoy_growth || '+8.4%';

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // Compensation', status: 'Market Intelligence', info: compensationLoading ? 'Analyzing...' : 'Ready' }}
      pageTitleLine1="Comp"
      pageTitleLine2="ensation"
      headerRightContent={
        <div style={{ display: 'flex', gap: '30px', textAlign: 'right' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Data Sources</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>142k Reports</p>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '12px', textTransform: 'uppercase' }}>Last Updated</h3>
            <p style={{ fontSize: '11px', opacity: 0.7 }}>Real-Time</p>
          </div>
        </div>
      }
    >
      <div style={styles.searchBar}>
        <input style={styles.searchInput} value={searchRole} onChange={e => setSearchRole(e.target.value)} placeholder="Search role title, e.g. Senior Product Designer" onKeyDown={e => e.key === 'Enter' && handleSearch()} />
        <button style={styles.searchBtn} onClick={handleSearch} disabled={compensationLoading}>{compensationLoading ? 'Loading...' : 'Benchmark'}</button>
      </div>

      {compensationError && (
        <div style={styles.errorBox}>
          <p style={styles.errorText}>{compensationError}</p>
          <button style={styles.retryBtn} onClick={handleSearch}>Retry</button>
        </div>
      )}

      {compensationLoading ? (
        <div style={{ padding: '40px' }}><Skeleton.Text lines={8} /><div style={{ marginTop: '24px' }}><Skeleton.List count={4} /></div></div>
      ) : (
        <>
          <div style={styles.bodyGrid}>
            <div style={styles.chartSection}>
              <div style={styles.chartLabel}><span>Salary Distribution</span><span style={{ opacity: 0.5 }}>P25: {p25} {'\u2014'} Median: {median} {'\u2014'} P75: {p75}</span></div>
              <div style={styles.distributionChart}>
                {distBars.map((bar, i) => <div key={i} style={{ ...styles.distBar, height: bar.h }} />)}
              </div>
              <div style={styles.axisLabels}><span>$80k</span><span>$120k</span><span>$160k</span><span>$200k</span><span>$240k+</span></div>
            </div>
            <div style={{ padding: '32px' }}>
              <div style={styles.chartLabel}><span>YoY Trend</span><span style={{ opacity: 0.5 }}>{yoyGrowth} Annual Growth</span></div>
              <div style={styles.trendChart}>
                <svg style={{ width: '100%', height: '100%' }} viewBox="0 0 400 200" preserveAspectRatio="none">
                  <path d="M0,180 L40,170 L80,160 L120,155 L160,140 L200,130 L240,115 L280,105 L320,90 L360,75 L400,60 L400,200 L0,200 Z" fill="rgba(0,0,0,0.08)" />
                  <polyline fill="none" stroke="var(--text-black)" strokeWidth="2" points="0,180 40,170 80,160 120,155 160,140 200,130 240,115 280,105 320,90 360,75 400,60" />
                </svg>
              </div>
              <div style={styles.axisLabels}><span>2020</span><span>2022</span><span>2024</span></div>
            </div>
          </div>

          <div style={styles.sectionHeader}>City Comparison</div>
          <div style={styles.cityGrid}>
            {cities.map((city, i) => (
              <div key={i} style={{ ...styles.cityCard, ...(i === cities.length - 1 ? { borderRight: 'none' } : {}) }}>
                <span style={styles.cityName}>{city.name}</span>
                <span style={styles.citySalary}>{city.salary}</span>
                <span style={{ ...styles.cityDelta, color: city.up ? 'var(--text-black)' : '#666' }}>{city.delta}</span>
              </div>
            ))}
          </div>

          <div style={styles.sectionHeader}>Total Compensation Breakdown</div>
          <div style={styles.breakdownGrid}>
            {breakdown.map((item, i) => (
              <div key={i} style={{ ...styles.breakdownItem, ...(i === breakdown.length - 1 ? { borderRight: 'none', background: 'rgba(0,0,0,0.04)' } : {}) }}>
                <span style={styles.breakdownLabel}>{item.label}</span>
                <span style={styles.breakdownValue}>{item.value}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </DashboardLayout>
  );
};

export default CompensationBenchmark;
