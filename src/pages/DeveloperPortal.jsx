import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import developerService from '../services/developerService';
import { useDeveloperStore } from '../store/developerStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './DeveloperPortal.css';

/* ── Static SDK data ─────────────────────────────────────────── */
const SDK_LIST = [
    { name: 'JavaScript', version: 'v2.1.0', desc: 'Works in Node.js and browser environments.' },
    { name: 'Python', version: 'v1.8.4', desc: 'Compatible with Python 3.8+.' },
    { name: 'Go-Lang', version: 'v0.9.1', desc: 'Lightweight Go module with full API coverage.' },
];

/* ── Endpoint sidebar item ───────────────────────────────────── */
const EndpointItem = ({ method, path, active, onClick }) => {
    const badgeClass = `dp-method-badge dp-method-badge--${method.toLowerCase()}`;
    return (
        <div
            className={`dp-endpoint-item ${active ? 'dp-endpoint-item--active' : ''}`}
            onClick={onClick}
        >
            <span className={badgeClass}>{method}</span>
            <span className="dp-endpoint-path">{path}</span>
        </div>
    );
};

/* ── SDK Card ────────────────────────────────────────────────── */
const SdkCard = ({ name, version }) => (
    <div className="dp-sdk-card">
        <span className="dp-sdk-card__name">{name}</span>
        <span className="dp-sdk-card__version">{version}</span>
    </div>
);

/* ── Main Component ──────────────────────────────────────────── */
const DeveloperPortal = () => {
    const {
        portalStats, portalStatsLoading,
        endpoints, rateLimits, changelog, changelogLoading,
        setPortalStats, setPortalStatsLoading, setPortalStatsError,
        setEndpoints, setRateLimits, setChangelog, setChangelogLoading,
    } = useDeveloperStore();

    const [activeTab, setActiveTab] = useState('quickstart');
    const [selectedEndpoint, setSelectedEndpoint] = useState(null);

    usePageTitle('Developer Portal', 'API documentation, SDKs, and integration guides.');

    /* Fetch all portal data */
    const fetchPortalData = useCallback(async () => {
        setPortalStatsLoading(true);
        setChangelogLoading(true);
        try {
            const [statsRes, endpointsRes, limitsRes, changelogRes] = await Promise.all([
                developerService.getPortalStats().catch(() => ({ data: null })),
                developerService.getEndpoints(),
                developerService.getRateLimits(),
                developerService.listChangelog(),
            ]);
            if (statsRes.data) setPortalStats(statsRes.data);
            setEndpoints(endpointsRes.data || []);
            setRateLimits(limitsRes.data || []);
            setChangelog((changelogRes.data?.results || changelogRes.data || []));
        } catch (err) {
            setPortalStatsError(getApiErrorMessage(err, 'Failed to load portal data.'));
        } finally {
            setPortalStatsLoading(false);
            setChangelogLoading(false);
        }
    }, [setPortalStats, setPortalStatsLoading, setPortalStatsError, setEndpoints, setRateLimits, setChangelog, setChangelogLoading]);

    useEffect(() => { fetchPortalData(); }, [fetchPortalData]);

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit API v4.0.2',
                status: 'API Status: Stable',
                info: 'Env: Production',
            }}
            pageTitleLine1="Dev"
            pageTitleLine2="Portal"
            headerRightContent={
                <div className="dp-header-stats">
                    <div className="dp-stat-block">
                        <h3>Uptime</h3>
                        <p>99.99% Annual</p>
                    </div>
                    <div className="dp-stat-block">
                        <h3>Latency</h3>
                        <p>42ms Global Avg</p>
                    </div>
                    {portalStats && (
                        <div className="dp-stat-block">
                            <h3>24h Calls</h3>
                            <p>{portalStats.total_api_calls_24h?.toLocaleString() ?? '—'}</p>
                        </div>
                    )}
                </div>
            }
        >
            <div className="dp-layout">
                {/* ── Endpoint Sidebar ─────────────────────── */}
                <aside className="dp-sidebar">
                    <div className="dp-sidebar__title">API Endpoints</div>
                    {endpoints.length === 0 ? (
                        Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="dp-endpoint-item">
                                <div className="dp-skeleton" style={{ width: 36, height: 14 }} />
                                <div className="dp-skeleton" style={{ width: '60%', height: 14 }} />
                            </div>
                        ))
                    ) : (
                        endpoints.map((ep, i) => (
                            <EndpointItem
                                key={i}
                                method={ep.method}
                                path={ep.path}
                                active={selectedEndpoint === i}
                                onClick={() => setSelectedEndpoint(i)}
                            />
                        ))
                    )}
                </aside>

                {/* ── Center Content ──────────────────────── */}
                <div className="dp-center">
                    <div className="dp-tabs">
                        {['quickstart', 'auth', 'rate-limits'].map((t) => (
                            <button
                                key={t}
                                className={`dp-tab ${activeTab === t ? 'dp-tab--active' : ''}`}
                                onClick={() => setActiveTab(t)}
                            >
                                {t === 'quickstart' ? 'Quick Start' : t === 'auth' ? 'Auth Guide' : 'Rate Limits'}
                            </button>
                        ))}
                    </div>

                    {/* Quick Start */}
                    {activeTab === 'quickstart' && (
                        <div className="dp-section">
                            <h3 className="dp-section__title">Getting Started</h3>
                            <p className="dp-section__text">
                                All requests must be signed with a Bearer Token obtained via the OAuth2 flow.
                                Tokens are valid for 3600 seconds. Include your API key in the Authorization header.
                            </p>
                            <div className="dp-code-block">
{`curl -X GET "https://api.talentorbit.com/v1/jobs" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Accept: application/json"`}
                            </div>

                            {selectedEndpoint !== null && endpoints[selectedEndpoint] && (
                                <>
                                    <h3 className="dp-section__title">
                                        {endpoints[selectedEndpoint].method} {endpoints[selectedEndpoint].path}
                                    </h3>
                                    <p className="dp-section__text">
                                        {endpoints[selectedEndpoint].description}
                                    </p>
                                    <div className="dp-code-block">
{`curl -X ${endpoints[selectedEndpoint].method} \\
  "https://api.talentorbit.com${endpoints[selectedEndpoint].path}" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json"`}
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {/* Auth Guide */}
                    {activeTab === 'auth' && (
                        <div className="dp-section">
                            <h3 className="dp-section__title">OAuth 2.0 Authentication</h3>
                            <p className="dp-section__text">
                                TalentOrbit uses OAuth 2.0 for secure authentication. All API requests must
                                include a valid Bearer token. Tokens expire after 3600 seconds and must be
                                refreshed using the refresh token endpoint.
                            </p>

                            <div className="dp-auth-flow">
                                <span className="dp-auth-step">Client App</span>
                                <span className="dp-auth-arrow">→</span>
                                <span className="dp-auth-step">POST /auth/token</span>
                                <span className="dp-auth-arrow">→</span>
                                <span className="dp-auth-step">Access Token</span>
                                <span className="dp-auth-arrow">→</span>
                                <span className="dp-auth-step">API Request</span>
                                <span className="dp-auth-arrow">→</span>
                                <span className="dp-auth-step">Response</span>
                            </div>

                            <div className="dp-code-block">
{`POST /v1/auth/token

{
  "grant_type": "client_credentials",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}`}
                            </div>

                            <h3 className="dp-section__title">Token Refresh</h3>
                            <div className="dp-code-block">
{`POST /v1/auth/token/refresh

{
  "refresh": "YOUR_REFRESH_TOKEN"
}`}
                            </div>
                        </div>
                    )}

                    {/* Rate Limits */}
                    {activeTab === 'rate-limits' && (
                        <div className="dp-section">
                            <h3 className="dp-section__title">Rate Limit Tiers</h3>
                            <p className="dp-section__text">
                                Rate limits are enforced per API key. Exceeding the limit returns HTTP 429
                                with a Retry-After header. Enterprise customers can request custom limits.
                            </p>
                            <table className="dp-table">
                                <thead>
                                    <tr>
                                        <th>Tier</th>
                                        <th>Limit</th>
                                        <th>Window</th>
                                        <th>Burst</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rateLimits.map((rl, i) => (
                                        <tr key={i}>
                                            <td>{rl.tier}</td>
                                            <td>{rl.limit}</td>
                                            <td>{rl.window}</td>
                                            <td>{rl.burst}</td>
                                        </tr>
                                    ))}
                                    {rateLimits.length === 0 && (
                                        <tr><td colSpan={4} style={{ textAlign: 'center', opacity: 0.5 }}>Loading...</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* ── Right Panel ─────────────────────────── */}
                <div className="dp-right-panel">
                    <div className="dp-right-panel__title">Available SDKs</div>
                    <div className="dp-sdk-grid">
                        {SDK_LIST.map((sdk) => (
                            <SdkCard key={sdk.name} name={sdk.name} version={sdk.version} />
                        ))}
                    </div>

                    <div className="dp-changelog-section">
                        <div className="dp-right-panel__title">Recent Changes</div>
                        {changelogLoading ? (
                            Array.from({ length: 3 }).map((_, i) => (
                                <div key={i} className="dp-changelog-item">
                                    <div className="dp-skeleton" style={{ width: '40%', height: 10, marginBottom: 8 }} />
                                    <div className="dp-skeleton" style={{ width: '70%', height: 14, marginBottom: 6 }} />
                                    <div className="dp-skeleton" style={{ width: '90%', height: 12 }} />
                                </div>
                            ))
                        ) : changelog.length > 0 ? (
                            changelog.slice(0, 5).map((entry) => (
                                <div key={entry.id} className="dp-changelog-item">
                                    <div className="dp-changelog-item__date">
                                        {entry.published_at
                                            ? new Date(entry.published_at).toLocaleDateString('en-US', {
                                                month: 'short', day: 'numeric', year: 'numeric',
                                            }).toUpperCase()
                                            : 'DRAFT'}
                                    </div>
                                    <div className="dp-changelog-item__version">
                                        {entry.version} {entry.title}
                                    </div>
                                    <div className="dp-changelog-item__desc">{entry.description}</div>
                                </div>
                            ))
                        ) : (
                            <div className="dp-changelog-item">
                                <div className="dp-changelog-item__date">MAR 12, 2024</div>
                                <div className="dp-changelog-item__version">V4.0.2 Patch Release</div>
                                <div className="dp-changelog-item__desc">Fixed webhook retry logic for high-latency regions.</div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default DeveloperPortal;
