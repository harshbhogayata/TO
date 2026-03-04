import { useState, useRef, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import { useAIStore } from '../store/aiStore';
import { useToast } from '../contexts/ToastContext';
import { getApiErrorMessage } from '../services/api';

const styles = {
  chatContainer: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  messagesArea: { flex: 1, overflowY: 'auto', padding: '24px 32px', display: 'flex', flexDirection: 'column', gap: '16px' },
  bubbleBot: { maxWidth: '70%', padding: '16px 20px', background: 'rgba(0,0,0,0.06)', border: '1px solid rgba(0,0,0,0.12)', fontFamily: 'var(--font-body)', fontSize: '13px', lineHeight: 1.6, alignSelf: 'flex-start' },
  bubbleUser: { maxWidth: '70%', padding: '16px 20px', background: 'var(--text-black)', color: 'var(--bg-beige)', fontFamily: 'var(--font-body)', fontSize: '13px', lineHeight: 1.6, alignSelf: 'flex-end' },
  bubbleError: { maxWidth: '70%', padding: '16px 20px', background: 'rgba(200,0,0,0.06)', border: '1px solid rgba(200,0,0,0.2)', fontFamily: 'var(--font-body)', fontSize: '13px', lineHeight: 1.6, alignSelf: 'flex-start' },
  bubbleSender: { fontFamily: 'var(--font-serif)', fontSize: '10px', textTransform: 'uppercase', fontWeight: 700, marginBottom: '6px', display: 'block', opacity: 0.6 },
  quickActions: { display: 'flex', gap: '8px', padding: '12px 32px', borderTop: '1px solid var(--text-black)', flexWrap: 'wrap', background: 'rgba(0,0,0,0.03)' },
  quickBtn: { padding: '6px 14px', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', border: '1px solid var(--text-black)', background: 'transparent', cursor: 'pointer', fontFamily: 'var(--font-body)' },
  inputBar: { padding: '16px 32px', borderTop: '1px solid var(--text-black)', display: 'flex', gap: '12px' },
  chatInput: { flex: 1, padding: '14px 16px', border: '1px solid var(--text-black)', background: 'transparent', fontFamily: 'var(--font-body)', fontSize: '14px' },
  sendBtn: { padding: '14px 32px', background: 'var(--text-black)', color: 'var(--bg-beige)', border: 'none', fontFamily: 'var(--font-body)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
  typingIndicator: { fontFamily: 'var(--font-body)', fontSize: '12px', opacity: 0.5, padding: '8px 0' },
  clearBtn: { padding: '10px 24px', background: 'transparent', color: 'var(--text-black)', border: '1px solid var(--text-black)', fontFamily: 'var(--font-body)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer', letterSpacing: '1px' },
};

const ChatBubble = ({ role, content }) => {
  const isUser = role === 'user';
  const isError = role === 'error';
  const bubbleStyle = isError ? styles.bubbleError : isUser ? styles.bubbleUser : styles.bubbleBot;
  return (
    <div style={bubbleStyle}>
      <span style={{ ...styles.bubbleSender, ...(isUser ? { color: 'var(--bg-beige)', opacity: 0.5 } : {}) }}>
        {isUser ? 'You' : isError ? 'System' : 'TalentOrbit AI'}
      </span>
      {content}
    </div>
  );
};

const AIChatbot = () => {
  usePageTitle('AI Chatbot', 'Full-page AI assistant experience.');
  const { chatHistory, chatLoading, sendChatMessage, clearChat } = useAIStore();
  const { addToast } = useToast();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  useEffect(() => () => clearChat(), [clearChat]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || chatLoading) return;
    const msg = input;
    setInput('');
    try {
      await sendChatMessage(msg);
    } catch (err) {
      addToast(getApiErrorMessage(err, 'Failed to send message.'), 'error');
    }
  }, [input, chatLoading, sendChatMessage, addToast]);

  const handleQuickAction = useCallback((action) => {
    setInput(action);
    setTimeout(async () => {
      try {
        await sendChatMessage(action);
      } catch (err) {
        addToast(getApiErrorMessage(err, 'Failed to send message.'), 'error');
      }
    }, 100);
  }, [sendChatMessage, addToast]);

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } };

  const displayMessages = chatHistory.length > 0
    ? chatHistory
    : [{ role: 'assistant', content: 'Welcome back. I can help you search candidates, schedule interviews, check pipeline status, or draft job posts. What would you like to do?' }];

  return (
    <DashboardLayout
      tapeBarProps={{ title: 'TalentOrbit v2.1 // AI Assistant', status: 'Intelligence Module', info: chatLoading ? 'Thinking...' : 'Online' }}
      pageTitleLine1="AI Chat"
      pageTitleLine2="bot"
      headerRightContent={<button style={styles.clearBtn} onClick={clearChat} disabled={chatHistory.length === 0}>Clear Chat</button>}
    >
      <div style={styles.chatContainer}>
        <div style={styles.messagesArea}>
          {displayMessages.map((msg, i) => (
            <ChatBubble key={i} role={msg.role} content={msg.content} />
          ))}
          {chatLoading && (
            <div style={styles.bubbleBot}>
              <span style={styles.bubbleSender}>TalentOrbit AI</span>
              <Skeleton.Text lines={2} />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={styles.quickActions}>
          <button style={styles.quickBtn} onClick={() => handleQuickAction('Show my pipeline')}>Pipeline</button>
          <button style={styles.quickBtn} onClick={() => handleQuickAction('Next interview?')}>Interviews</button>
          <button style={styles.quickBtn} onClick={() => handleQuickAction('Draft a job post')}>Draft Post</button>
          <button style={styles.quickBtn} onClick={() => handleQuickAction('Search candidates')}>Search</button>
        </div>

        <div style={styles.inputBar}>
          <input
            style={styles.chatInput}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
          />
          <button style={styles.sendBtn} onClick={handleSend} disabled={chatLoading}>
            {chatLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default AIChatbot;
