import { useState, useEffect, useRef } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import { messagingService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './Inbox.css';

const Inbox = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('Inbox', 'Messages between you and recruiters. Stay connected throughout the hiring process.');
    const [threads, setThreads] = useState([]);
    const [activeThread, setActiveThread] = useState(null);
    const [messages, setMessages] = useState([]);
    const [draft, setDraft] = useState('');
    const [sending, setSending] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [showNewThread, setShowNewThread] = useState(false);
    const [newRecipientEmail, setNewRecipientEmail] = useState('');
    const [newInitialMsg, setNewInitialMsg] = useState('');
    const [newThreadError, setNewThreadError] = useState('');
    const [creatingThread, setCreatingThread] = useState(false);
    const [threadSearch, setThreadSearch] = useState('');
    const bottomRef = useRef(null);

    useEffect(() => {
        messagingService.myThreads()
            .then(({ data }) => {
                const list = data.results || data;
                setThreads(list);
                if (list.length > 0) selectThread(list[0]);
            })
            .catch((err) => addToast(getApiErrorMessage(err, 'Failed to load conversations.'), 'error'))
            .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    /* Poll active thread messages every 10s for near-real-time updates */
    useEffect(() => {
        if (!activeThread) return;
        const threadId = activeThread.id;
        const interval = setInterval(async () => {
            try {
                const { data } = await messagingService.getMessages(threadId);
                const fresh = data.results || data;
                setMessages(prev => {
                    if (fresh.length !== prev.length) return fresh;
                    return prev;
                });
            } catch { /* silent */ }
        }, 10000);
        return () => clearInterval(interval);
    }, [activeThread]);

    const selectThread = async (thread) => {
        setActiveThread(thread);
        try {
            const { data } = await messagingService.getMessages(thread.id);
            setMessages(data.results || data);
        } catch (err) {
            setMessages([]);
            addToast(getApiErrorMessage(err, 'Failed to load messages.'), 'error');
        }
    };

    const handleSend = async () => {
        if (!draft.trim() || !activeThread || sending) return;
        setSending(true);
        try {
            const { data } = await messagingService.sendMessage({ thread: activeThread.id, body: draft.trim() });
            setMessages(prev => [...prev, data]);
            setDraft('');
            setThreads(prev => prev.map(t =>
                t.id === activeThread.id
                    ? { ...t, last_message: { body: draft.trim(), sender_name: user?.full_name, sent_at: new Date().toISOString() } }
                    : t
            ));
        } catch (err) { addToast(getApiErrorMessage(err, 'Failed to send message.'), 'error'); }
        finally { setSending(false); }
    };

    const handleCreateThread = async (e) => {
        e.preventDefault();
        if (!newRecipientEmail.trim()) return;
        setCreatingThread(true);
        setNewThreadError('');
        try {
            const { data } = await messagingService.createThread({
                recipient_email: newRecipientEmail.trim(),
                initial_message: newInitialMsg.trim() || undefined,
            });
            setThreads(prev => {
                const filtered = prev.filter(t => t.id !== data.id);
                return [data, ...filtered];
            });
            setShowNewThread(false);
            setNewRecipientEmail('');
            setNewInitialMsg('');
            selectThread(data);
        } catch (err) {
            setNewThreadError(getApiErrorMessage(err, 'Failed to create thread. Check the email matches a valid user.'));
        } finally {
            setCreatingThread(false);
        }
    };

    const getOtherParticipant = (thread) =>
        thread.participants?.find(p => p.id !== user?.id) || thread.participants?.[0];

    const formatTime = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        const now = new Date();
        if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Inbox",
                status: "Communications: Secured",
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
                        {isLoading && <Skeleton.Threads count={5} />}
                        {!isLoading && threads.length === 0 && (
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
                            const isActive = activeThread?.id === thread.id;
                            return (
                                <div
                                    key={thread.id}
                                    className={`thread-item ${isActive ? 'active' : ''}`}
                                    onClick={() => selectThread(thread)}
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
                                            <p>{thread.job_title ? `[${thread.job_title}] ` : ''}{thread.last_message?.body || 'No messages yet.'}</p>
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
                                        <span className="user-status">{getOtherParticipant(activeThread)?.role || ''}</span>
                                    </div>
                                </div>
                            </div>

                            <div className="message-history">
                                {messages.length === 0 && (
                                    <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase', textAlign: 'center' }}>
                                        No messages in this thread yet. Send the first one.
                                    </div>
                                )}
                                {messages.map(msg => {
                                    const isMine = msg.sender === user?.id || msg.sender_name === user?.full_name;
                                    return (
                                        <div key={msg.id} className={`message ${isMine ? 'sent' : 'received'}`}>
                                            <div className="message-content">{msg.body}</div>
                                            <div className="message-time">{formatTime(msg.sent_at)}</div>
                                        </div>
                                    );
                                })}
                                <div ref={bottomRef} />
                            </div>

                            <div className="composer">
                                <input
                                    type="text"
                                    className="composer-input"
                                    placeholder="Type your transmission..."
                                    value={draft}
                                    onChange={e => setDraft(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
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

                <div className="vertical-label-messaging">Comms Relay // Encrypted</div>
            </div>
        </DashboardLayout>
    );
};

export default Inbox;
