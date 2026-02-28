import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './UserProfile.css';

const UserProfile = () => {
    const { user, setUser } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('My Profile');
    const [profile, setProfile] = useState(null);
    const [form, setForm] = useState({ full_name: '', bio: '', location: '', linkedin_url: '', portfolio_url: '' });
    const [skills, setSkills] = useState([]);
    const [skillInput, setSkillInput] = useState('');
    const [resumeFile, setResumeFile] = useState(null);
    const [avatarFile, setAvatarFile] = useState(null);
    const [avatarPreview, setAvatarPreview] = useState(null);
    const [isSaving, setIsSaving] = useState(false);
    const [saveMsg, setSaveMsg] = useState('');

    const handleAvatarChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (file.size > 2 * 1024 * 1024) {
            addToast('Image must be under 2 MB.', 'error');
            return;
        }
        setAvatarFile(file);
        setAvatarPreview(URL.createObjectURL(file));
    };

    const currentAvatarUrl = avatarPreview || user?.avatar || null;
    const initials = (user?.full_name || user?.email || '?').charAt(0).toUpperCase();

    useEffect(() => {
        authService.getMe().then(({ data }) => {
            setProfile(data.profile);
            setForm({
                full_name: data.full_name || '',
                bio: data.profile?.bio || '',
                location: data.profile?.location || '',
                linkedin_url: data.profile?.linkedin_url || '',
                portfolio_url: data.profile?.portfolio_url || '',
            });
            setSkills(data.profile?.skills || []);
        }).catch((err) => addToast(getApiErrorMessage(err, 'Failed to load profile.'), 'error'));
    }, [addToast]);

    const handleAddSkill = (e) => {
        if (e.key === 'Enter' && skillInput.trim()) {
            e.preventDefault();
            if (!skills.includes(skillInput.trim())) setSkills([...skills, skillInput.trim()]);
            setSkillInput('');
        }
    };
    const removeSkill = (s) => setSkills(skills.filter(sk => sk !== s));

    const handleSave = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        setSaveMsg('');
        try {
            const fd = new FormData();
            Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
            fd.append('skills', JSON.stringify(skills));
            if (resumeFile) fd.append('resume', resumeFile);
            if (avatarFile) fd.append('avatar', avatarFile);
            const { data } = await authService.updateTalentProfile(fd);
            setProfile(data);
            // Refresh user in auth store so avatar shows everywhere
            try {
                const meRes = await authService.getMe();
                setUser(meRes.data);
            } catch { /* non-critical */ }
            setSaveMsg('Profile updated.');
        } catch (err) {
            setSaveMsg(getApiErrorMessage(err, 'Save failed. Please try again.'));
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit v2.1 // User Profile",
                status: `Account: ${user?.email || '—'}`,
                info: "Profile Configuration"
            }}
            pageTitleLine1="User"
            pageTitleLine2="Profile"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Status</h3>
                        <p>{user?.is_verified ? 'Verified Talent' : 'Unverified'}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Plan</h3>
                        <p>{profile?.subscription_tier || 'Free'}</p>
                    </div>
                </div>
            }
        >
            <form onSubmit={handleSave} style={{ display: 'contents' }}>
                <div className="settings-grid">
                    <div className="section-column border-right">
                        {/* Avatar Upload */}
                        <div className="list-header"><h2>Profile Photo</h2></div>
                        <div className="form-section" style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                            <div
                                onClick={() => document.getElementById('avatar-input').click()}
                                style={{
                                    width: '80px', height: '80px', borderRadius: '50%',
                                    border: '2px solid var(--border-color)', overflow: 'hidden',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    cursor: 'pointer', background: '#f5f5f5', flexShrink: 0,
                                    fontSize: '28px', fontFamily: 'var(--font-serif)', fontWeight: 700,
                                    color: '#999', textTransform: 'uppercase',
                                }}
                                title="Click to change photo"
                            >
                                {currentAvatarUrl ? (
                                    <img src={currentAvatarUrl} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                ) : initials}
                            </div>
                            <input id="avatar-input" type="file" accept="image/*" style={{ display: 'none' }} onChange={handleAvatarChange} />
                            <div>
                                <button
                                    type="button"
                                    onClick={() => document.getElementById('avatar-input').click()}
                                    style={{
                                        background: 'transparent', border: '1px solid var(--border-color)',
                                        padding: '8px 20px', fontFamily: 'var(--font-sans)', fontSize: '11px',
                                        fontWeight: 700, textTransform: 'uppercase', cursor: 'pointer',
                                        letterSpacing: '1px',
                                    }}
                                >
                                    {currentAvatarUrl ? 'Change Photo' : 'Upload Photo'}
                                </button>
                                <p style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', opacity: 0.5, marginTop: '8px' }}>
                                    JPG, PNG — max 2 MB
                                </p>
                            </div>
                        </div>

                        <div className="list-header"><h2>Personal Info</h2></div>
                        <div className="form-section">
                            <div className="form-row">
                                <label className="form-label">Full Name</label>
                                <input type="text" className="form-input" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Email Address</label>
                                <input type="email" className="form-input" value={user?.email || ''} disabled style={{ opacity: 0.5 }} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Location</label>
                                <input type="text" className="form-input" value={form.location} placeholder="City, Country" onChange={e => setForm(p => ({ ...p, location: e.target.value }))} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Professional Bio</label>
                                <textarea
                                    className="form-input"
                                    style={{ height: '100px', fontSize: '14px', fontFamily: 'var(--font-sans)', resize: 'none' }}
                                    value={form.bio}
                                    placeholder="Brief overview of your professional trajectory..."
                                    onChange={e => setForm(p => ({ ...p, bio: e.target.value }))}
                                />
                            </div>
                            <div className="form-row">
                                <label className="form-label">LinkedIn URL</label>
                                <input type="url" className="form-input" value={form.linkedin_url} placeholder="https://linkedin.com/in/..." onChange={e => setForm(p => ({ ...p, linkedin_url: e.target.value }))} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Portfolio URL</label>
                                <input type="url" className="form-input" value={form.portfolio_url} placeholder="https://yoursite.com" onChange={e => setForm(p => ({ ...p, portfolio_url: e.target.value }))} />
                            </div>

                            <div className="form-row">
                                <label className="form-label">Skill Badges</label>
                                <div className="badge-grid" style={{ marginBottom: '12px' }}>
                                    {skills.map(s => (
                                        <div key={s} className="skill-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                            {s}
                                            <span style={{ cursor: 'pointer', opacity: 0.6 }} onClick={() => removeSkill(s)}>×</span>
                                        </div>
                                    ))}
                                </div>
                                <input
                                    type="text"
                                    className="form-input"
                                    placeholder="+ Add Skill (Press Enter)"
                                    value={skillInput}
                                    onChange={(e) => setSkillInput(e.target.value)}
                                    onKeyDown={handleAddSkill}
                                />
                            </div>
                        </div>

                        <div className="list-header"><h2>Resume & Assets</h2></div>
                        <div className="form-section">
                            <div
                                className="resume-upload"
                                style={{ cursor: 'pointer' }}
                                onClick={() => document.getElementById('profile-resume').click()}
                            >
                                <input id="profile-resume" type="file" accept=".pdf" style={{ display: 'none' }} onChange={e => { if (e.target.files?.[0]) setResumeFile(e.target.files[0]); }} />
                                {resumeFile ? resumeFile.name : (profile?.resume ? 'Resume on file — click to replace' : 'Click to upload Resume / CV (PDF)')}
                                <br /><span style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', fontWeight: 700 }}>Click to {profile?.resume ? 'Replace' : 'Upload'} File</span>
                            </div>
                        </div>
                    </div>

                    <div className="right-col">
                        <div className="content-pane">
                            <div className="list-header"><h2>Quiz History</h2></div>
                            <div style={{ padding: '24px 32px', fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.5, textTransform: 'uppercase' }}>
                                Quiz results will appear here after completing assessments.
                            </div>

                            <div className="list-header" style={{ marginTop: '40px' }}><h2>Save Changes</h2></div>
                            <div style={{ padding: '24px 32px' }}>
                                {saveMsg && <p style={{ fontSize: '11px', marginBottom: '12px', color: saveMsg.includes('fail') ? '#b00' : '#060' }}>{saveMsg}</p>}
                                <button type="submit" className="btn-black" style={{ width: '100%', padding: '16px', opacity: isSaving ? 0.6 : 1, cursor: isSaving ? 'not-allowed' : 'pointer' }} disabled={isSaving}>
                                    {isSaving ? 'Saving...' : 'Save Profile'}
                                </button>
                            </div>
                        </div>
                        <VerticalLabel text="Account Configuration // V2.1" />
                    </div>
                </div>
            </form>
        </DashboardLayout>
    );
};

export default UserProfile;
