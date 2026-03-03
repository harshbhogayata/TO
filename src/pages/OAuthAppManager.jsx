import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import developerService from '../services/developerService';
import { useDeveloperStore } from '../store/developerStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './OAuthAppManager.css';

/* ── Available OAuth scopes (mirrors backend) ─────────────────── */
const OAUTH_SCOPES = [
    'user.read', 'user.write',
    'job.read', 'job.post',
    'assessment.read', 'assessment.write',
    'analytics.all', 'webhook.manage',
];

const STATUS_FILTERS = ['all', 'active', 'pending', 'suspended', 'revoked'];

/* ── Register App Modal ───────────────────────────────────────── */
const RegisterAppModal = ({ open, onClose, onCreated }) => {
    const [form, setForm] = useState({
        name: '',
        redirect_uris: '',
        scopes: ['user.read'],
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (open) setForm({ name: '', redirect_uris: '', scopes: ['user.read'] });
    }, [open]);

    if (!open) return null;

    const toggleScope = (scope) => {
        setForm((prev) => ({
            ...prev,
            scopes: prev.scopes.includes(scope)
                ? prev.scopes.filter((s) => s !== scope)
                : [...prev.scopes, scope],
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const uris = form.redirect_uris
                .split('\n')
                .map((u) => u.trim())
                .filter(Boolean);
            const { data } = await developerService.createOAuthApp({
                name: form.name,
                redirect_uris: uris,
                scopes: form.scopes,
            });
            onCreated(data);
            onClose();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to register application.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="oa-modal-backdrop" onClick={onClose}>
            <form className="oa-modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
                <h2>Register New Application</h2>
                <div className="oa-modal-field">
                    <label>Application Name</label>
                    <input
                        type="text"
                        className="oa-input"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="e.g. My Integration App"
                        required
                    />
                </div>
                <div className="oa-modal-field">
                    <label>Redirect URIs (one per line)</label>
                    <textarea
                        className="oa-textarea"
                        value={form.redirect_uris}
                        onChange={(e) => setForm({ ...form, redirect_uris: e.target.value })}
                        placeholder={'https://myapp.com/callback\nhttps://localhost:3000/auth'}
                        rows={3}
                    />
                </div>
                <div className="oa-modal-field">
                    <label>Requested Scopes</label>
                    <div className="oa-scope-checkbox-grid">
                        {OAUTH_SCOPES.map((scope) => (
                            <label key={scope} className="oa-scope-checkbox-item">
                                <input
                                    type="checkbox"
                                    checked={form.scopes.includes(scope)}
                                    onChange={() => toggleScope(scope)}
                                />
                                {scope}
                            </label>
                        ))}
                    </div>
                </div>
                <div className="oa-modal-actions">
                    <button type="button" className="oa-modal-cancel" onClick={onClose}>Cancel</button>
                    <button
                        type="submit"
                        className="oa-modal-submit"
                        disabled={saving || !form.name.trim() || form.scopes.length === 0}
                    >
                        {saving ? 'Registering...' : 'Generate Credentials'}
                    </button>
                </div>
            </form>
        </div>
    );
};

/* ── App Card ─────────────────────────────────────────────────── */
const AppCard = ({ app, onRevoke }) => {
    const status = app.status || 'active';
    const isRevoked = status === 'revoked';

    const formatDate = (iso) => {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    };

    const maskedSecret = app.client_secret_prefix
        ? `${app.client_secret_prefix}${'•'.repeat(20)}`
        : '••••••••••••••••••••';

    return (
        <div className={`oa-card ${isRevoked ? 'oa-card--revoked' : ''}`}>
            <div className="oa-card__header">
                <div className="oa-card__logo">
                    {app.logo_initials || app.name?.substring(0, 2).toUpperCase() || 'AP'}
                </div>
                <div>
                    <div className="oa-card__name">{app.name}</div>
                    <div className="oa-card__client-id">{app.client_id}</div>
                </div>
                <span className={`oa-status oa-status--${status}`}>
                    {status}
                </span>
            </div>

            <div className="oa-card__details">
                <div className="oa-detail">
                    <div className="oa-detail__label">Client Secret</div>
                    <div className="oa-detail__value oa-detail__value--mono">{maskedSecret}</div>
                </div>
                <div className="oa-detail">
                    <div className="oa-detail__label">Authorized Users</div>
                    <div className="oa-detail__value">{(app.authorized_users_count || 0).toLocaleString()}</div>
                </div>
                <div className="oa-detail">
                    <div className="oa-detail__label">Created</div>
                    <div className="oa-detail__value">{formatDate(app.created_at)}</div>
                </div>
                <div className="oa-detail">
                    <div className="oa-detail__label">{isRevoked ? 'Revoked' : 'Last Updated'}</div>
                    <div className="oa-detail__value">
                        {isRevoked ? formatDate(app.revoked_at) : formatDate(app.updated_at || app.created_at)}
                    </div>
                </div>
            </div>

            {/* Scopes */}
            <div className="oa-scopes">
                {(app.scopes || []).map((scope, i) => (
                    <span key={i} className="oa-scope-tag">{scope}</span>
                ))}
            </div>

            {/* Redirect URIs */}
            {(app.redirect_uris || []).length > 0 && (
                <ul className="oa-redirect-list">
                    {app.redirect_uris.map((uri, i) => (
                        <li key={i}>{uri}</li>
                    ))}
                </ul>
            )}

            {/* Actions */}
            {!isRevoked && (
                <div className="oa-card__actions">
                    <button
                        className="oa-revoke-btn"
                        onClick={() => onRevoke(app.id, app.name)}
                    >
                        Revoke Application
                    </button>
                </div>
            )}
        </div>
    );
};

/* ── Main Component ───────────────────────────────────────────── */
const OAuthAppManager = () => {
    const {
        oauthApps, oauthAppsLoading, oauthAppsError,
        setOauthApps, setOauthAppsLoading, setOauthAppsError,
    } = useDeveloperStore();

    const [showModal, setShowModal] = useState(false);
    const [newRawSecret, setNewRawSecret] = useState(null);
    const [copied, setCopied] = useState(false);
    const [statusFilter, setStatusFilter] = useState('all');

    usePageTitle('OAuth Apps', 'Register and manage OAuth 2.0 applications.');

    const fetchApps = useCallback(async () => {
        setOauthAppsLoading(true);
        setOauthAppsError(null);
        try {
            const params = statusFilter !== 'all' ? { status: statusFilter } : {};
            const { data } = await developerService.listOAuthApps(params);
            setOauthApps(data.results || data);
        } catch (err) {
            setOauthAppsError(getApiErrorMessage(err, 'Failed to load OAuth apps.'));
        } finally {
            setOauthAppsLoading(false);
        }
    }, [statusFilter, setOauthApps, setOauthAppsLoading, setOauthAppsError]);

    useEffect(() => { fetchApps(); }, [fetchApps]);

    const handleRevoke = async (id, name) => {
        if (!window.confirm(`Revoke "${name}"? All authorized users will lose access immediately.`)) return;
        try {
            await developerService.revokeOAuthApp(id);
            fetchApps();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to revoke application.'));
        }
    };

    const handleCreated = (data) => {
        if (data.client_secret) {
            setNewRawSecret(data.client_secret);
        }
        fetchApps();
    };

    const handleCopySecret = () => {
        navigator.clipboard.writeText(newRawSecret).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Admin Console',
                status: 'System Status: Operational',
                info: 'Settings > OAuth Apps',
            }}
            pageTitleLine1="OAuth"
            pageTitleLine2="Applications"
            headerRightContent={
                <div className="oa-header-actions">
                    <button className="oa-create-btn" onClick={() => setShowModal(true)}>
                        + Register Application
                    </button>
                </div>
            }
        >
            <div className="oa-layout">
                {oauthAppsError && <div className="oa-error-banner">{oauthAppsError}</div>}

                {/* New client secret banner */}
                {newRawSecret && (
                    <div className="oa-secret-banner">
                        <div>
                            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6, color: '#cf8e6d' }}>
                                ⚠ Client Secret — Copy now, it won't be shown again
                            </div>
                            <div className="oa-secret-banner__text">{newRawSecret}</div>
                        </div>
                        <button className="oa-secret-banner__copy" onClick={handleCopySecret}>
                            {copied ? 'Copied!' : 'Copy'}
                        </button>
                    </div>
                )}

                {/* Filter Tabs */}
                <div className="oa-filters">
                    {STATUS_FILTERS.map((filter) => (
                        <button
                            key={filter}
                            className={`oa-filter-btn ${statusFilter === filter ? 'oa-filter-btn--active' : ''}`}
                            onClick={() => setStatusFilter(filter)}
                        >
                            {filter.charAt(0).toUpperCase() + filter.slice(1)}
                        </button>
                    ))}
                </div>

                {/* App Cards */}
                {oauthAppsLoading ? (
                    <div className="oa-grid">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <div key={i} className="oa-card">
                                <div className="oa-card__header">
                                    <Skeleton style={{ width: 44, height: 44, borderRadius: 10 }} />
                                    <div style={{ flex: 1 }}>
                                        <Skeleton style={{ width: '60%', height: 16, marginBottom: 6 }} />
                                        <Skeleton style={{ width: '40%', height: 12 }} />
                                    </div>
                                </div>
                                <Skeleton style={{ width: '100%', height: 60, marginTop: 12 }} />
                                <Skeleton style={{ width: '70%', height: 14, marginTop: 12 }} />
                            </div>
                        ))}
                    </div>
                ) : oauthApps.length === 0 ? (
                    <div className="oa-empty">
                        {statusFilter !== 'all'
                            ? `No ${statusFilter} applications found.`
                            : 'No OAuth applications registered. Create one to enable third-party integrations.'
                        }
                    </div>
                ) : (
                    <div className="oa-grid">
                        {oauthApps.map((app) => (
                            <AppCard key={app.id} app={app} onRevoke={handleRevoke} />
                        ))}
                    </div>
                )}
            </div>

            <RegisterAppModal
                open={showModal}
                onClose={() => setShowModal(false)}
                onCreated={handleCreated}
            />
        </DashboardLayout>
    );
};

export default OAuthAppManager;
