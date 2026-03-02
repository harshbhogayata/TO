import { useState, useEffect } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './CompanyProfile.css';

const CompanyProfile = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('Company Profile', 'Edit your company profile to attract top talent on TalentOrbit.');
    const [profile, setProfile] = useState(null);
    const [form, setForm] = useState({ legal_name: '', industry: '', mission_statement: '', website: '' });
    const [logoFile, setLogoFile] = useState(null);
    const [isSaving, setIsSaving] = useState(false);
    const [saveMsg, setSaveMsg] = useState('');
    const [editMode, setEditMode] = useState(false);

    useEffect(() => {
        authService.getMe().then(({ data }) => {
            const p = data.profile || data.company_profile || {};
            setProfile(p);
            setForm({
                legal_name: p.legal_name || data.full_name || '',
                industry: p.industry || '',
                mission_statement: p.mission_statement || '',
                website: p.website || '',
            });
        }).catch((err) => addToast(getApiErrorMessage(err, 'Failed to load company profile.'), 'error'));
    }, [addToast]);

    const handleSave = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        setSaveMsg('');
        try {
            const fd = new FormData();
            Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
            if (logoFile) fd.append('logo', logoFile);
            const { data } = await authService.updateCompanyProfile(fd);
            setProfile(data);
            setSaveMsg('Profile updated successfully.');
            setEditMode(false);
        } catch (err) {
            setSaveMsg(getApiErrorMessage(err, 'Save failed. Please try again.'));
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Company Profile",
                status: `Account: ${user?.email || '—'}`,
                info: "Entity Configuration"
            }}
            pageTitleLine1="Company"
            pageTitleLine2="Profile"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Verified</h3>
                        <p>{user?.is_verified ? 'Yes' : 'Pending'}</p>
                    </div>
                    <div className="stat-block">
                        <h3>Industry</h3>
                        <p>{profile?.industry || form.industry || '—'}</p>
                    </div>
                </div>
            }
        >
            <form onSubmit={handleSave} style={{ display: 'contents' }}>
                <div className="cp-edit-layout">
                    {/* Left: identity form */}
                    <div className="cp-form-col border-right">
                        <div className="list-header">
                            <h2>Company Identity</h2>
                            <button
                                type="button"
                                className="btn-outline"
                                style={{ padding: '6px 12px', fontSize: '10px' }}
                                onClick={() => setEditMode(v => !v)}
                            >
                                {editMode ? 'Cancel' : 'Edit Mode'}
                            </button>
                        </div>

                        <div className="cp-form-body">
                            <div className="form-row">
                                <label className="form-label">Legal Name</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={form.legal_name}
                                    onChange={e => setForm(p => ({ ...p, legal_name: e.target.value }))}
                                    disabled={!editMode}
                                    style={{ opacity: editMode ? 1 : 0.6 }}
                                />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Industry</label>
                                <input
                                    type="text"
                                    className="form-input"
                                    value={form.industry}
                                    placeholder="Creative / Tech / Media"
                                    onChange={e => setForm(p => ({ ...p, industry: e.target.value }))}
                                    disabled={!editMode}
                                    style={{ opacity: editMode ? 1 : 0.6 }}
                                />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Website</label>
                                <input
                                    type="url"
                                    className="form-input"
                                    value={form.website}
                                    placeholder="https://company.com"
                                    onChange={e => setForm(p => ({ ...p, website: e.target.value }))}
                                    disabled={!editMode}
                                    style={{ opacity: editMode ? 1 : 0.6 }}
                                />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Company Description</label>
                                <textarea
                                    className="form-input"
                                    style={{ height: '120px', fontFamily: 'var(--font-sans)', fontSize: '14px', resize: 'none' }}
                                    value={form.mission_statement}
                                    placeholder="Brief overview of your company..."
                                    onChange={e => setForm(p => ({ ...p, mission_statement: e.target.value }))}
                                    disabled={!editMode}
                                />
                            </div>

                            {editMode && (
                                <div className="form-row">
                                    <label className="form-label">Company Logo</label>
                                    <div
                                        className="resume-upload"
                                        style={{ cursor: 'pointer' }}
                                        onClick={() => document.getElementById('cp-logo').click()}
                                    >
                                        <input
                                            id="cp-logo"
                                            type="file"
                                            accept="image/*"
                                            style={{ display: 'none' }}
                                            onChange={e => { if (e.target.files?.[0]) setLogoFile(e.target.files[0]); }}
                                        />
                                        {logoFile ? logoFile.name : (profile?.logo ? 'Logo on file — click to replace' : 'Click to upload logo (PNG / JPG)')}
                                        <br /><span style={{ fontSize: '11px', fontFamily: 'var(--font-sans)', fontWeight: 700 }}>Click to {profile?.logo ? 'Replace' : 'Upload'}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right: info + save */}
                    <div className="cp-right-col">
                        <div style={{ flex: 1, overflowY: 'auto' }}>
                            {profile?.logo && (
                                <>
                                    <div className="list-header"><h2>Logo</h2></div>
                                    <div style={{ padding: '24px 32px' }}>
                                        <img loading="lazy" src={profile.logo} alt="Company logo" style={{ maxWidth: '180px', maxHeight: '80px', objectFit: 'contain' }} />
                                    </div>
                                </>
                            )}

                            <div className="list-header"><h2>Save Changes</h2></div>
                            <div style={{ padding: '24px 32px' }}>
                                {saveMsg && (
                                    <p style={{ fontSize: '11px', marginBottom: '12px', color: saveMsg.includes('fail') ? '#b00' : '#060', textTransform: 'uppercase' }}>{saveMsg}</p>
                                )}
                                <button
                                    type="submit"
                                    className="btn-black"
                                    style={{ width: '100%', padding: '16px', opacity: (isSaving || !editMode) ? 0.4 : 1, cursor: (isSaving || !editMode) ? 'not-allowed' : 'pointer' }}
                                    disabled={isSaving || !editMode}
                                >
                                    {isSaving ? 'Saving...' : 'Save Profile'}
                                </button>
                                {!editMode && (
                                    <p style={{ fontSize: '10px', marginTop: '8px', opacity: 0.4, textTransform: 'uppercase' }}>Enable Edit Mode to make changes</p>
                                )}
                            </div>
                        </div>
                        <VerticalLabel text="Entity Configuration // V2.1" />
                    </div>
                </div>
            </form>
        </DashboardLayout>
    );
};

export default CompanyProfile;
