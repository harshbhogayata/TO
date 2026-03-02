import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { useNavigate } from 'react-router-dom';
import { authService, coursesService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './SkillHub.css';

const SkillHub = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    const navigate = useNavigate();
    usePageTitle('Skill Hub', 'Explore courses and resources to develop in-demand skills and advance your career.');
    const [profile, setProfile] = useState(null);
    const [courses, setCourses] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        authService.getMe().then(({ data }) => setProfile(data.profile)).catch((err) => addToast(getApiErrorMessage(err, 'Failed to load profile.'), 'error'));
        coursesService.listCourses()
            .then(({ data }) => setCourses(data.results || data))
            .catch((err) => addToast(getApiErrorMessage(err, 'Failed to load courses.'), 'error'))
            .finally(() => setIsLoading(false));
    }, [addToast]);

    const skills = profile?.skills || [];

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit Skill Hub v1.0",
                status: `User: ${user?.full_name || user?.email || '—'}`,
                info: "Courses & Certifications"
            }}
            pageTitleLine1="Skill"
            pageTitleLine2="Hub"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Skills Listed</h3>
                        <p>{skills.length} on Profile</p>
                    </div>
                    <div className="stat-block">
                        <h3>Status</h3>
                        <p>{user?.is_verified ? 'Verified' : 'Pending'}</p>
                    </div>
                </div>
            }
        >
            <div className="quiz-alert">
                <span>Courses & quizzes are coming soon — check back shortly.</span>
            </div>

            <div className="hub-grid">
                <div className="video-library">
                    <div className="list-header">
                        <h2>Library</h2>
                        <div style={{ display: 'flex', gap: '12px' }}>
                            <span style={{ fontSize: '11px', fontWeight: 600 }}>SORT: POPULAR</span>
                        </div>
                    </div>

                    <div className="video-grid">
                        {isLoading && <div style={{ fontSize: '11px', opacity: 0.5, padding: '20px' }}>LOADING COURSES...</div>}
                        {!isLoading && courses.length === 0 && <div style={{ fontSize: '11px', opacity: 0.5, padding: '20px' }}>NO COURSES AVAILABLE YET.</div>}

                        {courses.map((v) => (
                            <div key={v.id} className="video-item">
                                <div className="thumbnail-placeholder">
                                    <img loading="lazy" src={v.img_url} alt={v.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    <span className="duration-tag">{v.duration}</span>
                                    {v.is_coming_soon && (
                                        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                            <span style={{ color: 'white', fontSize: '11px', fontFamily: 'var(--font-sans)', textTransform: 'uppercase' }}>Coming Soon</span>
                                        </div>
                                    )}
                                </div>
                                <span className="video-meta">{v.category} • {v.module_name}</span>
                                <h3 className="video-title">{v.title}</h3>
                                {v.is_coming_soon ? (
                                    <button className="btn-outline" style={{ width: '100%', opacity: 0.5, cursor: 'not-allowed' }} disabled>Coming Soon</button>
                                ) : (
                                    <button className="btn-primary" style={{ width: '100%' }} onClick={() => v.url ? window.open(v.url, '_blank') : addToast('Course viewer launching soon — stay tuned!', 'info')}>Start Course</button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="sidebar-right">
                    <div style={{ display: 'flex', height: '100%' }}>
                        <div style={{ flex: 1 }}>
                            <div className="list-header" style={{ padding: '16px 32px' }}>
                                <h2 style={{ fontSize: '20px' }}>Your Skills</h2>
                            </div>

                            {skills.length === 0 ? (
                                <div style={{ padding: '24px 32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>
                                    No skills on your profile yet.<br />
                                    <span style={{ textDecoration: 'underline', cursor: 'pointer' }} onClick={() => navigate('/profile')}>Update your profile →</span>
                                </div>
                            ) : (
                                <div style={{ padding: '16px 32px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                                    {skills.map(s => (
                                        <div key={s} style={{ padding: '6px 12px', border: '1px solid var(--border-color)', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', fontFamily: 'var(--font-sans)' }}>{s}</div>
                                    ))}
                                </div>
                            )}

                            <div className="list-header" style={{ padding: '16px 32px', marginTop: '20px' }}>
                                <h2 style={{ fontSize: '20px' }}>Earned</h2>
                            </div>

                            <div className="certificate-card" style={{ opacity: 0.4 }}>
                                <span className="video-meta">Coming Soon</span>
                                <h3 className="video-title" style={{ fontSize: '14px' }}>Certifications available after course launch</h3>
                                <p style={{ fontSize: '10px', marginBottom: '12px', opacity: 0.6 }}>Coming Soon</p>
                            </div>
                        </div>
                        <VerticalLabel text="Growth // Analytics" />
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default SkillHub;
