import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import developerService from '../services/developerService';
import { useDeveloperStore } from '../store/developerStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './WebhookManager.css';

/* ── Available webhook events (mirrors backend AVAILABLE_EVENTS) ── */
const WEBHOOK_EVENTS = [
    'job.created', 'job.updated', 'job.closed',
    'application.received', 'application.status_changed',
    'assessment.completed', 'assessment.graded',
    'user.deactivated', 'invoice.paid', 'team.member_added',
];

/* ── Create / Edit Endpoint Modal ─────────────────────────────── */
const EndpointModal = ({ open, onClose, onSaved, editEndpoint }) => {
    const [form, setForm] = useState({ url: '', events: [], description: '' });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (editEndpoint) {
            setForm({
                url: editEndpoint.url || '',
                events: editEndpoint.events || [],
                description: editEndpoint.description || '',
            });
        } else {
            setForm({ url: '', events: [], description: '' });
        }
    }, [editEndpoint, open]);

    if (!open) return null;

    const toggleEvent = (evt) => {
        setForm((prev) => ({
            ...prev,
            events: prev.events.includes(evt)
                ? prev.events.filter((e) => e !== evt)
                : [...prev.events, evt],
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            if (editEndpoint) {
                await developerService.updateWebhook(editEndpoint.id, {
                    url: form.url,
                    events: form.events,
                    description: form.description,
                });
            } else {
                const { data } = await developerService.createWebhook({
                    url: form.url,
                    events: form.events,
                    description: form.description,
                });
                onSaved(data);
                onClose();
                return;
            }
            onSaved(null);
            onClose();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to save webhook.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="wm-modal-backdrop" onClick={onClose}>
            <form className="wm-modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
                <h2>{editEndpoint ? 'Edit Endpoint' : 'Add Endpoint'}</h2>
                <div className="wm-modal-field">
                    <label>Endpoint URL</label>
                    <input
                        type="url"
                        className="wm-input"
                        value={form.url}
                        onChange={(e) => setForm({ ...form, url: e.target.value })}
                        placeholder="https://your-domain.com/webhooks"
                        required
                        disabled={!!editEndpoint}
                    />
                </div>
                <div className="wm-modal-field">
                    <label>Description</label>
                    <input
                        type="text"
                        className="wm-input"
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                        placeholder="Production webhook handler"
                    />
                </div>
                <div className="wm-modal-field">
                    <label>Subscribe to Events</label>
                    <div className="wm-event-checkbox-grid">
                        {WEBHOOK_EVENTS.map((evt) => (
                            <label key={evt} className="wm-event-checkbox-item">
                                <input
                                    type="checkbox"
                                    checked={form.events.includes(evt)}
                                    onChange={() => toggleEvent(evt)}
                                />
                                {evt}
                            </label>
                        ))}
                    </div>
                </div>
                <div className="wm-modal-actions">
                    <button type="button" className="wm-modal-cancel" onClick={onClose}>Cancel</button>
                    <button
                        type="submit"
                        className="wm-modal-submit"
                        disabled={saving || !form.url.trim() || form.events.length === 0}
                    >
                        {saving ? 'Saving...' : editEndpoint ? 'Update' : 'Create Endpoint'}
                    </button>
                </div>
            </form>
        </div>
    );
};

/* ── Delivery Log Panel ───────────────────────────────────────── */
const DeliveryLogPanel = ({ endpoint, deliveries, loading, onTestPing }) => {
    const [pinging, setPinging] = useState(false);
    const [pingResult, setPingResult] = useState(null);

    if (!endpoint) {
        return (
            <div className="wm-panel">
                <div className="wm-panel__title">Delivery Log</div>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', padding: '20px 0' }}>
                    Select an endpoint to view its delivery log.
                </div>
            </div>
        );
    }

    const handlePing = async () => {
        setPinging(true);
        setPingResult(null);
        try {
            const { data } = await developerService.testWebhookPing(endpoint.id);
            setPingResult({
                success: data.is_success ?? data.status_code < 400,
                statusCode: data.status_code,
                responseTime: data.response_time_ms,
            });
            if (onTestPing) onTestPing();
        } catch (err) {
            setPingResult({ success: false, statusCode: 0, error: getApiErrorMessage(err) });
        } finally {
            setPinging(false);
        }
    };

    const formatTimestamp = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleString('en-US', {
            month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
    };

    return (
        <div className="wm-panel">
            <div className="wm-panel__title">
                Delivery Log — {endpoint.url?.replace(/https?:\/\//, '').substring(0, 35)}…
            </div>

            {/* Test Ping */}
            <button
                className="wm-test-btn"
                style={{ marginBottom: 14, width: '100%' }}
                onClick={handlePing}
                disabled={pinging}
            >
                {pinging ? 'Sending...' : '⚡ Send Test Ping'}
            </button>
            {pingResult && (
                <div className={`wm-ping-result wm-ping-result--${pingResult.success ? 'success' : 'fail'}`}>
                    {pingResult.success
                        ? `✓ ${pingResult.statusCode} — ${pingResult.responseTime}ms`
                        : `✗ ${pingResult.statusCode || 'Timeout'} — ${pingResult.error || 'Delivery failed'}`
                    }
                </div>
            )}

            {/* Signing Secret */}
            <SigningSecretBlock prefix={endpoint.signing_secret_prefix} />

            {/* Deliveries */}
            {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} style={{ padding: '10px 0' }}>
                        <Skeleton style={{ width: '70%', height: 14, marginBottom: 6 }} />
                        <Skeleton style={{ width: '40%', height: 12 }} />
                    </div>
                ))
            ) : deliveries.length === 0 ? (
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', padding: '20px 0' }}>
                    No deliveries yet.
                </div>
            ) : (
                deliveries.map((del) => (
                    <div key={del.id} className="wm-delivery-item">
                        <div>
                            <div className="wm-delivery__event">{del.event_type}</div>
                            <div className="wm-delivery__timestamp">{formatTimestamp(del.delivered_at)}</div>
                            <div className="wm-delivery__meta">
                                {del.response_time_ms != null && `${del.response_time_ms}ms`}
                                {del.attempt_number > 1 && ` · retry #${del.attempt_number}`}
                            </div>
                        </div>
                        <span className={`wm-delivery__status wm-delivery__status--${del.is_success ? 'success' : 'fail'}`}>
                            {del.status_code || 'ERR'}
                        </span>
                    </div>
                ))
            )}
        </div>
    );
};

/* ── Signing Secret Block ─────────────────────────────────────── */
const SigningSecretBlock = ({ prefix }) => {
    const [copied, setCopied] = useState(false);
    const masked = prefix ? `${prefix}${'•'.repeat(24)}` : '••••••••••••••••';

    const handleCopy = () => {
        navigator.clipboard.writeText(masked).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="wm-secret-block">
            <div className="wm-secret-block__label">Signing Secret</div>
            <div className="wm-secret-block__value">{masked}</div>
            <button className="wm-secret-block__copy" onClick={handleCopy}>
                {copied ? 'Copied!' : 'Copy Prefix'}
            </button>
        </div>
    );
};

/* ── Main Component ───────────────────────────────────────────── */
const WebhookManager = () => {
    const {
        webhooks, webhooksLoading, webhooksError,
        setWebhooks, setWebhooksLoading, setWebhooksError,
        activeWebhook, setActiveWebhook,
        deliveryLog, deliveryLogLoading,
        setDeliveryLog, setDeliveryLogLoading,
    } = useDeveloperStore();

    const [showModal, setShowModal] = useState(false);
    const [editTarget, setEditTarget] = useState(null);
    const [newRawSecret, setNewRawSecret] = useState(null);

    usePageTitle('Webhooks', 'Manage webhook endpoints and delivery logs.');

    const fetchWebhooks = useCallback(async () => {
        setWebhooksLoading(true);
        setWebhooksError(null);
        try {
            const { data } = await developerService.listWebhooks();
            setWebhooks(data.results || data);
        } catch (err) {
            setWebhooksError(getApiErrorMessage(err, 'Failed to load webhooks.'));
        } finally {
            setWebhooksLoading(false);
        }
    }, [setWebhooks, setWebhooksLoading, setWebhooksError]);

    const fetchDeliveries = useCallback(async (webhookId) => {
        setDeliveryLogLoading(true);
        try {
            const { data } = await developerService.getDeliveryLog(webhookId);
            setDeliveryLog(data.results || data);
        } catch {
            setDeliveryLog([]);
        } finally {
            setDeliveryLogLoading(false);
        }
    }, [setDeliveryLog, setDeliveryLogLoading]);

    useEffect(() => { fetchWebhooks(); }, [fetchWebhooks]);

    useEffect(() => {
        if (activeWebhook) {
            fetchDeliveries(activeWebhook.id);
        }
    }, [activeWebhook, fetchDeliveries]);

    const handleRowClick = (endpoint) => {
        setActiveWebhook(endpoint);
    };

    const handleDelete = async (e, id) => {
        e.stopPropagation();
        if (!window.confirm('Delete this webhook endpoint? All delivery logs will also be removed.')) return;
        try {
            await developerService.deleteWebhook(id);
            if (activeWebhook?.id === id) {
                setActiveWebhook(null);
                setDeliveryLog([]);
            }
            fetchWebhooks();
        } catch (err) {
            alert(getApiErrorMessage(err, 'Failed to delete webhook.'));
        }
    };

    const handleEdit = (e, endpoint) => {
        e.stopPropagation();
        setEditTarget(endpoint);
        setShowModal(true);
    };

    const handleTestPing = (e, endpoint) => {
        e.stopPropagation();
        setActiveWebhook(endpoint);
    };

    const handleSaved = (data) => {
        if (data?.signing_secret) {
            setNewRawSecret(data.signing_secret);
        }
        fetchWebhooks();
        if (activeWebhook) {
            fetchDeliveries(activeWebhook.id);
        }
    };

    const openCreateModal = () => {
        setEditTarget(null);
        setShowModal(true);
    };

    const getStatusClass = (endpoint) => {
        if (!endpoint.is_active) return 'disabled';
        if (endpoint.failure_count >= 5) return 'failing';
        return 'active';
    };

    const formatDate = (iso) => {
        if (!iso) return 'Never';
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Admin Console',
                status: 'System Status: Operational',
                info: 'Settings > Webhooks',
            }}
            pageTitleLine1="Webhook"
            pageTitleLine2="Manager"
            headerRightContent={
                <div className="wm-header-actions">
                    <button className="wm-create-btn" onClick={openCreateModal}>
                        + Add Endpoint
                    </button>
                </div>
            }
        >
            <div className="wm-layout">
                {/* Left: Endpoints Table */}
                <div className="wm-content">
                    {webhooksError && <div className="wm-error-banner">{webhooksError}</div>}

                    {/* New signing secret banner */}
                    {newRawSecret && (
                        <div className="wm-secret-block" style={{ marginBottom: 18 }}>
                            <div className="wm-secret-block__label">⚠ New Signing Secret — Copy now, it won't be shown again</div>
                            <div className="wm-secret-block__value">{newRawSecret}</div>
                            <button
                                className="wm-secret-block__copy"
                                onClick={() => {
                                    navigator.clipboard.writeText(newRawSecret).catch(() => {});
                                    setNewRawSecret(null);
                                }}
                            >
                                Copy & Dismiss
                            </button>
                        </div>
                    )}

                    {webhooksLoading ? (
                        <table className="wm-table">
                            <thead>
                                <tr>
                                    <th>URL</th><th>Events</th><th>Status</th>
                                    <th>Last Delivery</th><th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Array.from({ length: 3 }).map((_, i) => (
                                    <tr key={i}>
                                        <td><Skeleton style={{ width: 200, height: 14 }} /></td>
                                        <td><Skeleton style={{ width: 100, height: 14 }} /></td>
                                        <td><Skeleton style={{ width: 60, height: 20 }} /></td>
                                        <td><Skeleton style={{ width: 80, height: 14 }} /></td>
                                        <td><Skeleton style={{ width: 100, height: 24 }} /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : webhooks.length === 0 ? (
                        <div className="wm-empty">
                            No webhook endpoints registered. Add one to start receiving real-time event notifications.
                        </div>
                    ) : (
                        <table className="wm-table">
                            <thead>
                                <tr>
                                    <th>Endpoint URL</th>
                                    <th>Events</th>
                                    <th>Status</th>
                                    <th>Last Delivery</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {webhooks.map((ep) => {
                                    const status = getStatusClass(ep);
                                    const selected = activeWebhook?.id === ep.id;
                                    return (
                                        <tr
                                            key={ep.id}
                                            className={selected ? 'wm-row--selected' : ''}
                                            onClick={() => handleRowClick(ep)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <td>
                                                <div className="wm-endpoint-url">{ep.url}</div>
                                                {ep.description && (
                                                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginTop: 3 }}>
                                                        {ep.description}
                                                    </div>
                                                )}
                                            </td>
                                            <td>
                                                {(ep.events || []).slice(0, 3).map((evt, i) => (
                                                    <span key={i} className="wm-event-tag">{evt}</span>
                                                ))}
                                                {(ep.events || []).length > 3 && (
                                                    <span className="wm-event-tag">+{ep.events.length - 3}</span>
                                                )}
                                            </td>
                                            <td>
                                                <span className={`wm-status-badge wm-status-badge--${status}`}>
                                                    {status === 'active' ? '● Active' :
                                                     status === 'failing' ? '▲ Failing' : '○ Disabled'}
                                                </span>
                                            </td>
                                            <td style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>
                                                {formatDate(ep.last_delivery_at)}
                                                {ep.last_status_code && (
                                                    <div style={{ fontSize: 10, marginTop: 2 }}>HTTP {ep.last_status_code}</div>
                                                )}
                                            </td>
                                            <td>
                                                <div className="wm-btn-row">
                                                    <button className="wm-test-btn" onClick={(e) => handleTestPing(e, ep)}>
                                                        Ping
                                                    </button>
                                                    <button className="wm-edit-btn" onClick={(e) => handleEdit(e, ep)}>
                                                        Edit
                                                    </button>
                                                    <button className="wm-delete-btn" onClick={(e) => handleDelete(e, ep.id)}>
                                                        Delete
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Right: Delivery Log Panel */}
                <DeliveryLogPanel
                    endpoint={activeWebhook}
                    deliveries={deliveryLog}
                    loading={deliveryLogLoading}
                    onTestPing={() => {
                        if (activeWebhook) fetchDeliveries(activeWebhook.id);
                        fetchWebhooks();
                    }}
                />
            </div>

            <EndpointModal
                open={showModal}
                onClose={() => { setShowModal(false); setEditTarget(null); }}
                onSaved={handleSaved}
                editEndpoint={editTarget}
            />
        </DashboardLayout>
    );
};

export default WebhookManager;
