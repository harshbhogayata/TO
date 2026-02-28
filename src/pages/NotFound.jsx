import DashboardLayout from '../layouts/DashboardLayout';
import { useNavigate } from 'react-router-dom';
import './NotFound.css';

const NotFound = () => {
    const navigate = useNavigate();
    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Error",
                status: "System Status: 404 Not Found",
                info: "Location: Out of Bounds"
            }}
            pageTitleLine1="404"
            pageTitleLine2="Error"
        >
            <div className="notfound-content">
                <section className="error-top">
                    <h1 className="error-code">404</h1>
                    <div className="error-message">
                        <h2>Lost Orbit</h2>
                        <p>The page you are looking for has drifted outside our reachable parameters. It may have been relocated or deleted from the system.</p>
                        <div className="search-box-nf">
                            <input type="text" placeholder="Search Console..." />
                            <button>Find</button>
                        </div>
                    </div>
                </section>

                <section className="error-bottom">
                    <div className="animation-sector">
                        <div className="orbit-container">
                            <div className="planet"></div>
                            <div className="lost-object">?</div>
                        </div>
                    </div>

                    <div className="links-sector">
                        <h3 className="sector-title">Recalibrate</h3>
                        <div className="nav-list">
                            <div className="nav-list-item" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                                <span>Return to Home</span><span>→</span>
                            </div>
                            <div className="nav-list-item" onClick={() => navigate('/jobs')} style={{ cursor: 'pointer' }}>
                                <span>View All Open Jobs</span><span>→</span>
                            </div>
                            <div className="nav-list-item" onClick={() => navigate('/support')} style={{ cursor: 'pointer' }}>
                                <span>Contact Support</span><span>→</span>
                            </div>
                            <div className="nav-list-item" onClick={() => navigate('/auth')} style={{ cursor: 'pointer' }}>
                                <span>Go to Login</span><span>→</span>
                            </div>
                        </div>
                    </div>

                    <div className="vertical-label-nf">
                        Signal Loss // Redacted
                    </div>
                </section>
            </div>
        </DashboardLayout>
    );
};

export default NotFound;
