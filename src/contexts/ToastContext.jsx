import { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const addToast = useCallback((message, type = 'info') => {
        const id = Math.random().toString(36).substr(2, 9);
        setToasts(prev => [...prev, { id, message, type }]);
        setTimeout(() => removeToast(id), 5000);
    }, [removeToast]);

    return (
        <ToastContext.Provider value={{ addToast }}>
            {children}
            <div style={{
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                zIndex: 9999,
                pointerEvents: 'none'
            }}>
                {toasts.map(t => (
                    <div key={t.id} style={{
                        background: t.type === 'error' ? 'var(--dark-gray)' : 'var(--text-black)',
                        color: t.type === 'error' ? '#f55' : 'var(--bg-white)',
                        padding: '16px 24px',
                        minWidth: '280px',
                        fontFamily: 'var(--font-sans)',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
                        border: t.type === 'error' ? '1px solid #330000' : '1px solid var(--text-black)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        pointerEvents: 'auto'
                    }}>
                        <span>{t.message}</span>
                        <button
                            onClick={() => removeToast(t.id)}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'inherit',
                                cursor: 'pointer',
                                marginLeft: '16px',
                                opacity: 0.5
                            }}>
                            ×
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};

export const useToast = () => useContext(ToastContext);
