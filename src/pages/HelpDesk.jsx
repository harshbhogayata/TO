import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import api, { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './HelpDesk.css';

const HelpDesk = () => {
    usePageTitle('Help Desk');
    const [submitted, setSubmitted] = useState(false);
    const [sending, setSending] = useState(false);
    const [openFaq, setOpenFaq] = useState(null);
    const [sendError, setSendError] = useState('');
    const [form, setForm] = useState({ name: '', email: '', subject: 'Technical Issue', message: '' });
    const [localTime, setLocalTime] = useState('');

    /* Live clock for header */
    useEffect(() => {
        const tick = () => {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const offset = -now.getTimezoneOffset() / 60;
            const sign = offset >= 0 ? '+' : '';
            setLocalTime(`${h}:${m} GMT${sign}${offset}`);
        };
        tick();
        const id = setInterval(tick, 30000);
        return () => clearInterval(id);
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSending(true);
        setSendError('');
        try {
            await api.post('/auth/contact/', form);
            setSubmitted(true);
            setForm({ name: '', email: '', subject: 'Technical Issue', message: '' });
            setTimeout(() => setSubmitted(false), 5000);
        } catch (err) {
            setSendError(getApiErrorMessage(err, 'Failed to send inquiry. Please try again.'));
        } finally {
            setSending(false);
        }
    };
    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Support",
                status: "System Status: Operational",
                info: "Support Response Time: < 15m"
            }}
            pageTitleLine1="Help"
            pageTitleLine2="Desk"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Support</h3>
                        <p>Email Only</p>
                    </div>
                    <div className="stat-block">
                        <h3>Response Time</h3>
                        <p>{"< 24h"}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Local Time</h3>
                        <p>{localTime || '—'}</p>
                    </div>
                </div>
            }
        >
            <div className="support-grid">
                <div className="support-column border-right">
                    <div className="section-header">Submit Inquiry</div>
                    <form className="inquiry-form" onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Full Name</label>
                            <input
                                type="text"
                                className="form-input"
                                placeholder="Enter name"
                                value={form.name}
                                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Email Address</label>
                            <input
                                type="email"
                                className="form-input"
                                placeholder="you@example.com"
                                value={form.email}
                                onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Subject</label>
                            <select
                                className="form-input"
                                value={form.subject}
                                onChange={e => setForm(p => ({ ...p, subject: e.target.value }))}
                            >
                                <option>Technical Issue</option>
                                <option>Billing &amp; Payments</option>
                                <option>Account Security</option>
                                <option>General Feedback</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Message</label>
                            <textarea
                                className="form-input form-textarea"
                                placeholder="How can we assist?"
                                value={form.message}
                                onChange={e => setForm(p => ({ ...p, message: e.target.value }))}
                                required
                            />
                        </div>
                        {submitted && <p style={{ color: '#060', fontSize: '11px', textTransform: 'uppercase' }}>✓ Inquiry dispatched successfully.</p>}
                        {sendError && <p style={{ color: '#b00', fontSize: '11px', textTransform: 'uppercase' }}>{sendError}</p>}
                        <button type="submit" className="btn-black-support" disabled={sending}>
                            {sending ? 'Dispatching...' : 'Dispatch Inquiry'}
                        </button>
                    </form>

                    <div className="section-header border-top">Direct Contact</div>
                    <div className="contact-methods">
                        <div className="method-card">
                            <h4>Email Support</h4>
                            <p>support@talentorbit.com<br />Primary contact channel</p>
                        </div>
                        <div className="method-card">
                            <h4>Contact Form</h4>
                            <p>Use the inquiry form<br />on this page</p>
                        </div>
                        <div className="method-card">
                            <h4>Response Time</h4>
                            <p>Within 24 hours<br />Monday – Friday</p>
                        </div>
                        <div className="method-card">
                            <h4>Priority Access</h4>
                            <p>Reserved for Enterprise<br />Upgrade required</p>
                        </div>
                    </div>
                </div>

                <div className="support-column" style={{ borderRight: 'none' }}>
                    <div className="flex-row" style={{ height: '100%' }}>
                        <div style={{ flex: 1 }}>
                            <div className="section-header">Frequently Asked</div>
                            <div className="faq-item">
                                <div className="faq-question" style={{ cursor: 'pointer' }} onClick={() => setOpenFaq(openFaq === 0 ? null : 0)}>How to reset system credentials? <span style={{ fontSize: '20px' }}>{openFaq === 0 ? '−' : '+'}</span></div>
                                {openFaq === 0 && <div className="faq-answer">Navigate to [06] Settings &gt; Security and trigger a global key reset. A verification code will be dispatched to your encrypted mobile device.</div>}
                            </div>
                            <div className="faq-item">
                                <div className="faq-question" style={{ cursor: 'pointer' }} onClick={() => setOpenFaq(openFaq === 1 ? null : 1)}>Adding new enterprise nodes? <span style={{ fontSize: '20px' }}>{openFaq === 1 ? '−' : '+'}</span></div>
                                {openFaq === 1 && <div className="faq-answer">Tier 2 administrators can expand nodes via the Companies console. Standard limits apply based on current subscription level.</div>}
                            </div>
                            <div className="faq-item">
                                <div className="faq-question" style={{ cursor: 'pointer' }} onClick={() => setOpenFaq(openFaq === 2 ? null : 2)}>Data export protocols? <span style={{ fontSize: '20px' }}>{openFaq === 2 ? '−' : '+'}</span></div>
                                {openFaq === 2 && <div className="faq-answer">Exports are available in JSON and CSV formats via the Dashboard report generator. Logs are kept for 90 days.</div>}
                            </div>

                            <div className="office-info">
                                <div className="section-header" style={{ padding: '0 0 24px 0', borderBottom: 'none' }}>Office Location</div>
                                <h4>Main Operations Center</h4>
                                <p>1422 Vector Plaza, Suite 900<br />Industrial District, New York, NY 10013</p>
                                <div className="map-placeholder"></div>
                            </div>
                        </div>
                        <div className="vertical-label-support">
                            Operational Support // Terminal
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default HelpDesk;
