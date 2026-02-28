import { useNavigate } from 'react-router-dom';
import './Terms.css';

const Privacy = () => {
    const navigate = useNavigate();

    return (
        <div className="terms-wrapper">
            <header className="terms-minimal-header">
                <div className="terms-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>TALENT<br />ORBIT</div>
            </header>

            <main className="terms-content-layout">
                <aside className="terms-toc-sidebar">
                    <h2 className="terms-toc-title">Table of Contents</h2>
                    <nav className="terms-toc-nav">
                        <a href="#section-1" className="terms-toc-link">01. Data We Collect</a>
                        <a href="#section-2" className="terms-toc-link">02. How We Use Data</a>
                        <a href="#section-3" className="terms-toc-link">03. Data Sharing</a>
                        <a href="#section-4" className="terms-toc-link">04. Your Rights</a>
                        <a href="#section-5" className="terms-toc-link">05. Data Retention</a>
                        <a href="#section-6" className="terms-toc-link">06. Contact Us</a>
                    </nav>
                </aside>

                <div className="terms-document-area">
                    <div className="terms-doc-header">
                        <h1 className="terms-doc-title">Privacy Policy</h1>
                        <div className="terms-doc-meta">
                            <span>Last Updated: 15 October 2023</span>
                            <span>Version: 1.4.0 (Global)</span>
                        </div>
                    </div>

                    <div className="terms-legal-text">
                        <section id="section-1" className="terms-legal-section">
                            <h3 className="terms-section-heading">01. Data We Collect</h3>
                            <p>TalentOrbit collects information you provide directly to us, such as when you create an account, submit a profile, apply for a job, or contact us. This includes:</p>
                            <ul>
                                <li>Identity data: full name, email address, profile photo.</li>
                                <li>Professional data: resume, skills, portfolio links, work history.</li>
                                <li>Usage data: pages visited, features used, login timestamps.</li>
                                <li>Communications: messages sent through our platform.</li>
                            </ul>
                        </section>

                        <section id="section-2" className="terms-legal-section">
                            <h3 className="terms-section-heading">02. How We Use Data</h3>
                            <p>We use collected data to operate and improve the platform, match talent with relevant opportunities, send transactional and service notifications, and comply with legal obligations. We do not use your data to serve third-party advertising.</p>
                        </section>

                        <section id="section-3" className="terms-legal-section">
                            <h3 className="terms-section-heading">03. Data Sharing</h3>
                            <p>We share your professional profile data with companies you apply to or that you explicitly permit. We do not sell personal data to third parties. We may share data with service providers who process data on our behalf under strict confidentiality agreements.</p>
                        </section>

                        <section id="section-4" className="terms-legal-section">
                            <h3 className="terms-section-heading">04. Your Rights</h3>
                            <ul>
                                <li>Access and export a copy of your personal data.</li>
                                <li>Correct inaccurate data in your profile.</li>
                                <li>Request deletion of your account and associated data.</li>
                                <li>Withdraw consent for optional data processing at any time.</li>
                            </ul>
                            <p>To exercise these rights, contact us at privacy@talentorbit.com.</p>
                        </section>

                        <section id="section-5" className="terms-legal-section">
                            <h3 className="terms-section-heading">05. Data Retention</h3>
                            <p>We retain your data for as long as your account is active, or as needed to provide you services. After account deletion, data is purged within 30 days, except where retention is required by law.</p>
                        </section>

                        <section id="section-6" className="terms-legal-section">
                            <h3 className="terms-section-heading">06. Contact Us</h3>
                            <p>If you have questions about this Privacy Policy or your data, contact our Data Protection Officer at <strong>privacy@talentorbit.com</strong> or write to: TalentOrbit Inc., 1422 Vector Plaza, Suite 900, New York, NY 10013.</p>
                        </section>
                    </div>

                    <div className="terms-action-footer">
                        <div className="terms-button-group">
                            <button className="terms-btn-outline" onClick={() => navigate(-1)}>← Back</button>
                            <button className="terms-btn-solid" onClick={() => navigate('/')}>Return Home</button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Privacy;
