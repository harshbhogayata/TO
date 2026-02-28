import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Terms.css';

const Terms = () => {
    const navigate = useNavigate();
    const [accepted, setAccepted] = useState(false);

    return (
        <div className="terms-wrapper">
            <header className="terms-minimal-header">
                <div className="terms-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>TALENT<br />ORBIT</div>
            </header>

            <main className="terms-content-layout">
                <aside className="terms-toc-sidebar">
                    <h2 className="terms-toc-title">Table of Contents</h2>
                    <nav className="terms-toc-nav">
                        <a href="#section-1" className="terms-toc-link">01. Acceptance of Terms</a>
                        <a href="#section-2" className="terms-toc-link">02. Platform Usage & Licensing</a>
                        <a href="#section-3" className="terms-toc-link">03. User Obligations (Talent)</a>
                        <a href="#section-4" className="terms-toc-link">04. Corporate Obligations</a>
                        <a href="#section-5" className="terms-toc-link">05. Intellectual Property</a>
                        <a href="#section-6" className="terms-toc-link">06. Liability & Disclaimers</a>
                    </nav>
                </aside>

                <div className="terms-document-area">
                    <div className="terms-doc-header">
                        <h1 className="terms-doc-title">Terms of Service</h1>
                        <div className="terms-doc-meta">
                            <span>Last Updated: 15 October 2023</span>
                            <span>Version: 2.1.4 (Global)</span>
                        </div>
                    </div>

                    <div className="terms-legal-text">
                        <section id="section-1" className="terms-legal-section">
                            <h3 className="terms-section-heading">01. Acceptance of Terms</h3>
                            <p>By accessing or using the TalentOrbit platform, you agree to be bound by these Terms of Service. If you do not agree to all the terms and conditions of this agreement, you may not access the platform or use any services.</p>
                            <p>These Terms apply to all users of the site, including without limitation users who are browsers, vendors, customers, merchants, and/ or contributors of content.</p>
                        </section>

                        <section id="section-2" className="terms-legal-section">
                            <h3 className="terms-section-heading">02. Platform Usage & Licensing</h3>
                            <p>TalentOrbit grants you a limited, non-exclusive, non-transferable, and revocable license to use our platform strictly in accordance with these Terms.</p>
                            <p>You agree not to reproduce, duplicate, copy, sell, resell or exploit any portion of the Service, use of the Service, or access to the Service or any contact on the website through which the service is provided, without express written permission by us.</p>
                        </section>

                        <section id="section-3" className="terms-legal-section">
                            <h3 className="terms-section-heading">03. User Obligations (Talent)</h3>
                            <ul>
                                <li>You represent that all portfolio materials, resumes, and code samples submitted are your own original work or that you have the rights to display them.</li>
                                <li>You agree not to misrepresent your skills, employment history, or quiz results.</li>
                                <li>Quiz completion must be done independently without unauthorized assistance or automated tools.</li>
                            </ul>
                        </section>

                        <section id="section-4" className="terms-legal-section">
                            <h3 className="terms-section-heading">04. Corporate Obligations</h3>
                            <p>Companies utilizing TalentOrbit for recruitment agree to:</p>
                            <ul>
                                <li>Provide accurate and non-discriminatory job descriptions.</li>
                                <li>Use candidate data exclusively for the purpose of recruitment and in compliance with GDPR, CCPA, and other applicable data protection laws.</li>
                                <li>Not utilize the platform to solicit independent contract work outside the bounds of the described roles without explicit agreement.</li>
                            </ul>
                        </section>

                        <section id="section-5" className="terms-legal-section">
                            <h3 className="terms-section-heading">05. Intellectual Property</h3>
                            <p>The layout, design, data structures, and algorithmic matching systems are the exclusive property of TalentOrbit Inc. User-generated content remains the property of the respective user.</p>
                        </section>

                        <section id="section-6" className="terms-legal-section">
                            <h3 className="terms-section-heading">06. Liability & Disclaimers</h3>
                            <p>The service and all products and services delivered to you through the service are (except as expressly stated by us) provided 'as is' and 'as available' for your use, without any representation, warranties or conditions of any kind.</p>
                            <p>TalentOrbit shall not be liable for any injury, loss, claim, or any direct, indirect, incidental, punitive, special, or consequential damages of any kind, including, without limitation lost profits, lost revenue, lost savings, loss of data, replacement costs, or any similar damages.</p>
                        </section>
                    </div>

                    <div className="terms-action-footer">
                        <div className="terms-checkbox-wrapper">
                            <input
                                type="checkbox"
                                id="accept-terms"
                                className="terms-checkbox"
                                checked={accepted}
                                onChange={(e) => setAccepted(e.target.checked)}
                            />
                            <label htmlFor="accept-terms">I have read and agree to the Terms of Service and Privacy Policy.</label>
                        </div>
                        <div className="terms-button-group">
                            <button className="terms-btn-outline" onClick={() => navigate(-1)}>Decline</button>
                            <button
                                className={`terms-btn-solid ${!accepted ? 'disabled' : ''}`}
                                disabled={!accepted}
                                onClick={() => navigate('/register/user')}
                            >
                                Accept & Continue
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Terms;
