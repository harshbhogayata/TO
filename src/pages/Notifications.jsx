import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { notificationsService, getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './Notifications.css';

const CATEGORIES = ['All', 'Application', 'Message'];

const Notifications = () => {
    const { addToast } = useToast();
    usePageTitle('Notifications', 'Stay updated with application status changes, messages, and platform announcements.');
    const [notifications, setNotifications] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeFilter, setActiveFilter] = useState('All');

    useEffect(() => {
        notificationsService.myNotifications()
            .then(({ data }) => setNotifications(data.results || data))
            .catch((err) => addToast(getApiErrorMessage(err, 'Failed to load real-time alerts.'), 'error'))
            .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const markRead = async (id) => {
        try {
            await notificationsService.read(id);
            setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
        } catch (err) { addToast(getApiErrorMessage(err, 'Failed to mark notification as read.'), 'error'); }
    };

    const markAllRead = async () => {
        try {
            await notificationsService.readAll();
            setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
        } catch (err) { addToast(getApiErrorMessage(err, 'Failed to mark all as read.'), 'error'); }
    };

    const filtered = activeFilter === 'All'
        ? notifications
        : notifications.filter(n => (n.category || 'System').toLowerCase() === activeFilter.toLowerCase());

    const unread = notifications.filter(n => !n.is_read).length;

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
                status: isLoading ? "Loading..." : `${unread} Unread`,
                info: "Live Notifications"
            }}
            pageTitleLine1="Alert"
            pageTitleLine2="Center"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Unread</h3><p>{unread}</p></div>
                    <div className="stat-block"><h3>Total</h3><p>{notifications.length}</p></div>
                    {unread > 0 && (
                        <button className="btn-outline" style={{ padding: '6px 12px', fontSize: '10px' }} onClick={markAllRead}>
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
                            onClick={() => markRead(n.id)}
                        >
                            {!n.is_read && <div className="notif-unread-indicator" />}
                            <div style={{ display: 'flex', flex: 1, gap: '16px', padding: '20px 32px', alignItems: 'flex-start' }}>
                                <div className="notif-category-tag">{n.category || 'System'}</div>
                                <div className="notif-item-content" style={{ flex: 1 }}>
                                    <span className="notif-item-title">{n.title}</span>
                                    <p className="notif-item-desc">{n.description || n.message || ''}</p>
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
