import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import api from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './About.css';


const About = () => {
    usePageTitle('About', 'Learn about TalentOrbit — the next-generation recruitment platform bridging the gap between talent and opportunity.');
    const [submitted, setSubmitted] = useState(false);
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState('');
    const [form, setForm] = useState({ name: '', email: '', subject: 'Platform Inquiry', message: '' });
    const [stats, setStats] = useState({ users: '—', jobs: '—', match: '—', regions: '—' });

    useEffect(() => {
        /* Fetch real public platform stats */
        api.get('/admin-api/public-stats/')
            .then(({ data }) => {
                setStats({
                    users: data.total_users ?? '—',
                    jobs: data.total_jobs ?? '—',
                    match: '—',
                    regions: '—',
                });
            })
            .catch(() => { /* leave dashes */ });
    }, []);

    const handleContact = async (e) => {
        e.preventDefault();
        setSending(true);
        setSendError('');
        try {
            await api.post('/auth/contact/', form);
            setSubmitted(true);
            setForm({ name: '', email: '', subject: 'Platform Inquiry', message: '' });
            setTimeout(() => setSubmitted(false), 5000);
        } catch {
            setSendError('Failed to send message. Please try again.');
        } finally {
            setSending(false);
        }
    };
    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // About",
                status: "System Status: Operational",
                info: "Location: HQ / About"
            }}
            pageTitleLine1="About"
            pageTitleLine2="Orbit"
            headerRightContent={
                <div className="partner-logos-header" style={{ opacity: 0.4 }}>
                    <div className="partner-logo" style={{ fontSize: '9px' }}>PARTNERS</div>
                    <div className="partner-logo" style={{ fontSize: '9px' }}>COMING</div>
                    <div className="partner-logo" style={{ fontSize: '9px' }}>SOON</div>
                </div>
            }
        >
            <div className="about-content">
                <div className="stats-strip">
                    <div className="stat-item">
                        <h4>{stats.users}</h4>
                        <span>Registered Users</span>
                    </div>
                    <div className="stat-item">
                        <h4>{stats.jobs}</h4>
                        <span>Job Posts</span>
                    </div>
                    <div className="stat-item">
                        <h4>—</h4>
                        <span>Skill Match Engine</span>
                    </div>
                    <div className="stat-item">
                        <h4>{stats.regions}</h4>
                        <span>Active Regions</span>
                    </div>
                </div>

                <div className="about-grid">
                    <div className="section-padding">
                        <h2 className="sub-label">Our Mission</h2>
                        <p className="mission-text">
                            To redefine the orbital path of professional growth through rigorous skill validation and transparent institutional connectivity. We don't just find jobs; we align trajectories.
                        </p>
                        <div className="partner-logos-inline" style={{ opacity: 0.4 }}>
                            <span className="trusted-text">Partner integrations coming soon</span>
                        </div>
                    </div>
                    <div className="section-padding border-left">
                        <h2 className="sub-label">Support</h2>
                        <form onSubmit={handleContact}>
                            <div className="form-group">
                                <label>Your Name</label>
                                <input
                                    type="text"
                                    className="about-input"
                                    placeholder="Full name"
                                    value={form.name}
                                    onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Email Address</label>
                                <input
                                    type="email"
                                    className="about-input"
                                    placeholder="you@example.com"
                                    value={form.email}
                                    onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label>Subject</label>
                                <select
                                    className="about-input"
                                    value={form.subject}
                                    onChange={e => setForm(p => ({ ...p, subject: e.target.value }))}
                                >
                                    <option>Platform Inquiry</option>
                                    <option>Technical Support</option>
                                    <option>Partnership Request</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Your Message</label>
                                <textarea
                                    className="about-input"
                                    rows="4"
                                    placeholder="Briefly describe your request..."
                                    value={form.message}
                                    onChange={e => setForm(p => ({ ...p, message: e.target.value }))}
                                    required
                                />
                            </div>
                            {submitted && <p style={{ color: '#060', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>✓ Transmission sent.</p>}
                            {sendError && <p style={{ color: '#b00', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>{sendError}</p>}
                            <button type="submit" className="btn-black-full" disabled={sending}>
                                {sending ? 'Sending...' : 'Send Transmission'}
                            </button>
                        </form>
                    </div>
                </div>

                <div className="team-section" style={{ opacity: 0.5 }}>
                    <div style={{ width: '100%', textAlign: 'center', padding: '20px 0 10px', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--font-sans)' }}>
                        Team profiles — coming soon
                    </div>
                </div>

                <div className="section-padding border-top" style={{ textAlign: 'center', opacity: 0.5 }}>
                    <span className="footer-small">
                        TalentOrbit // Est. 2024 // Terminal-V2.1-Node-00
                    </span>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default About;
