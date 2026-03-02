import { useState, useEffect, useRef, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import { getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useChatStore } from '../store/chatStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './Inbox.css';

const Inbox = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('Inbox', 'Messages between you and recruiters. Stay connected throughout the hiring process.');

    const {
        threads, messages, activeThreadId, typingUsers,
        isLoadingThreads, isLoadingMessages, wsConnected, totalUnread,
        initialize, selectThread, sendMessage,
        sendTypingStart, sendTypingStop, disconnectWebSocket,
    } = useChatStore();

    const [draft, setDraft] = useState('');
    const [sending, setSending] = useState(false);
    const [showNewThread, setShowNewThread] = useState(false);
    const [newRecipientEmail, setNewRecipientEmail] = useState('');
    const [newInitialMsg, setNewInitialMsg] = useState('');
    const [newThreadError, setNewThreadError] = useState('');
    const [creatingThread, setCreatingThread] = useState(false);
    const [threadSearch, setThreadSearch] = useState('');
    const bottomRef = useRef(null);

    // ── Initialize on mount ───────────────────────────────────────────────
    useEffect(() => {
        initialize().catch((err) =>
            addToast(getApiErrorMessage(err, 'Failed to load conversations.'), 'error')
        );
        return () => disconnectWebSocket();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── Auto-scroll to bottom when new messages arrive ────────────────────
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // ── Select first thread on initial load ───────────────────────────────
    useEffect(() => {
        if (!isLoadingThreads && threads.length > 0 && !activeThreadId) {
            selectThread(threads[0].id);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isLoadingThreads]);

    const activeThread = threads.find(t => t.id === activeThreadId);

    const handleSend = useCallback(async () => {
        if (!draft.trim() || !activeThreadId || sending) return;
        setSending(true);
        try {
            await sendMessage(activeThreadId, draft.trim());
            setDraft('');
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to send message.'), 'error');
        } finally {
            setSending(false);
        }
    }, [draft, activeThreadId, sending, sendMessage, addToast]);

    const handleDraftChange = useCallback((e) => {
        const value = e.target.value;
        setDraft(value);
        if (value.trim() && activeThreadId) {
            sendTypingStart(activeThreadId);
        }
    }, [activeThreadId, sendTypingStart]);

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }, [handleSend]);

    const handleCreateThread = async (e) => {
        e.preventDefault();
        if (!newRecipientEmail.trim()) return;
        setCreatingThread(true);
        setNewThreadError('');
        try {
            const { createThread } = useChatStore.getState();
            const data = await createThread(newRecipientEmail.trim(), newInitialMsg.trim());
            setShowNewThread(false);
            setNewRecipientEmail('');
            setNewInitialMsg('');
            selectThread(data.id);
        } catch (err) {
            setNewThreadError(getApiErrorMessage(err, 'Failed to create thread. Check the email matches a valid user.'));
        } finally {
            setCreatingThread(false);
        }
    };

    const getOtherParticipant = (thread) =>
        thread?.participants?.find(p => p.id !== user?.id) || thread?.participants?.[0];

    const formatTime = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        const now = new Date();
        if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    };

    // ── Typing indicator text for active thread ───────────────────────────
    const activeTyping = typingUsers[activeThreadId] || [];
    const typingText = activeTyping.length > 0
        ? activeTyping.length === 1
            ? `${activeTyping[0].userName} is typing…`
            : `${activeTyping.map(t => t.userName).join(', ')} are typing…`
        : '';

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Inbox",
                status: wsConnected ? "● Live" : "○ Connecting…",
                info: `Active Threads: ${threads.length}`
            }}
            pageTitleLine1="In"
            pageTitleLine2="Box"
            headerRightContent={null}
        >
            <div className="messaging-grid">
                {/* Thread List */}
                <div className="threads-panel">
                    <div className="threads-header">
                        <h2>Active Comms</h2>
                        <button
                            style={{ background: '#000', color: '#fff', border: 'none', padding: '6px 12px', fontSize: '10px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', cursor: 'pointer' }}
                            onClick={() => setShowNewThread(v => !v)}
                        >
                            {showNewThread ? '✕' : '+ New'}
                        </button>
                    </div>

                    {/* New Thread Form */}
                    {showNewThread && (
                        <form onSubmit={handleCreateThread} style={{ padding: '16px', borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <input
                                type="email"
                                placeholder="Recipient email..."
                                value={newRecipientEmail}
                                onChange={e => setNewRecipientEmail(e.target.value)}
                                required
                                style={{ padding: '8px', border: '1px solid var(--border-color)', background: 'transparent', fontFamily: 'var(--font-sans)', fontSize: '11px' }}
                            />
                            <input
                                type="text"
                                placeholder="Opening message (optional)"
                                value={newInitialMsg}
                                onChange={e => setNewInitialMsg(e.target.value)}
                                style={{ padding: '8px', border: '1px solid var(--border-color)', background: 'transparent', fontFamily: 'var(--font-sans)', fontSize: '11px' }}
                            />
                            {newThreadError && <p style={{ color: '#b00', fontSize: '10px', textTransform: 'uppercase' }}>{newThreadError}</p>}
                            <button type="submit" disabled={creatingThread} style={{ padding: '8px', background: '#000', color: '#fff', border: 'none', fontFamily: 'var(--font-sans)', fontSize: '10px', textTransform: 'uppercase', cursor: 'pointer' }}>
                                {creatingThread ? 'Creating...' : 'Start Thread'}
                            </button>
                        </form>
                    )}
                    <div className="search-bar">
                        <input
                            type="text"
                            placeholder="Search Threads..."
                            value={threadSearch}
                            onChange={e => setThreadSearch(e.target.value)}
                        />
                    </div>

                    <div className="thread-list">
                        {isLoadingThreads && <Skeleton.Threads count={5} />}
                        {!isLoadingThreads && threads.length === 0 && (
                            <div style={{ padding: '24px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                                No messages yet.
                            </div>
                        )}
                        {(threadSearch
                            ? threads.filter(t => {
                                const other = getOtherParticipant(t);
                                const q = threadSearch.toLowerCase();
                                return (
                                    other?.full_name?.toLowerCase().includes(q) ||
                                    other?.email?.toLowerCase().includes(q) ||
                                    t.last_message?.body?.toLowerCase().includes(q)
                                );
                            })
                            : threads
                        ).map(thread => {
                            const other = getOtherParticipant(thread);
                            const isActive = activeThreadId === thread.id;
                            const threadTyping = typingUsers[thread.id] || [];
                            return (
                                <div
                                    key={thread.id}
                                    className={`thread-item ${isActive ? 'active' : ''}`}
                                    onClick={() => selectThread(thread.id)}
                                    style={{ cursor: 'pointer' }}
                                >
                                    <div className="thread-avatar">
                                        {(other?.full_name || 'U').charAt(0).toUpperCase()}
                                    </div>
                                    <div className="thread-info">
                                        <div className="thread-top">
                                            <h4>{other?.full_name || other?.email || 'Unknown'}</h4>
                                            <span>{formatTime(thread.last_message?.sent_at || thread.updated_at)}</span>
                                        </div>
                                        <div className="thread-preview">
                                            {thread.unread_count > 0 && <span className="unread-dot"></span>}
                                            <p>
                                                {threadTyping.length > 0
                                                    ? <em style={{ opacity: 0.7 }}>typing…</em>
                                                    : <>
                                                        {thread.job_title ? `[${thread.job_title}] ` : ''}
                                                        {thread.last_message?.body || 'No messages yet.'}
                                                    </>
                                                }
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Chat Area */}
                <div className="chat-area">
                    {activeThread ? (
                        <>
                            <div className="chat-header">
                                <div className="chat-user-info">
                                    <div style={{ width: '40px', height: '40px', background: 'var(--text-black)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                                        {(getOtherParticipant(activeThread)?.full_name || 'U').charAt(0).toUpperCase()}
                                    </div>
                                    <div>
                                        <h3>{getOtherParticipant(activeThread)?.full_name || 'Unknown'}</h3>
                                        <span className="user-status">
                                            {getOtherParticipant(activeThread)?.role || ''}
                                            {wsConnected && <span style={{ marginLeft: '8px', color: '#2d8a4e', fontSize: '9px' }}>● LIVE</span>}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="message-history">
                                {isLoadingMessages && <Skeleton.List count={4} />}
                                {!isLoadingMessages && messages.length === 0 && (
                                    <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase', textAlign: 'center' }}>
                                        No messages in this thread yet. Send the first one.
                                    </div>
                                )}
                                {messages.map(msg => {
                                    const isMine = msg.sender === user?.id;
                                    return (
                                        <div key={msg.id} className={`message ${isMine ? 'sent' : 'received'}`}>
                                            <div className="message-content">{msg.body}</div>
                                            <div className="message-time">
                                                {formatTime(msg.sent_at)}
                                                {isMine && msg.read && (
                                                    <span style={{ marginLeft: '6px', fontSize: '9px', opacity: 0.6 }} title={msg.read_at ? `Read at ${new Date(msg.read_at).toLocaleString()}` : 'Read'}>
                                                        ✓✓
                                                    </span>
                                                )}
                                                {isMine && !msg.read && (
                                                    <span style={{ marginLeft: '6px', fontSize: '9px', opacity: 0.3 }} title="Delivered">
                                                        ✓
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}

                                {/* Typing indicator */}
                                {typingText && (
                                    <div className="message received" style={{ opacity: 0.6 }}>
                                        <div className="message-content" style={{ fontStyle: 'italic', padding: '10px 16px', fontSize: '12px' }}>
                                            {typingText}
                                        </div>
                                    </div>
                                )}

                                <div ref={bottomRef} />
                            </div>

                            <div className="composer">
                                <input
                                    type="text"
                                    className="composer-input"
                                    placeholder="Type your transmission..."
                                    value={draft}
                                    onChange={handleDraftChange}
                                    onKeyDown={handleKeyDown}
                                    onBlur={() => activeThreadId && sendTypingStop(activeThreadId)}
                                />
                                <button className="btn-send" onClick={handleSend} disabled={sending}>
                                    {sending ? '...' : 'SEND'}
                                </button>
                            </div>
                        </>
                    ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                            Select a thread to view messages.
                        </div>
                    )}
                </div>

                <div className="vertical-label-messaging">Comms Relay // {wsConnected ? 'Live' : 'Reconnecting'}</div>
            </div>
        </DashboardLayout>
    );
};

export default Inbox;
