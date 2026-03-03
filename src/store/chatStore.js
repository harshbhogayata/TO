/**
 * src/store/chatStore.js
 * Zustand store for real-time messaging via WebSocket.
 *
 * Manages:
 *  - WebSocket connection lifecycle
 *  - Thread list with unread counts
 *  - Active thread messages
 *  - Typing indicators
 *  - Read receipts
 *  - Optimistic message sending with offline queue
 *  - Message delivery acknowledgments
 *  - User presence (online/offline/last-seen)
 *  - Reconnect gap recovery (sync missed messages)
 */
import { create } from 'zustand';
import { WebSocketManager } from '../services/websocket';
import { useAuthStore } from './authStore';
import { messagingService } from '../services/api';
import api from '../services/api';

/** @type {WebSocketManager|null} */
let _chatWs = null;

/** Typing indicator debounce timers per thread */
const _typingTimers = new Map();

/** Timestamp of last received message (for reconnect sync) */
let _lastMessageTimestamp = null;

/** Offline message queue — messages sent while disconnected */
const _offlineQueue = [];

export const useChatStore = create((set, get) => ({
    // ── State ─────────────────────────────────────────────────────────────
    threads: [],
    activeThreadId: null,
    messages: [],             // Messages for the active thread
    typingUsers: {},          // { threadId: [{ userId, userName, expiresAt }] }
    isLoadingThreads: true,
    isLoadingMessages: false,
    isSending: false,
    wsConnected: false,
    totalUnread: 0,
    presence: {},             // { userId: { is_online: bool, last_seen: string|null } }
    pendingAcks: new Set(),   // Message IDs waiting for delivery ack

    // ── Thread Management ─────────────────────────────────────────────────

    /**
     * Load all threads from the REST API and start WebSocket connection.
     */
    initialize: async () => {
        set({ isLoadingThreads: true });
        try {
            const { data } = await messagingService.myThreads();
            const threads = data.results || data;
            set({ threads, isLoadingThreads: false });

            // Calculate total unread
            const totalUnread = threads.reduce((sum, t) => sum + (t.unread_count || 0), 0);
            set({ totalUnread });

            // Connect WebSocket
            get().connectWebSocket();

            // Fetch initial presence for all participants
            get()._fetchInitialPresence(threads);
        } catch {
            set({ isLoadingThreads: false });
        }
    },

    /**
     * Select a thread and load its messages.
     */
    selectThread: async (threadId) => {
        if (threadId === get().activeThreadId) return;

        set({ activeThreadId: threadId, isLoadingMessages: true, messages: [] });

        try {
            const { data } = await messagingService.getMessages(threadId);
            const messages = data.results || data;
            set({ messages, isLoadingMessages: false });

            // Track last message timestamp for reconnect sync
            if (messages.length > 0) {
                _lastMessageTimestamp = messages[messages.length - 1].sent_at;
            }

            // Update thread unread count locally
            set(state => ({
                threads: state.threads.map(t =>
                    t.id === threadId ? { ...t, unread_count: 0 } : t
                ),
                totalUnread: Math.max(0, state.totalUnread - (
                    state.threads.find(t => t.id === threadId)?.unread_count || 0
                )),
            }));

            // Send read receipt via WebSocket
            get().sendReadReceipt(threadId);
        } catch {
            set({ isLoadingMessages: false });
        }
    },

    /**
     * Send a message — optimistic update + WebSocket with offline fallback.
     */
    sendMessage: async (threadId, body) => {
        const user = useAuthStore.getState().user;
        if (!body.trim() || !user) return null;

        const trimmedBody = body.trim();

        // Try WebSocket first (lower latency)
        const wsSent = _chatWs?.send({
            type: 'chat.message',
            thread_id: threadId,
            body: trimmedBody,
        });

        if (!wsSent) {
            // Fallback to REST API
            set({ isSending: true });
            try {
                const { data } = await messagingService.sendMessage({
                    thread: threadId,
                    body: trimmedBody,
                });
                // Add to messages if this is the active thread
                if (get().activeThreadId === threadId) {
                    set(state => ({
                        messages: [...state.messages, data],
                    }));
                }
                // Update thread preview
                get()._updateThreadPreview(threadId, trimmedBody, user.full_name);
                return data;
            } catch (err) {
                throw err;
            } finally {
                set({ isSending: false });
            }
        }

        // WebSocket sent — message will arrive via broadcast
        // Stop typing indicator
        get().sendTypingStop(threadId);
        return null;
    },

    /**
     * Create a new thread and add it to the list.
     */
    createThread: async (recipientEmail, initialMessage, jobId) => {
        const { data } = await messagingService.createThread({
            recipient_email: recipientEmail,
            initial_message: initialMessage || undefined,
            job_id: jobId || undefined,
        });

        set(state => ({
            threads: [data, ...state.threads.filter(t => t.id !== data.id)],
        }));

        return data;
    },

    // ── Typing Indicators ─────────────────────────────────────────────────

    /**
     * Send a typing indicator (debounced — only sends once per 3s).
     */
    sendTypingStart: (threadId) => {
        if (_typingTimers.has(threadId)) return; // Already sent recently

        _chatWs?.send({
            type: 'chat.typing',
            thread_id: threadId,
            is_typing: true,
        });

        // Throttle: don't send again for 3 seconds
        const timer = setTimeout(() => {
            _typingTimers.delete(threadId);
        }, 3000);
        _typingTimers.set(threadId, timer);
    },

    /**
     * Send typing stopped indicator.
     */
    sendTypingStop: (threadId) => {
        if (_typingTimers.has(threadId)) {
            clearTimeout(_typingTimers.get(threadId));
            _typingTimers.delete(threadId);
        }

        _chatWs?.send({
            type: 'chat.typing',
            thread_id: threadId,
            is_typing: false,
        });
    },

    // ── Read Receipts ─────────────────────────────────────────────────────

    /**
     * Send a read receipt for all messages in a thread.
     */
    sendReadReceipt: (threadId) => {
        _chatWs?.send({
            type: 'chat.read',
            thread_id: threadId,
        });
    },

    // ── Presence ──────────────────────────────────────────────────────────

    /**
     * Get the online status of a specific user.
     * @param {number} userId
     * @returns {{ is_online: boolean, last_seen: string|null }}
     */
    getUserPresence: (userId) => {
        return get().presence[userId] || { is_online: false, last_seen: null };
    },

    // ── WebSocket ─────────────────────────────────────────────────────────

    connectWebSocket: () => {
        if (_chatWs?.isConnected) return;

        // Disconnect any existing connection
        _chatWs?.disconnect();

        _chatWs = new WebSocketManager('/ws/chat/', {
            getToken: () => useAuthStore.getState().accessToken,
            onOpen: () => {
                set({ wsConnected: true });

                // Flush offline queue
                while (_offlineQueue.length > 0) {
                    const msg = _offlineQueue.shift();
                    _chatWs?.send(msg);
                }

                // Sync missed messages if we have a last timestamp
                if (_lastMessageTimestamp && get().activeThreadId) {
                    get()._syncMissedMessages(get().activeThreadId, _lastMessageTimestamp);
                }
            },
            onClose: () => {
                set({ wsConnected: false });
            },
            onMessage: (data) => {
                get()._handleWsMessage(data);
            },
            onError: () => {
                // Handled by reconnect logic
            },
        });

        _chatWs.connect();
    },

    disconnectWebSocket: () => {
        _chatWs?.disconnect();
        _chatWs = null;
        set({ wsConnected: false });

        // Clear all typing timers
        _typingTimers.forEach(timer => clearTimeout(timer));
        _typingTimers.clear();
    },

    // ── Internal Handlers ─────────────────────────────────────────────────

    _handleWsMessage: (data) => {
        const userId = useAuthStore.getState().user?.id;

        switch (data.type) {
            case 'chat.message': {
                const msg = data.message;
                const { activeThreadId, messages } = get();

                // Track timestamp for reconnect sync
                if (msg.sent_at) {
                    _lastMessageTimestamp = msg.sent_at;
                }

                // Add message to active thread if it matches
                if (msg.thread_id === activeThreadId) {
                    // Avoid duplicates
                    const exists = messages.some(m => m.id === msg.id);
                    if (!exists) {
                        set({ messages: [...messages, msg] });
                    }

                    // Auto-send read receipt if message is from someone else
                    if (msg.sender !== userId) {
                        get().sendReadReceipt(msg.thread_id);
                    }
                }

                // Update thread preview & unread count
                get()._updateThreadPreview(
                    msg.thread_id,
                    msg.body,
                    msg.sender_name,
                    msg.sent_at,
                    msg.sender !== userId && msg.thread_id !== activeThreadId,
                );

                // Clear typing indicator for this user in this thread
                set(state => {
                    const threadTyping = (state.typingUsers[msg.thread_id] || [])
                        .filter(t => t.userId !== msg.sender);
                    return {
                        typingUsers: {
                            ...state.typingUsers,
                            [msg.thread_id]: threadTyping,
                        },
                    };
                });
                break;
            }

            case 'chat.ack': {
                // Server acknowledged message delivery
                const { message_id, thread_id, sent_at } = data;
                set(state => ({
                    pendingAcks: (() => {
                        const next = new Set(state.pendingAcks);
                        next.delete(message_id);
                        return next;
                    })(),
                }));
                break;
            }

            case 'chat.typing': {
                const { thread_id, user_id, user_name, is_typing } = data;

                set(state => {
                    const existing = state.typingUsers[thread_id] || [];

                    if (is_typing) {
                        // Add user to typing list (or update)
                        const filtered = existing.filter(t => t.userId !== user_id);
                        return {
                            typingUsers: {
                                ...state.typingUsers,
                                [thread_id]: [
                                    ...filtered,
                                    { userId: user_id, userName: user_name, expiresAt: Date.now() + 5000 },
                                ],
                            },
                        };
                    } else {
                        // Remove user from typing list
                        return {
                            typingUsers: {
                                ...state.typingUsers,
                                [thread_id]: existing.filter(t => t.userId !== user_id),
                            },
                        };
                    }
                });

                // Auto-expire typing indicator after 5s
                if (data.is_typing) {
                    setTimeout(() => {
                        set(state => ({
                            typingUsers: {
                                ...state.typingUsers,
                                [thread_id]: (state.typingUsers[thread_id] || [])
                                    .filter(t => t.expiresAt > Date.now()),
                            },
                        }));
                    }, 5000);
                }
                break;
            }

            case 'chat.read': {
                const { thread_id } = data;
                // Mark messages in active thread as read
                if (thread_id === get().activeThreadId) {
                    set(state => ({
                        messages: state.messages.map(m =>
                            m.sender === userId && !m.read
                                ? { ...m, read: true, read_at: new Date().toISOString() }
                                : m
                        ),
                    }));
                }
                break;
            }

            case 'presence': {
                const { user_id, is_online, last_seen } = data;
                set(state => ({
                    presence: {
                        ...state.presence,
                        [user_id]: { is_online, last_seen },
                    },
                }));
                break;
            }

            case 'error': {
                console.warn('Chat WS error:', data.code, data.detail);
                break;
            }
        }
    },

    /**
     * Sync messages missed during a WebSocket disconnect.
     * @param {number} threadId
     * @param {string} sinceTimestamp - ISO timestamp
     */
    _syncMissedMessages: async (threadId, sinceTimestamp) => {
        try {
            const { data } = await api.get(
                `/messages/${threadId}/sync/`,
                { params: { since: sinceTimestamp } }
            );
            const missed = data.messages || [];
            if (missed.length === 0) return;

            set(state => {
                const existingIds = new Set(state.messages.map(m => m.id));
                const newMessages = missed.filter(m => !existingIds.has(m.id));
                if (newMessages.length === 0) return state;

                const merged = [...state.messages, ...newMessages]
                    .sort((a, b) => new Date(a.sent_at) - new Date(b.sent_at));

                // Update last timestamp
                _lastMessageTimestamp = merged[merged.length - 1].sent_at;

                return { messages: merged };
            });
        } catch {
            // Non-critical — user can refresh to see missed messages
        }
    },

    /**
     * Fetch initial presence for all unique participants across threads.
     * @param {Array} threads
     */
    _fetchInitialPresence: async (threads) => {
        const userIds = new Set();
        const currentUserId = useAuthStore.getState().user?.id;
        for (const thread of threads) {
            for (const p of (thread.participants || [])) {
                if (p.id !== currentUserId) {
                    userIds.add(p.id);
                }
            }
        }

        if (userIds.size === 0) return;

        try {
            const { data } = await api.post('/push/presence/', {
                user_ids: [...userIds],
            });
            const presenceMap = {};
            for (const [uid, info] of Object.entries(data.presence || {})) {
                presenceMap[Number(uid)] = info;
            }
            set({ presence: presenceMap });
        } catch {
            // Non-critical
        }
    },

    /**
     * Update a thread's preview (last message, unread count, position).
     */
    _updateThreadPreview: (threadId, body, senderName, sentAt, incrementUnread = false) => {
        set(state => {
            const threads = state.threads.map(t => {
                if (t.id !== threadId) return t;
                return {
                    ...t,
                    last_message: {
                        body,
                        sender_name: senderName,
                        sent_at: sentAt || new Date().toISOString(),
                    },
                    updated_at: sentAt || new Date().toISOString(),
                    unread_count: incrementUnread ? (t.unread_count || 0) + 1 : t.unread_count,
                };
            });

            // Move updated thread to top
            const idx = threads.findIndex(t => t.id === threadId);
            if (idx > 0) {
                const [thread] = threads.splice(idx, 1);
                threads.unshift(thread);
            }

            const totalUnread = threads.reduce((sum, t) => sum + (t.unread_count || 0), 0);

            return { threads, totalUnread };
        });
    },

    // ── Cleanup ───────────────────────────────────────────────────────────
    reset: () => {
        _chatWs?.disconnect();
        _chatWs = null;
        _lastMessageTimestamp = null;
        _offlineQueue.length = 0;
        _typingTimers.forEach(timer => clearTimeout(timer));
        _typingTimers.clear();
        set({
            threads: [],
            activeThreadId: null,
            messages: [],
            typingUsers: {},
            isLoadingThreads: true,
            isLoadingMessages: false,
            isSending: false,
            wsConnected: false,
            totalUnread: 0,
            presence: {},
            pendingAcks: new Set(),
        });
    },
}));
