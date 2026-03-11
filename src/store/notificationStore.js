/**
 * src/store/notificationStore.js
 * Zustand store for real-time notifications via WebSocket.
 *
 * Manages:
 *  - WebSocket connection for live notification push
 *  - Notification list with optimistic read marking
 *  - Unread count (synced with WebSocket)
 *  - Push notification permission & token registration
 *  - Reconnect-aware unread refresh
 */
import { create } from 'zustand';
import { WebSocketManager } from '../services/websocket';
import { useAuthStore } from './authStore';
import { notificationsService } from '../services/api';
import api from '../services/api';

/** @type {WebSocketManager|null} */
let _notifWs = null;

/** Invalidate stale async initialization after unmount/navigation */
let _notificationInitVersion = 0;

/** Track whether this is a reconnect (not the first connect) */
let _hasConnectedOnce = false;

export const useNotificationStore = create((set, get) => ({
    // ── State ─────────────────────────────────────────────────────────────
    notifications: [],
    unreadCount: 0,
    isLoading: true,
    wsConnected: false,
    pushPermission: 'default',   // 'default' | 'granted' | 'denied'
    pushSupported: typeof window !== 'undefined' && 'Notification' in window && 'serviceWorker' in navigator,

    // ── Initialization ────────────────────────────────────────────────────

    /**
     * Load notifications from REST API and start WebSocket connection.
     */
    initialize: async () => {
        const initVersion = ++_notificationInitVersion;
        set({ isLoading: true });
        try {
            const { data } = await notificationsService.myNotifications();
            const notifications = data.results || data;
            const unreadCount = notifications.filter(n => !n.is_read).length;
            if (initVersion !== _notificationInitVersion) return;
            set({ notifications, unreadCount, isLoading: false });
        } catch {
            if (initVersion === _notificationInitVersion) {
                set({ isLoading: false });
            }
        }

        if (initVersion !== _notificationInitVersion) return;

        // Connect WebSocket
        get().connectWebSocket();

        // Check push permission status
        if (get().pushSupported) {
            set({ pushPermission: Notification.permission });
        }
    },

    // ── Notification Actions ──────────────────────────────────────────────

    /**
     * Mark a single notification as read (optimistic update + WS).
     */
    markRead: async (notificationId) => {
        // Optimistic update
        set(state => ({
            notifications: state.notifications.map(n =>
                n.id === notificationId ? { ...n, is_read: true } : n
            ),
            unreadCount: Math.max(0, state.unreadCount - 1),
        }));

        // Send via WebSocket if connected, otherwise REST
        const wsSent = _notifWs?.send({
            type: 'mark_read',
            notification_id: notificationId,
        });

        if (!wsSent) {
            try {
                await notificationsService.read(notificationId);
            } catch {
                // Revert optimistic update
                set(state => ({
                    notifications: state.notifications.map(n =>
                        n.id === notificationId ? { ...n, is_read: false } : n
                    ),
                    unreadCount: state.unreadCount + 1,
                }));
            }
        }
    },

    /**
     * Mark all notifications as read.
     */
    markAllRead: async () => {
        const previousNotifs = get().notifications;
        const previousCount = get().unreadCount;

        // Optimistic update
        set(state => ({
            notifications: state.notifications.map(n => ({ ...n, is_read: true })),
            unreadCount: 0,
        }));

        const wsSent = _notifWs?.send({ type: 'mark_all_read' });

        if (!wsSent) {
            try {
                await notificationsService.readAll();
            } catch {
                // Revert
                set({ notifications: previousNotifs, unreadCount: previousCount });
            }
        }
    },

    // ── Push Notifications ────────────────────────────────────────────────

    /**
     * Request push notification permission and register the FCM token.
     */
    requestPushPermission: async () => {
        if (!get().pushSupported) return 'unsupported';

        try {
            const permission = await Notification.requestPermission();
            set({ pushPermission: permission });

            if (permission === 'granted') {
                await get()._registerPushToken();
            }

            return permission;
        } catch {
            return 'denied';
        }
    },

    /**
     * Register the FCM token with the backend.
     * @internal
     */
    _registerPushToken: async () => {
        try {
            const reg = await navigator.serviceWorker.ready;

            // Get the Firebase messaging token via the service worker
            // The SW handles the Firebase SDK initialization
            const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;
            if (!vapidKey) return;

            // Use the PushManager API directly since we're not loading Firebase on the main thread
            const subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: vapidKey,
            });

            // Send to backend
            const token = JSON.stringify(subscription);
            await api.post('/push/subscribe/', {
                token,
                platform: 'web',
            });
        } catch {
            // Push registration failed — non-critical
        }
    },

    // ── WebSocket ─────────────────────────────────────────────────────────

    connectWebSocket: () => {
        if (_notifWs?.isConnected) return;

        _notifWs?.disconnect();

        _notifWs = new WebSocketManager('/ws/notifications/', {
            getToken: () => useAuthStore.getState().accessToken,
            onOpen: () => {
                set({ wsConnected: true });

                // On reconnect, refresh unread count from server to catch
                // anything missed during the disconnect window.
                if (_hasConnectedOnce) {
                    get()._refreshFromServer();
                }
                _hasConnectedOnce = true;
            },
            onClose: () => {
                set({ wsConnected: false });
            },
            onMessage: (data) => {
                get()._handleWsMessage(data);
            },
        });

        _notifWs.connect();
    },

    disconnectWebSocket: () => {
        _notificationInitVersion++;
        _notifWs?.disconnect();
        _notifWs = null;
        set({ wsConnected: false });
    },

    // ── Internal Handlers ─────────────────────────────────────────────────

    _handleWsMessage: (data) => {
        switch (data.type) {
            case 'notification': {
                const notif = data.notification;

                // Avoid duplicates (e.g. after reconnect sync)
                const exists = get().notifications.some(n => n.id === notif.id);
                if (exists) break;

                // Prepend new notification
                set(state => ({
                    notifications: [notif, ...state.notifications],
                    unreadCount: state.unreadCount + 1,
                }));

                // Show browser notification if permitted and tab is hidden
                if (Notification.permission === 'granted' && document.hidden) {
                    try {
                        new Notification(notif.title, {
                            body: notif.description || '',
                            icon: '/icon-192.svg',
                            badge: '/icon-192.svg',
                            tag: `notif-${notif.id}`,
                        });
                    } catch {
                        // Notification API may fail in some contexts
                    }
                }
                break;
            }

            case 'unread_count': {
                set({ unreadCount: data.count });
                break;
            }

            case 'presence': {
                // Forward presence events to the chat store for centralized
                // presence state.  We import lazily to avoid circular deps.
                import('./chatStore').then(({ useChatStore }) => {
                    const { user_id, is_online, last_seen } = data;
                    useChatStore.setState(state => ({
                        presence: {
                            ...state.presence,
                            [user_id]: { is_online, last_seen },
                        },
                    }));
                });
                break;
            }
        }
    },

    /**
     * Re-fetch the notification list from the server. Used after WebSocket
     * reconnect to ensure nothing was missed.
     * @internal
     */
    _refreshFromServer: async () => {
        try {
            const { data } = await notificationsService.myNotifications();
            const notifications = data.results || data;
            const unreadCount = notifications.filter(n => !n.is_read).length;
            set({ notifications, unreadCount });
        } catch {
            // Best-effort — existing state is still usable
        }
    },

    // ── Cleanup ───────────────────────────────────────────────────────────
    reset: () => {
        _notificationInitVersion++;
        _notifWs?.disconnect();
        _notifWs = null;
        _hasConnectedOnce = false;
        set({
            notifications: [],
            unreadCount: 0,
            isLoading: true,
            wsConnected: false,
        });
    },
}));
