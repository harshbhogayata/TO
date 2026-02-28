import { Link, useNavigate } from 'react-router-dom';
import TapeBar from '../components/TapeBar';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';
import './Home.css';

const Home = () => {
    const navigate = useNavigate();
    const { isAuthenticated, user } = useAuthStore();
    usePageTitle('Home');
    return (
        <div className="home-container">
            <TapeBar
                title="TalentOrbit Ecosystem v2.1"
                status="Next Generation Recruitment"
                info="Est. 2024"
            />

            <nav className="public-nav">
                <div className="logo">Talent<br />Orbit</div>
                <div className="nav-links">
                    <span onClick={() => navigate('/about')} style={{ cursor: 'pointer' }}>About</span>
                    <span onClick={() => navigate('/pricing')} style={{ cursor: 'pointer' }}>Pricing</span>
                    <span onClick={() => navigate('/support')} style={{ cursor: 'pointer' }}>Support</span>
                </div>
                <div className="header-actions">
                    {isAuthenticated ? (
                        <button className="nav-btn-outline" onClick={() => navigate(user?.role === 'COMPANY' ? '/company' : user?.role === 'ADMIN' ? '/admin' : '/user')}>
                            Dashboard
                        </button>
                    ) : (
                        <>
                            <button className="nav-btn-outline" onClick={() => navigate('/auth')}>Login</button>
                            <button className="nav-btn-solid" onClick={() => navigate('/register/user')}>Register</button>
                        </>
                    )}
                </div>
            </nav>

            <header className="hero">
                <div className="hero-content">
                    <h1 className="hero-title">Beyond<br />The Hire</h1>
                    <p className="hero-subtitle">The first specialized network connecting high-performance creative talent with the world's most ambitious studios.</p>
                    <div>
                        <Link to="/register/company" className="btn btn-black" style={{ padding: '18px 40px', fontSize: '14px' }}>Get Started</Link>
                    </div>
                </div>
                <div className="hero-image"></div>
            </header>

            <div className="featured-companies">
                <div className="company-track">
                    {/* First set */}
                    <div className="company-logo">Volume One</div>
                    <div className="company-logo">TechFlow Inc.</div>
                    <div className="company-logo">Global Brands</div>
                    <div className="company-logo">Design Co.</div>
                    <div className="company-logo">BuildIt</div>
                    <div className="company-logo">Studio Arktos</div>
                    <div className="company-logo">Nexus Media</div>
                    {/* Duplicate set — for seamless infinite loop */}
                    <div className="company-logo">Volume One</div>
                    <div className="company-logo">TechFlow Inc.</div>
                    <div className="company-logo">Global Brands</div>
                    <div className="company-logo">Design Co.</div>
                    <div className="company-logo">BuildIt</div>
                    <div className="company-logo">Studio Arktos</div>
                    <div className="company-logo">Nexus Media</div>
                </div>
            </div>

            <div className="section-header">
                <h2>The Value<br />Proposition</h2>
                <div className="attribution">// Why TalentOrbit?</div>
            </div>

            <div className="grid-3">
                <div className="feature-card">
                    <span className="feature-num">[01]</span>
                    <h3 className="feature-title">Verified Skills</h3>
                    <p className="feature-text">Our proprietary quiz system and portfolio review ensure that every talent in our orbit is qualified, capable, and ready to deliver.</p>
                </div>
                <div className="feature-card">
                    <span className="feature-num">[02]</span>
                    <h3 className="feature-title">Studio Match</h3>
                    <p className="feature-text">We go beyond keywords. Our algorithm matches creative culture and technical requirements for long-term placement success.</p>
                </div>
                <div className="feature-card">
                    <span className="feature-num">[03]</span>
                    <h3 className="feature-title">Rapid Tendering</h3>
                    <p className="feature-text">Companies can post tenders and receive qualified bids within hours, not weeks. Streamlined flow from brief to contract.</p>
                </div>
            </div>

            <div className="testimonial-section">
                <div className="testimonial-box">
                    <p className="quote">"TalentOrbit changed how we scale our design team. The quality of verified applicants is unmatched in the current market."</p>
                    <p className="attribution">Sarah Jenkins — Creative Director, Volume One</p>
                </div>
                <div className="testimonial-box" style={{ background: '#D9D5CB' }}>
                    <p className="quote">"Finally, a platform that understands the nuance of creative work. I found my dream role at TechFlow within three days."</p>
                    <p className="attribution">Marcus Thorne — Senior Frontend Developer</p>
                </div>
            </div>

            <div className="split-row">
                <div className="split-image" style={{ backgroundImage: "url('https://images.unsplash.com/photo-1515378960530-7c0da6231fb1?q=80&w=1000&auto=format&fit=crop')" }}></div>
                <div className="hero-content" style={{ borderRight: 'none' }}>
                    <h2 className="hero-title" style={{ fontSize: '64px' }}>Ready to<br />Orbit?</h2>
                    <p className="feature-text" style={{ marginBottom: '30px' }}>Join 12,000+ professionals and 800+ companies already redefining the creative industry.</p>
                    <div className="cta-group">
                        <Link to="/register/user" className="btn btn-black">Create Account</Link>
                        <Link to="/support" className="btn btn-outline">Schedule Demo</Link>
                    </div>
                </div>
            </div>

            <footer className="public-footer">
                <div className="logo" style={{ color: 'var(--text-white)' }}>Talent<br />Orbit</div>
                <div className="footer-copy">
                    © {new Date().getFullYear()} TalentOrbit Acquisition Group. All Rights Reserved.
                </div>
                <div className="cta-group">
                    <Link to="/terms" className="nav-link footer-link">Terms</Link>
                    <Link to="/privacy" className="nav-link footer-link">Privacy</Link>
                    <a href="https://twitter.com" target="_blank" rel="noreferrer" className="nav-link footer-link">Twitter</a>
                </div>
            </footer>
        </div>
    );
};

export default Home;
