import { useState, useEffect, useCallback } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { getApiErrorMessage } from '../services/api';
import { useNotificationStore } from '../store/notificationStore';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './Notifications.css';

const CATEGORIES = ['All', 'Application', 'Message'];

const Notifications = () => {
    const { addToast } = useToast();
    usePageTitle('Notifications', 'Stay updated with application status changes, messages, and platform announcements.');
    const [activeFilter, setActiveFilter] = useState('All');

    const {
        notifications, unreadCount, isLoading, wsConnected, pushPermission, pushSupported,
        initialize, markRead, markAllRead, requestPushPermission, disconnectWebSocket,
    } = useNotificationStore();

    useEffect(() => {
        initialize().catch((err) =>
            addToast(getApiErrorMessage(err, 'Failed to load real-time alerts.'), 'error')
        );
        return () => disconnectWebSocket();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleMarkRead = useCallback(async (id) => {
        try {
            await markRead(id);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to mark notification as read.'), 'error');
        }
    }, [markRead, addToast]);

    const handleMarkAllRead = useCallback(async () => {
        try {
            await markAllRead();
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to mark all as read.'), 'error');
        }
    }, [markAllRead, addToast]);

    const handleEnablePush = useCallback(async () => {
        const result = await requestPushPermission();
        if (result === 'denied') {
            addToast('Push notifications were blocked. Enable them in browser settings.', 'warning');
        } else if (result === 'granted') {
            addToast('Push notifications enabled!', 'success');
        }
    }, [requestPushPermission, addToast]);

    const filtered = activeFilter === 'All'
        ? notifications
        : notifications.filter(n => (n.category || 'System').toLowerCase() === activeFilter.toLowerCase());

    const formatTime = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        const now = new Date();
        const diff = now - d;
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Alert Center",
                status: wsConnected ? `● Live — ${unreadCount} Unread` : `○ Connecting… — ${unreadCount} Unread`,
                info: "Real-Time Notifications"
            }}
            pageTitleLine1="Alert"
            pageTitleLine2="Center"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Unread</h3><p>{unreadCount}</p></div>
                    <div className="stat-block"><h3>Total</h3><p>{notifications.length}</p></div>
                    {pushSupported && pushPermission !== 'granted' && (
                        <button className="btn-outline" style={{ padding: '6px 12px', fontSize: '10px' }} onClick={handleEnablePush}>
                            Enable Push
                        </button>
                    )}
                    {unreadCount > 0 && (
                        <button className="btn-outline" style={{ padding: '6px 12px', fontSize: '10px' }} onClick={handleMarkAllRead}>
                            Mark All Read
                        </button>
                    )}
                </div>
            }
        >
            <div style={{ display: 'flex', flex: 1, minHeight: 0, flexDirection: 'column', overflow: 'hidden' }}>
                {/* Filter tabs */}
                <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', padding: '0 32px', gap: '4px', flexShrink: 0 }}>
                    {CATEGORIES.map(cat => (
                        <button
                            key={cat}
                            onClick={() => setActiveFilter(cat)}
                            style={{
                                padding: '14px 16px',
                                border: 'none',
                                background: 'transparent',
                                fontFamily: 'var(--font-sans)',
                                fontSize: '11px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                cursor: 'pointer',
                                borderBottom: activeFilter === cat ? '2px solid #000' : '2px solid transparent',
                                marginBottom: '-1px',
                                opacity: activeFilter === cat ? 1 : 0.4,
                            }}
                        >
                            {cat}
                        </button>
                    ))}
                </div>

                {/* List */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '0' }}>
                    {isLoading && <Skeleton.List count={6} />}

                    {!isLoading && filtered.length === 0 && (
                        <div style={{ padding: '60px 32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            No {activeFilter.toLowerCase()} notifications.
                        </div>
                    )}

                    {filtered.map(n => (
                        <div
                            key={n.id}
                            className={`notif-row ${!n.is_read ? 'unread' : ''}`}
                            style={{ cursor: 'pointer', display: 'flex', gap: '0', padding: 0 }}
                            onClick={() => handleMarkRead(n.id)}
                        >
                            {!n.is_read && <div className="notif-unread-indicator" />}
                            <div style={{ display: 'flex', flex: 1, gap: '16px', padding: '20px 32px', alignItems: 'flex-start' }}>
                                <div className="notif-category-tag">{n.category || 'System'}</div>
                                <div className="notif-item-content" style={{ flex: 1 }}>
                                    <span className="notif-item-title">{n.title}</span>
                                    <p className="notif-item-desc">{n.description || ''}</p>
                                    <span className="notif-time">{formatTime(n.created_at)}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default Notifications;
