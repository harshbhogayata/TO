import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import Skeleton from '../components/Skeleton';
import { intelligenceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './CompanyAnalytics.css';

const FUNNEL_COLORS = ['#111111', '#333333', '#555555', '#777777', '#2e7d32', '#1b5e20'];

const CompanyAnalytics = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('Company Analytics', 'Data-driven hiring insights for your organization.');

    const [overview, setOverview] = useState(null);
    const [funnel, setFunnel] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [benchmarks, setBenchmarks] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [overviewRes, funnelRes, jobsRes, benchmarksRes] = await Promise.all([
                    intelligenceService.getAnalyticsOverview(),
                    intelligenceService.getAnalyticsFunnel(),
                    intelligenceService.getJobPerformance(),
                    intelligenceService.getBenchmarks(),
                ]);
                // overview → {total_views, total_applications, application_change, active_jobs, total_jobs}
                setOverview(overviewRes.data);
                // funnel → {stages: [{name, count, conversion_rate}], total_views, total_applications, rejected, withdrawn}
                setFunnel(funnelRes.data?.stages || []);
                // jobs → [{id, title, status, views, applications, shortlisted, interviewing, offered, days_active, health}]
                setJobs(Array.isArray(jobsRes.data) ? jobsRes.data : jobsRes.data?.results || []);
                // benchmarks → [{name, your_value, platform_avg, industry_avg, sample_size}]
                setBenchmarks(benchmarksRes.data);
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load analytics.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const formatNum = (n) => n != null ? Number(n).toLocaleString() : '—';
    const formatDec = (n, d = 1) => n != null ? Number(n).toFixed(d) : '—';

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Company Intelligence",
                status: "Data Pipeline: Active / 200 OK",
                info: `Client: ${user?.company_name || user?.email?.split('@')[0] || 'Company'}`
            }}
            pageTitleLine1="Company"
            pageTitleLine2="Analytic"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Period</h3>
                        <p>Last 30 Days</p>
                    </div>
                </div>
            }
        >
            {isLoading ? (
                <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <div className="ca-metric-row">
                        <Skeleton.Stat /><Skeleton.Stat /><Skeleton.Stat />
                    </div>
                    <Skeleton height={160} />
                    <Skeleton.List count={3} />
                </div>
            ) : (
                <div className="ca-grid">
                    <div className="ca-stats-panel">
                        {/* ── Metric Cards ── */}
                        <div className="ca-metric-row">
                            <div className="ca-metric-card">
                                <span className="ca-metric-label">Total Applications</span>
                                <span className="ca-metric-value">{formatNum(overview?.total_applications)}</span>
                                {overview?.application_change != null && (
                                    <span className={`ca-metric-trend ${Number(overview.application_change) >= 0 ? 'ca-metric-trend--positive' : 'ca-metric-trend--negative'}`}>
                                        {Number(overview.application_change) >= 0 ? '↑' : '↓'} {Math.abs(overview.application_change).toFixed(1)}% vs Prev 30d
                                    </span>
                                )}
                            </div>
                            <div className="ca-metric-card">
                                <span className="ca-metric-label">Active Listings</span>
                                <span className="ca-metric-value">{formatNum(overview?.active_jobs)}</span>
                                {overview?.total_jobs != null && (
                                    <span className="ca-metric-trend">
                                        {overview.total_jobs} total jobs
                                    </span>
                                )}
                            </div>
                            <div className="ca-metric-card">
                                <span className="ca-metric-label">Total Views</span>
                                <span className="ca-metric-value">{formatNum(overview?.total_views)}</span>
                            </div>
                        </div>

                        {/* ── Funnel ── */}
                        <span className="ca-section-label">Applicant Funnel Performance</span>
                        <div className="ca-funnel">
                            {funnel.length > 0 ? funnel.map((stage, i) => {
                                const maxCount = funnel[0]?.count || 1;
                                const pct = Math.max(5, (stage.count / maxCount) * 100);
                                return (
                                    <div
                                        key={stage.name || i}
                                        className="ca-funnel-stage"
                                        style={{
                                            width: `${pct}%`,
                                            background: FUNNEL_COLORS[i] || '#111111',
                                        }}
                                    >
                                        {stage.name}: {formatNum(stage.count)}
                                        {stage.conversion_rate != null && ` (${stage.conversion_rate}%)`}
                                    </div>
                                );
                            }) : (
                                <div className="ca-empty">No funnel data available yet.</div>
                            )}
                        </div>

                        {/* ── Performance Table ── */}
                        <span className="ca-section-label">Top Performing Listings</span>
                        <div className="ca-table-wrap">
                            <table className="ca-table">
                                <thead>
                                    <tr>
                                        <th>Role Name</th>
                                        <th>Views</th>
                                        <th>Apps</th>
                                        <th>Shortlisted</th>
                                        <th>Health</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {jobs.length > 0 ? jobs.map((job) => (
                                        <tr key={job.id || job.title}>
                                            <td style={{ fontWeight: 600 }}>{job.title}</td>
                                            <td>{formatNum(job.views)}</td>
                                            <td>{formatNum(job.applications)}</td>
                                            <td>{formatNum(job.shortlisted)}</td>
                                            <td className={job.health === 'healthy' ? 'ca-quality-high' : ''} style={{ fontWeight: 700, textTransform: 'capitalize' }}>
                                                {job.health || '—'}
                                            </td>
                                        </tr>
                                    )) : (
                                        <tr>
                                            <td colSpan={5} className="ca-empty" style={{ textAlign: 'center' }}>
                                                No job performance data yet.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* ── Right Sidebar ── */}
                    <div className="ca-sidebar-wrapper">
                        <div className="ca-sidebar-meta">
                            {/* Benchmarks comparison */}
                            {Array.isArray(benchmarks) && benchmarks.length > 0 ? (
                                benchmarks.map((b, i) => (
                                    <div key={i} className="ca-meta-section">
                                        <span className="ca-meta-label">{b.name || 'Metric'}</span>
                                        <div className="ca-ratio-ring">
                                            <span className="ca-ratio-text">
                                                {typeof b.your_value === 'number' ? b.your_value.toFixed(2) : '—'}
                                            </span>
                                        </div>
                                        <p className="ca-meta-desc">
                                            Platform avg: {typeof b.platform_avg === 'number' ? b.platform_avg.toFixed(2) : '—'}
                                            {b.industry_avg ? ` • Industry avg: ${b.industry_avg.toFixed(2)}` : ''}
                                            {b.sample_size ? ` • Sample: ${b.sample_size}` : ''}
                                        </p>
                                    </div>
                                ))
                            ) : (
                                <div className="ca-meta-section">
                                    <span className="ca-meta-label">Benchmarks</span>
                                    <p className="ca-meta-desc">
                                        Benchmark data will appear once enough hiring data has been collected.
                                    </p>
                                </div>
                            )}

                            <div className="ca-meta-section">
                                <span className="ca-meta-label">AI Intelligence Insight</span>
                                <p className="ca-insight-text">
                                    {overview ? `Your ${overview.active_jobs || 0} active jobs have received ${overview.total_applications || 0} applications with ${overview.application_change != null && overview.application_change >= 0 ? 'positive' : overview.application_change != null ? 'declining' : 'neutral'} momentum.` : 'AI insights will appear once enough hiring data has been collected.'}
                                </p>
                            </div>
                        </div>
                        <VerticalLabel text="System Metrics // Intelligence" />
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default CompanyAnalytics;
