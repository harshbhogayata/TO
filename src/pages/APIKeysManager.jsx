import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import developerService from '../services/developerService';
import { useDeveloperStore } from '../store/developerStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './APIKeysManager.css';

/* ── Sparkline component ─────────────────────────────────────── */
const Sparkline = ({ data = [] }) => {
    const max = Math.max(...data, 1);
    return (
        <div className="ak-sparkline">
            {data.map((val, i) => (
                <div
                    key={i}
                    className="ak-sparkline__bar"
                    style={{ height: `${(val / max) * 100}%` }}
                />
            ))}
        </div>
    );
};

/* ── Create Key Modal ────────────────────────────────────────── */
const AVAILABLE_SCOPES = [
    'read:jobs', 'write:jobs',
    'read:assessments', 'write:assessments',
    'read:users', 'write:users',
    'read:analytics', 'admin',
];

const CreateKeyModal = ({ open, onClose, onCreated }) => {
    const [form, setForm] = useState({ name: '', scopes: ['read:jobs'], ipAllowlist: '' });
    const [saving, setSaving] = useState(false);

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
            const payload = {
                name: form.name,
                scopes: form.scopes,
                ip_allowlist: form.ipAllowlist
                    ? form.ipAllowlist.split(',').map((s) => s.trim()).filter(Boolean)
                    : [],
            };
            const { data } = await developerService.createAPIKey(payload);
            onCreated(data);
            onClose();
            setForm({ name: '', scopes: ['read:jobs'], ipAllowlist: '' });
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to create API key.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="ak-modal-backdrop" onClick={onClose}>
            <form className="ak-modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
                <h2>Create New Key</h2>
                <div className="ak-modal-field">
                    <label>Key Name</label>
                    <input
                        type="text"
                        className="ak-input"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="e.g. Production Main"
                        required
                    />
                </div>
                <div className="ak-modal-field">
                    <label>Scopes</label>
                    <div className="ak-checkbox-grid">
                        {AVAILABLE_SCOPES.map((scope) => (
                            <label key={scope} className="ak-checkbox-item">
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
                <div className="ak-modal-field">
                    <label>IP Allowlist (Comma Separated)</label>
                    <input
                        type="text"
                        className="ak-input"
                        value={form.ipAllowlist}
                        onChange={(e) => setForm({ ...form, ipAllowlist: e.target.value })}
                        placeholder="192.168.1.1, 10.0.0.0/24"
                    />
                </div>
                <div className="ak-modal-actions">
                    <button type="button" className="ak-modal-cancel" onClick={onClose}>Cancel</button>
                    <button
                        type="submit"
                        className="ak-modal-submit"
                        disabled={saving || !form.name.trim() || form.scopes.length === 0}
                    >
                        {saving ? 'Creating...' : 'Generate Key'}
                    </button>
                </div>
            </form>
        </div>
    );
};

/* ── Main Component ──────────────────────────────────────────── */
const APIKeysManager = () => {
    const {
        apiKeys, apiKeysLoading, apiKeysError,
        setApiKeys, setApiKeysLoading, setApiKeysError,
    } = useDeveloperStore();

    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newRawKey, setNewRawKey] = useState(null);
    const [copied, setCopied] = useState(false);

    usePageTitle('API Keys', 'Manage API keys, scopes, and IP allowlists.');

    const fetchKeys = useCallback(async () => {
        setApiKeysLoading(true);
        setApiKeysError(null);
        try {
            const { data } = await developerService.listAPIKeys();
            setApiKeys(data.results || data);
        } catch (err) {
            setApiKeysError(getApiErrorMessage(err, 'Failed to load API keys.'));
        } finally {
            setApiKeysLoading(false);
        }
    }, [setApiKeys, setApiKeysLoading, setApiKeysError]);

    useEffect(() => { fetchKeys(); }, [fetchKeys]);

    const handleRevoke = async (id) => {
        if (!window.confirm('Revoke this API key? This action cannot be undone.')) return;
        try {
            await developerService.revokeAPIKey(id);
            fetchKeys();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to revoke key.'));
        }
    };

    const handleRotate = async (id) => {
        if (!window.confirm('Rotate this key? The old key will be revoked immediately.')) return;
        try {
            const { data } = await developerService.rotateAPIKey(id);
            setNewRawKey(data.raw_key);
            fetchKeys();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to rotate key.'));
        }
    };

    const handleKeyCreated = (data) => {
        if (data.raw_key) {
            setNewRawKey(data.raw_key);
        }
        fetchKeys();
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(newRawKey).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const formatDate = (iso) => {
        if (!iso) return 'Never';
        const d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    };

    const formatLastUsed = (iso) => {
        if (!iso) return 'Never';
        const diff = Date.now() - new Date(iso).getTime();
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return formatDate(iso);
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Admin Console',
                status: 'System Status: Operational',
                info: 'Settings > API Keys',
            }}
            pageTitleLine1="API"
            pageTitleLine2="Keys"
            headerRightContent={
                <div className="ak-header-actions">
                    <button className="ak-create-btn" onClick={() => setShowCreateModal(true)}>
                        + Create New Key
                    </button>
                </div>
            }
        >
            <div className="ak-layout">
                <div className="ak-content">
                    {apiKeysError && <div className="ak-error-banner">{apiKeysError}</div>}

                    {/* Raw key banner (shown once after creation) */}
                    {newRawKey && (
                        <div className="ak-raw-key-banner">
                            <div>
                                <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6, color: '#cf8e6d' }}>
                                    ⚠ Copy this key now — it won't be shown again
                                </div>
                                <div className="ak-raw-key-banner__text">{newRawKey}</div>
                            </div>
                            <button className="ak-raw-key-banner__copy" onClick={handleCopy}>
                                {copied ? 'Copied!' : 'Copy'}
                            </button>
                        </div>
                    )}

                    {/* Keys table */}
                    {apiKeysLoading ? (
                        <table className="ak-table">
                            <thead>
                                <tr>
                                    <th>Key Name</th><th>Prefix</th><th>Scopes</th>
                                    <th>Activity (7d)</th><th>Created / Last Used</th><th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Array.from({ length: 3 }).map((_, i) => (
                                    <tr key={i}>
                                        <td><Skeleton style={{ width: 120, height: 16 }} /></td>
                                        <td><Skeleton style={{ width: 100, height: 16 }} /></td>
                                        <td><Skeleton style={{ width: 80, height: 16 }} /></td>
                                        <td><Skeleton style={{ width: 100, height: 30 }} /></td>
                                        <td><Skeleton style={{ width: 120, height: 16 }} /></td>
                                        <td><Skeleton style={{ width: 60, height: 24 }} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : apiKeys.length === 0 ? (
                        <div className="ak-empty">
                            No API keys yet. Create one to start integrating with the TalentOrbit API.
                        </div>
                    ) : (
                        <table className="ak-table">
                            <thead>
                                <tr>
                                    <th>Key Name</th>
                                    <th>Prefix</th>
                                    <th>Scopes</th>
                                    <th>Activity (7d)</th>
                                    <th>Created / Last Used</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {apiKeys.map((key) => (
                                    <tr key={key.id} style={!key.is_active ? { opacity: 0.4 } : {}}>
                                        <td>
                                            <div className="ak-key-name">{key.name}</div>
                                        </td>
                                        <td>
                                            <span className="ak-key-prefix">{key.prefix}…</span>
                                        </td>
                                        <td>
                                            {(key.scopes || []).map((scope, i) => (
                                                <span key={i} className="ak-scope-tag">{scope}</span>
                                            ))}
                                        </td>
                                        <td>
                                            <Sparkline data={key.daily_usage || [0, 0, 0, 0, 0, 0, 0]} />
                                        </td>
                                        <td>
                                            <div className="ak-date-meta">
                                                <strong>Created:</strong> {formatDate(key.created_at)}<br />
                                                <span><strong>Last Used:</strong> {formatLastUsed(key.last_used_at)}</span>
                                            </div>
                                        </td>
                                        <td>
                                            {key.is_active && (
                                                <>
                                                    <button className="ak-rotate-btn" onClick={() => handleRotate(key.id)}>
                                                        Rotate
                                                    </button>
                                                    <button className="ak-revoke-btn" onClick={() => handleRevoke(key.id)}>
                                                        Revoke
                                                    </button>
                                                </>
                                            )}
                                            {!key.is_active && (
                                                <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', opacity: 0.6 }}>
                                                    Revoked
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}

                    {/* IP Allowlist + Scope Settings */}
                    {apiKeys.length > 0 && (
                        <div className="ak-settings-pane">
                            <div className="ak-field-group">
                                <h2 className="ak-field-label">Active Scopes Overview</h2>
                                <div className="ak-checkbox-grid">
                                    {AVAILABLE_SCOPES.map((scope) => {
                                        const used = apiKeys.some((k) => k.is_active && (k.scopes || []).includes(scope));
                                        return (
                                            <label key={scope} className="ak-checkbox-item" style={{ opacity: used ? 1 : 0.4 }}>
                                                <input type="checkbox" checked={used} readOnly />
                                                {scope}
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>
                            <div className="ak-field-group">
                                <h2 className="ak-field-label">Quick Stats</h2>
                                <div style={{ fontSize: 13, lineHeight: 2 }}>
                                    <div><strong>Total Keys:</strong> {apiKeys.length}</div>
                                    <div><strong>Active:</strong> {apiKeys.filter((k) => k.is_active).length}</div>
                                    <div><strong>Revoked:</strong> {apiKeys.filter((k) => !k.is_active).length}</div>
                                    <div><strong>Total Usage:</strong> {apiKeys.reduce((sum, k) => sum + (k.usage_count || 0), 0).toLocaleString()}</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <CreateKeyModal
                open={showCreateModal}
                onClose={() => setShowCreateModal(false)}
                onCreated={handleKeyCreated}
            />
        </DashboardLayout>
    );
};

export default APIKeysManager;
