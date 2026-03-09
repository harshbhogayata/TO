import { useState } from 'react';
import { useToast } from '../contexts/ToastContext';
import { useNavigate } from 'react-router-dom';
import { authService, intelligenceService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import './UserRegistration.css';

const UserRegistration = () => {
    const { addToast } = useToast();
    const navigate = useNavigate();
    const { setAuth } = useAuthStore();

    const [step, setStep] = useState(1);

    // Step 1 State
    const [form, setForm] = useState({ full_name: '', email: '', password: '' });
    const [role, setRole] = useState('TALENT');
    const [step1Error, setStep1Error] = useState('');

    // Step 2 State
    const [resumeFile, setResumeFile] = useState(null);
    const [isParsing, setIsParsing] = useState(false);
    const [parseProgress, setParseProgress] = useState(0);

    // Step 3 State
    const [skills, setSkills] = useState([]);
    const [skillInput, setSkillInput] = useState('');
    const [bio, setBio] = useState('');
    const [preferences, setPreferences] = useState({ location: 'Remote Only', type: 'Full-Time Role' });
    const [isLoading, setIsLoading] = useState(false);

    // --- STEP 1 LOGIC ---
    const handleInput = (e) => setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    const goStep2 = (e) => {
        e.preventDefault();
        if (role === 'COMPANY') {
            navigate('/register/company');
            return;
        }
        if (!form.full_name || !form.email || !form.password) {
            setStep1Error('Please fill all fields.');
            return;
        }
        setStep(2);
    };

    // --- STEP 2 LOGIC ---
    const handleFileUpload = (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setResumeFile(file);
            simulateParsing(file);
        }
    };

    const simulateParsing = async (file) => {
        setIsParsing(true);
        setParseProgress(20);

        try {
            const formData = new FormData();
            formData.append('resume', file);

            // Uploading and extracting...
            setParseProgress(50);
            const { data } = await intelligenceService.parseResumeAIPublic(formData);

            const extractedSkills = (data.parsed_skills || [])
                .map((skill) => (typeof skill === 'string'
                    ? skill
                    : skill.canonical_name || skill.name || ''))
                .filter(Boolean);

            if (extractedSkills.length > 0) {
                setSkills(extractedSkills);
            } else {
                setSkills(['General Professional']);
            }

            if (data.generated_bio) {
                setBio(data.generated_bio);
            }

            setParseProgress(100);
            setTimeout(() => {
                setIsParsing(false);
            }, 600);

        } catch (error) {
            addToast(getApiErrorMessage(error, 'Resume extraction failed. Using fallback skills.'), 'error');
            setParseProgress(100);
            setIsParsing(false);
            // Fallback if parsing completely fails so the user isn't stuck
            setSkills(['Communication', 'Teamwork']);
        }
    };

    // --- STEP 3 LOGIC ---
    const handleAddSkill = (e) => {
        if (e.key === 'Enter' && skillInput.trim()) {
            e.preventDefault();
            if (!skills.includes(skillInput.trim())) setSkills([...skills, skillInput.trim()]);
            setSkillInput('');
        }
    };
    const removeSkill = (s) => setSkills(skills.filter(sk => sk !== s));

    const handleSubmit = async () => {
        setIsLoading(true);
        try {
            const { data } = await authService.registerTalent({
                ...form,
                password_confirm: form.password,
                bio,
                skills,
                location: preferences.location || '',
            });
            setAuth(data.user, data.tokens.access, data.tokens.refresh);

            if (resumeFile) {
                const fd = new FormData();
                fd.append('resume', resumeFile);
                await authService.updateTalentProfile(fd).catch(() => { });
            }
            navigate('/user', { replace: true });
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Registration failed. Please try again.'), 'error');
        } finally {
            setIsLoading(false);
        }
    };

    // --- RENDERS ---
    if (step === 1) {
        return (
            <div style={{ background: 'var(--bg-beige)', color: 'var(--text-black)', width: '100%', minHeight: '100vh', minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
                <div className="wizard-tape-bar">
                    <span>// TalentOrbit Registry System v1.0</span>
                    <span>// Security: Encrypted Tunnel</span>
                    <span>// Welcome, Guest User</span>
                </div>
                <div className="onboarding-layout">
                    <aside className="wizard-sidebar-brand">
                        <div className="wizard-brand-text">Join<br />The<br />Orbit</div>
                        <div className="wizard-sidebar-footer">
                            // {new Date().getFullYear()} Global Talent Protocol<br />
                            Accelerating human potential through decentralized networking and skill verification.
                        </div>
                    </aside>
                    <main className="wizard-main">
                        <div className="wizard-progress-container">
                            <div className="wizard-progress-header">
                                <span className="wizard-step-count">[Step 01 of 03]</span>
                                <span className="wizard-step-label">Establishing Identity</span>
                            </div>
                            <div className="wizard-progress-bar-bg">
                                <div className="wizard-progress-bar-fill" style={{ width: '33.33%' }}></div>
                            </div>
                        </div>
                        <div style={{ display: 'flex', flex: 1 }}>
                            <div className="wizard-content" style={{ flex: 1 }}>
                                <h1 className="wizard-title">Create<br />Account</h1>
                                <form onSubmit={goStep2} className="wizard-form-section">
                                    <div className="wizard-field-group">
                                        <label className="wizard-label">Legal Full Name</label>
                                        <input type="text" className="wizard-input-text" placeholder="Entry Required" name="full_name" value={form.full_name} onChange={handleInput} />
                                    </div>
                                    <div className="wizard-field-group">
                                        <label className="wizard-label">Email Address</label>
                                        <input type="email" className="wizard-input-text" placeholder="name@domain.com" name="email" value={form.email} onChange={handleInput} />
                                    </div>
                                    <div className="wizard-field-group">
                                        <label className="wizard-label">Password</label>
                                        <input type="password" className="wizard-input-text" placeholder="********" name="password" value={form.password} onChange={handleInput} />
                                    </div>
                                    <div className="wizard-field-group">
                                        <label className="wizard-label">Select Protocol Role</label>
                                        <div className="wizard-role-selector">
                                            <div className={`wizard-role-option ${role === 'TALENT' ? 'active' : ''}`} onClick={() => setRole('TALENT')}>
                                                <span className="wizard-role-title">Talent</span>
                                                <span className="wizard-role-desc">Looking for opportunities</span>
                                            </div>
                                            <div className={`wizard-role-option ${role === 'COMPANY' ? 'active' : ''}`} onClick={() => setRole('COMPANY')}>
                                                <span className="wizard-role-title">Company</span>
                                                <span className="wizard-role-desc">Searching for expertise</span>
                                            </div>
                                        </div>
                                    </div>
                                    {step1Error && <span style={{ color: 'red', fontSize: '12px' }}>{step1Error}</span>}
                                    <div className="wizard-cta-container">
                                        <span className="wizard-login-link" onClick={() => navigate('/auth')}>Already Registered?</span>
                                        <button type="submit" className="wizard-btn-next">Next Step -&gt;</button>
                                    </div>
                                </form>
                            </div>
                            <div className="wizard-vertical-rule">Registration Phase // 01</div>
                        </div>
                    </main>
                </div>
            </div>
        );
    }

    if (step === 2) {
        return (
            <div style={{ background: 'var(--bg-beige)', color: 'var(--text-black)', width: '100%', minHeight: '100vh', minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
                <div className="wizard-tape-bar">
                    <span>// TalentOrbit Onboarding Protocol</span>
                    <span>// Module: Profile Building</span>
                    <span>// Step: 02 - Resume Extraction</span>
                </div>
                <div className="onboarding-app-container">
                    <aside className="nav-sidebar">
                        <div className="nav-brand">Talent<br />Orbit</div>
                        <nav style={{ marginBottom: '40px' }}>
                            <div className="nav-item-new"><span className="nav-num-new">[01]</span><span className="nav-label-new">Basic Info</span></div>
                            <div className="nav-item-new active"><span className="nav-num-new">[02]</span><span className="nav-label-new">Experience</span></div>
                            <div className="nav-item-new"><span className="nav-num-new">[03]</span><span className="nav-label-new">Finalize</span></div>
                        </nav>
                    </aside>
                    <main className="wizard-main">
                        <header className="step-content-header">
                            <h1 className="step-page-title">Resume<br />Upload</h1>
                            <div className="step-indicator">
                                <h3 style={{ margin: 0, textTransform: 'uppercase' }}>Step 02 // 03</h3>
                            </div>
                        </header>
                        <div className="wizard-container-2">
                            <section className="upload-section">
                                <label className="drop-zone" htmlFor="resume-upload">
                                    <h3>Drag & Drop Resume</h3>
                                    <p>Our AI will automatically parse your experience and skills.</p>
                                    <div className="btn-black" style={{ background: 'transparent', border: '1px solid black', color: 'black', marginBottom: '24px', display: 'inline-block' }}>Browse Files</div>
                                    <div className="file-hints">Supported: PDF, DOCX, TXT | Max 5MB</div>
                                    <input type="file" id="resume-upload" style={{ display: 'none' }} accept=".pdf,.docx,.txt" onChange={handleFileUpload} />
                                </label>
                                {(isParsing || resumeFile) && (
                                    <div className="parsing-status">
                                        <div className="status-header">
                                            <span className="status-label">{isParsing ? 'Analyzing your resume...' : 'Extraction Complete'}</span>
                                            <span className="status-label" style={{ fontFamily: 'var(--font-sans)', fontSize: '11px' }}>{parseProgress}%</span>
                                        </div>
                                        <div className="loading-bar-bg">
                                            <div className="loading-bar-fill" style={{ width: `${parseProgress}%` }}></div>
                                        </div>
                                    </div>
                                )}
                                <div className="action-footer">
                                    <button className="btn-black" style={{ background: 'transparent', color: 'black', border: '1px solid black' }} onClick={() => setStep(1)}>Back</button>
                                    <button className="btn-black" disabled={isParsing} onClick={() => setStep(3)}>
                                        {resumeFile ? 'Continue to Preview' : 'Skip - Continue Without Resume'}
                                    </button>
                                </div>
                            </section>
                            <section style={{ display: 'flex' }}>
                                <div className="preview-pane">
                                    <h2 className="preview-header">Data Preview</h2>
                                    <div className="skeleton-group">
                                        <span className="status-label" style={{ fontSize: '10px', opacity: 0.6 }}>Extracted Identity</span>
                                        {parseProgress > 40 ? <div style={{ fontWeight: 600, fontSize: '14px' }}>{form.full_name || '...'}</div> : <div className="skeleton medium"></div>}
                                        {parseProgress > 40 ? <div style={{ fontSize: '12px', opacity: 0.7 }}>{form.email || '...'}</div> : <div className="skeleton small"></div>}
                                    </div>
                                    <div className="skeleton-group" style={{ marginTop: '20px' }}>
                                        <span className="status-label" style={{ fontSize: '10px', opacity: 0.6 }}>Work History</span>
                                        {parseProgress > 80 ? (
                                            <div style={{ fontSize: '12px' }}>Designer<br />Current</div>
                                        ) : (
                                            <><div className="skeleton large"></div><div className="skeleton medium"></div><div className="skeleton large"></div></>
                                        )}
                                    </div>
                                    <div className="skeleton-group" style={{ marginTop: '20px' }}>
                                        <span className="status-label" style={{ fontSize: '10px', opacity: 0.6 }}>Core Competencies</span>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            {parseProgress === 100 ? (
                                                <div className="skill-chip">UI DESIGN</div>
                                            ) : (
                                                <><div className="skeleton small" style={{ width: '60px' }}></div><div className="skeleton small" style={{ width: '80px' }}></div><div className="skeleton small" style={{ width: '40px' }}></div></>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <div className="wizard-vertical-rule">Onboarding // Process</div>
                            </section>
                        </div>
                    </main>
                </div>
            </div>
        );
    }

    if (step === 3) {
        return (
            <div style={{ background: 'var(--bg-beige)', color: 'var(--text-black)', width: '100%', minHeight: '100vh', minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
                <div className="wizard-tape-bar">
                    <span>// TalentOrbit Admin Console v2.1</span>
                    <span>// Onboarding Status: Finalizing Node</span>
                    <span>// Step: 03 of 03</span>
                </div>
                <div className="onboarding-app-container">
                    <aside className="nav-sidebar">
                        <div className="nav-brand">Talent<br />Orbit</div>
                        <nav style={{ marginBottom: '40px' }}>
                            <div className="nav-item-new"><span className="nav-num-new">[01]</span><span className="nav-label-new">Identity</span></div>
                            <div className="nav-item-new"><span className="nav-num-new">[02]</span><span className="nav-label-new">Upload CV</span></div>
                            <div className="nav-item-new active"><span className="nav-num-new">[03]</span><span className="nav-label-new">Verification</span></div>
                        </nav>
                    </aside>
                    <main className="wizard-main">
                        <header className="step-content-header">
                            <h1 className="step-page-title">Final<br />Setup</h1>
                            <div className="step-indicator">
                                <h3 style={{ margin: 0 }}>Onboarding Wizard</h3>
                                <p style={{ margin: 0 }}>Step 3: Verification & Bio</p>
                            </div>
                        </header>
                        <div className="setup-grid">
                            <div className="setup-form-section">
                                <div className="input-group">
                                    <label className="input-label">Extracted Skill Tags</label>
                                    <div className="skill-container">
                                        {skills.map(s => (
                                            <div className="skill-chip" key={s}>
                                                {s} <span className="skill-remove" onClick={() => removeSkill(s)}>x</span>
                                            </div>
                                        ))}
                                        <input
                                            type="text"
                                            className="skill-add"
                                            placeholder="+ Add Skill (Enter)"
                                            value={skillInput}
                                            onChange={(e) => setSkillInput(e.target.value)}
                                            onKeyDown={handleAddSkill}
                                        />
                                    </div>
                                    <span className="parse-notice">// {skills.length} Skills identified from "{resumeFile ? resumeFile.name : 'Unknown'}"</span>
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Professional Bio</label>
                                    <textarea className="bio-textarea" placeholder="Describe your creative approach..." value={bio} onChange={e => setBio(e.target.value)}></textarea>
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Career Preferences</label>
                                    <div className="pref-grid">
                                        <select className="select-box" value={preferences.location} onChange={e => setPreferences({ ...preferences, location: e.target.value })}>
                                            <option>Remote Only</option>
                                            <option>Hybrid Preferred</option>
                                            <option>On-site</option>
                                        </select>
                                        <select className="select-box" value={preferences.type} onChange={e => setPreferences({ ...preferences, type: e.target.value })}>
                                            <option>Full-Time Role</option>
                                            <option>Contract / Freelance</option>
                                            <option>Retainer Basis</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', height: '100%' }}>
                                <div className="setup-preview-pane">
                                    <h2 className="section-title">Preview</h2>
                                    <div className="card-preview">
                                        <div className="card-header">Profile Card // 03</div>
                                        <div className="card-body">
                                            <div style={{ width: '80px', height: '80px', background: '#ccc', marginBottom: '16px', filter: 'grayscale(100%)', border: '1px solid #000' }}></div>
                                            <h3 style={{ fontFamily: 'var(--font-serif)', textTransform: 'uppercase', marginBottom: '4px' }}>{form.full_name || 'Anonymous'}</h3>
                                            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', opacity: 0.6, textTransform: 'uppercase', marginBottom: '12px' }}>{skills[0] || 'Professional'}</p>
                                            <p style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', lineHeight: 1.4 }}>{bio}</p>
                                        </div>
                                    </div>
                                    <button className="btn-finish" onClick={handleSubmit} disabled={isLoading}>
                                        {isLoading ? 'Finalizing...' : 'Finish Setup'}
                                    </button>
                                </div>
                                <div className="wizard-vertical-rule">Finalization // Sequence</div>
                            </div>
                        </div>
                    </main>
                </div>
            </div>
        );
    }

    return null;
};

export default UserRegistration;


