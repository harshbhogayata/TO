import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import Skeleton from '../components/Skeleton';
import { intelligenceService, getApiErrorMessage } from '../services/api';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './AdminAnalytics.css';

const AdminAnalytics = () => {
    const { addToast } = useToast();
    usePageTitle('Platform Analytics', 'Global platform insights — users, postings, and system health.');

    const [metrics, setMetrics] = useState(null);
    const [signups, setSignups] = useState([]);
    const [engagement, setEngagement] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [metricsRes, growthRes, engagementRes] = await Promise.all([
                    intelligenceService.getPlatformMetrics(30),
                    intelligenceService.getPlatformGrowth(30),
                    intelligenceService.getPlatformEngagement(30),
                ]);

                // Platform metrics: array of daily snapshots (sorted by -date)
                // Fields: date, total_users, new_users, active_users_1d/7d/30d, talent_count,
                //         company_count, total_open_jobs, new_jobs_posted, jobs_closed,
                //         total_applications, new_applications, offers_extended,
                //         total_messages_sent, total_searches, avg_search_results,
                //         total_recommendation_requests, avg_recommendation_ctr
                const metricsArr = metricsRes.data || [];
                const latest = metricsArr[0] || {};
                const earliest = metricsArr[metricsArr.length - 1] || {};
                setMetrics({ latest, earliest, count: metricsArr.length, all: metricsArr });

                // Growth: array of {date, new_users, new_jobs_posted, new_applications}
                setSignups(growthRes.data || []);

                // Engagement: array of {date, active_users_1d, active_users_7d, active_users_30d, total_searches, total_messages_sent}
                setEngagement(engagementRes.data || []);
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load platform analytics.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const formatNum = (n) => n != null ? Number(n).toLocaleString() : '—';
    const formatPct = (n) => n != null ? `${Math.abs(Number(n)).toFixed(1)}%` : '';

    // Compute % change between earliest and latest period entry
    const trendPct = (field) => {
        const l = metrics?.latest?.[field];
        const e = metrics?.earliest?.[field];
        if (l == null || e == null || e === 0) return null;
        return ((l - e) / e) * 100;
    };

    // Derive system health from data freshness
    const latestDate = metrics?.latest?.date;
    const daysSinceLastMetric = latestDate
        ? Math.floor((Date.now() - new Date(latestDate).getTime()) / 86400000)
        : null;
    const healthStatus = daysSinceLastMetric == null ? 'unknown'
        : daysSinceLastMetric <= 1 ? 'nominal'
        : daysSinceLastMetric <= 3 ? 'warning'
        : 'error';
    const pulseClass = healthStatus === 'nominal' ? '' : healthStatus === 'unknown' ? '' : healthStatus === 'warning' ? ' aa-pulse--warning' : ' aa-pulse--error';

    // Build recent activity log from engagement time series
    const activityLog = engagement.slice(0, 5).map(e => ({
        date: e.date,
        message: `DAU: ${e.active_users_1d || 0} · Searches: ${e.total_searches || 0} · Messages: ${e.total_messages_sent || 0}`,
    }));

    // Engagement summary from latest entry
    const latestEngagement = engagement[0] || {};
    const totalSearches30d = engagement.reduce((sum, e) => sum + (e.total_searches || 0), 0);
    const totalMessages30d = engagement.reduce((sum, e) => sum + (e.total_messages_sent || 0), 0);

    // Compute bar heights from growth data (new_users per day)
    const recentSignups = signups.slice(-12);
    const maxSignup = Math.max(1, ...recentSignups.map(s => s.new_users || 0));
    const barData = recentSignups.map(s => ({
        height: `${Math.max(10, ((s.new_users || 0) / maxSignup) * 100)}%`,
        date: s.date || '',
        value: s.new_users || 0,
    }));

    // Fallback bars when no data
    const fallbackBars = [40, 60, 55, 85, 70, 95, 45, 30, 50, 75, 65, 80].map(h => ({
        height: `${h}%`, date: '', value: 0,
    }));
    const displayBars = barData.length > 0 ? barData : fallbackBars;

    // Geographic density from platform metrics (aggregate talent_count/company_count by date isn't geo,
    // so we show a decorative map with fallback dots)
    const mapDots = [
        { top: '30%', left: '20%', scale: 2.5 },
        { top: '45%', left: '25%', scale: 1.8 },
        { top: '35%', left: '65%', scale: 2.2 },
        { top: '70%', left: '75%', scale: 1.4 },
        { top: '25%', left: '85%', scale: 1.1 },
        { top: '60%', left: '45%', scale: 0.8 },
    ];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit Admin Console v2.1",
                status: `System Status: ${healthStatus === 'nominal' ? 'Operational' : healthStatus === 'warning' ? 'Delayed' : healthStatus === 'error' ? 'Stale Data' : 'Unknown'}`,
                info: `Last Sync: ${latestDate ? new Date(latestDate + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            }}
            pageTitleLine1="Global"
            pageTitleLine2="Insights"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Period: Last 30 Days</h3>
                        <p>{new Date(Date.now() - 30 * 86400000).toLocaleDateString('en-US', { month: 'short', day: '2-digit' }).toUpperCase()} — {new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit' }).toUpperCase()}</p>
                    </div>
                </div>
            }
        >
            {isLoading ? (
                <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <div className="aa-kpi-strip">
                        <Skeleton.Stat /><Skeleton.Stat /><Skeleton.Stat /><Skeleton.Stat />
                    </div>
                    <Skeleton height={200} />
                    <Skeleton height={200} />
                </div>
            ) : (
                <div className="aa-grid">
                    <div className="aa-body">
                        {/* ── KPI Strip ── */}
                        <div className="aa-kpi-strip">
                            {(() => {
                                const talentTrend = trendPct('talent_count');
                                const jobsTrend = trendPct('total_open_jobs');
                                const dauTrend = trendPct('active_users_1d');
                                const ctr = metrics?.latest?.avg_recommendation_ctr;
                                return (<>
                                    <div className="aa-kpi-card">
                                        <span className="aa-kpi-label">Total Talent</span>
                                        <span className="aa-kpi-value">{formatNum(metrics?.latest?.talent_count)}</span>
                                        {talentTrend != null && (
                                            <span className={`aa-kpi-trend${talentTrend < 0 ? ' aa-kpi-trend--negative' : ''}`}>
                                                {talentTrend >= 0 ? '↑' : '↓'} {formatPct(talentTrend)}
                                            </span>
                                        )}
                                    </div>
                                    <div className="aa-kpi-card">
                                        <span className="aa-kpi-label">Active Postings</span>
                                        <span className="aa-kpi-value">{formatNum(metrics?.latest?.total_open_jobs)}</span>
                                        {jobsTrend != null && (
                                            <span className={`aa-kpi-trend${jobsTrend < 0 ? ' aa-kpi-trend--negative' : ''}`}>
                                                {jobsTrend >= 0 ? '↑' : '↓'} {formatPct(jobsTrend)}
                                            </span>
                                        )}
                                    </div>
                                    <div className="aa-kpi-card">
                                        <span className="aa-kpi-label">Recommendation CTR</span>
                                        <span className="aa-kpi-value">
                                            {ctr != null ? `${(Number(ctr) * 100).toFixed(1)}%` : '—'}
                                        </span>
                                    </div>
                                    <div className="aa-kpi-card">
                                        <span className="aa-kpi-label">Daily Active Users</span>
                                        <span className="aa-kpi-value">{formatNum(metrics?.latest?.active_users_1d)}</span>
                                        {dauTrend != null && (
                                            <span className={`aa-kpi-trend${dauTrend < 0 ? ' aa-kpi-trend--negative' : ''}`}>
                                                {dauTrend >= 0 ? '↑' : '↓'} {formatPct(dauTrend)}
                                            </span>
                                        )}
                                    </div>
                                </>);
                            })()}
                        </div>

                        {/* ── Bar Chart: Daily Signups ── */}
                        <div className="aa-chart-section">
                            <div className="aa-chart-header">
                                <span className="aa-chart-title">Daily User Signups</span>
                                <span className="aa-chart-subtitle">Volume / 24h</span>
                            </div>
                            <div className="aa-bar-chart">
                                {displayBars.map((bar, i) => (
                                    <div key={i} className="aa-bar" style={{ height: bar.height }} title={bar.date ? `${bar.date}: ${bar.value} signups` : ''} />
                                ))}
                            </div>
                        </div>

                        {/* ── Geographic Density ── */}
                        <div className="aa-heatmap">
                            <span className="aa-chart-title">Geographic Talent Density</span>
                            <div className="aa-map">
                                {mapDots.map((dot, i) => (
                                    <div
                                        key={i}
                                        className="aa-dot"
                                        style={{ top: dot.top, left: dot.left, transform: `scale(${dot.scale})` }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* ── Right Sidebar ── */}
                    <div className="aa-right-wrapper">
                        <div className="aa-right-sidebar">
                            <div className="aa-status-panel">
                                <span className="aa-status-title">System Health</span>
                                <div className="aa-health-row">
                                    <div className={`aa-pulse${pulseClass}`} />
                                    <span className="aa-health-label">
                                        {healthStatus === 'nominal' ? 'Systems Nominal'
                                            : healthStatus === 'warning' ? 'Metrics Delayed'
                                            : healthStatus === 'error' ? 'Stale Data Alert'
                                            : 'Awaiting First Sync'}
                                    </span>
                                </div>

                                <span className="aa-status-title">Daily Engagement Feed</span>
                                <ul className="aa-log-list">
                                    {activityLog.length > 0 ? activityLog.map((entry, i) => (
                                        <li key={i} className="aa-log-item">
                                            <span className="aa-log-time">{entry.date}</span>
                                            {entry.message}
                                        </li>
                                    )) : (
                                        <li className="aa-empty">No engagement data yet.</li>
                                    )}
                                </ul>
                            </div>

                            <div className="aa-revenue">
                                <span className="aa-revenue-label">30-Day Engagement Volume</span>
                                <p className="aa-revenue-value">{formatNum(totalSearches30d)} searches</p>
                                <span className="aa-revenue-trend">
                                    {formatNum(totalMessages30d)} messages · WAU: {formatNum(latestEngagement.active_users_7d)}
                                </span>
                            </div>
                        </div>
                        <VerticalLabel text="Platform Operations // Control" />
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default AdminAnalytics;
