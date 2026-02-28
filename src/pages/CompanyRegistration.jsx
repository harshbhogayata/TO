import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import VerticalLabel from '../components/VerticalLabel';
import { useNavigate } from 'react-router-dom';
import { authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import './CompanyRegistration.css';

const CompanyRegistration = () => {
    const { addToast } = useToast();
    const navigate = useNavigate();
    const { setAuth } = useAuthStore();

    const [form, setForm] = useState({
        legal_name: '', industry: '', registration_number: '',
        email: '', full_name: '', password: '', password_confirm: ''
    });
    const [isLoading, setIsLoading] = useState(false);
    const [errors, setErrors] = useState({});

    // Restore saved draft on mount
    useEffect(() => {
        const saved = localStorage.getItem('co_reg_draft');
        if (saved) {
            try { setForm(prev => ({ ...prev, ...JSON.parse(saved) })); } catch { /* corrupt */ }
        }
    }, []);

    const handleInput = (e) => {
        setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
        setErrors(prev => ({ ...prev, [e.target.name]: null }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setErrors({});
        try {
            const { data } = await authService.registerCompany(form);
            setAuth(data.user, data.tokens.access, data.tokens.refresh);
            navigate('/company', { replace: true });
        } catch (err) {
            const apiErrors = err.response?.data;
            if (apiErrors && typeof apiErrors === 'object') {
                setErrors(apiErrors);
            } else {
                setErrors({ non_field_errors: [getApiErrorMessage(err, 'Registration failed. Please try again.')] });
            }
        } finally {
            setIsLoading(false);
        }
    };
    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Registration",
                status: "Node: Registration_Terminal_04",
                info: "Status: Secure connection established"
            }}
            pageTitleLine1="Regis"
            pageTitleLine2="tration"
            headerRightContent={
                <div style={{ textAlign: 'right' }}>
                    <div className="verification-badge">ID: TO-REG-{new Date().getFullYear()}-X</div>
                    <p style={{ fontSize: '11px', opacity: 0.6, textTransform: 'uppercase' }}>New Entity Onboarding</p>
                </div>
            }
        >
            <form onSubmit={handleSubmit} className="registration-grid" style={{ display: 'contents' }}>
                <div className="registration-grid">
                    <div className="form-section">
                        <div className="section-header">
                            <h2>01. Company Identity</h2>
                        </div>

                        <div className="input-group">
                            <label className="input-label">Legal Entity Name</label>
                            <input type="text" name="legal_name" value={form.legal_name} onChange={handleInput} className="text-input" placeholder="e.g. Volume One Studios Ltd." required />
                            {errors.legal_name && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.legal_name}</span>}
                        </div>

                        <div className="grid-2">
                            <div className="input-group">
                                <label className="input-label">Industry Sector</label>
                                <input type="text" name="industry" value={form.industry} onChange={handleInput} className="text-input" placeholder="Creative / Tech / Media" />
                                {errors.industry && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.industry}</span>}
                            </div>
                            <div className="input-group">
                                <label className="input-label">Registration Number</label>
                                <input type="text" name="registration_number" value={form.registration_number} onChange={handleInput} className="text-input" placeholder="TAX-ID-99021-X" />
                                {errors.registration_number && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.registration_number}</span>}
                            </div>
                        </div>

                        <div className="section-header" style={{ marginTop: '40px' }}>
                            <h2>02. Security Protocol</h2>
                        </div>

                        <div className="grid-2">
                            <div className="input-group">
                                <label className="input-label">Password</label>
                                <input type="password" name="password" value={form.password} onChange={handleInput} className="text-input" placeholder="Min 8 characters" required />
                                {errors.password && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.password}</span>}
                            </div>
                            <div className="input-group">
                                <label className="input-label">Confirm Password</label>
                                <input type="password" name="password_confirm" value={form.password_confirm} onChange={handleInput} className="text-input" placeholder="••••••••" required />
                                {errors.password_confirm && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.password_confirm}</span>}
                            </div>
                        </div>

                        <div className="section-header" style={{ marginTop: '40px' }}>
                            <h2>03. Verification Protocol</h2>
                        </div>

                        <div className="grid-2">
                            <div className="input-group">
                                <label className="input-label">Primary Contact Email</label>
                                <input type="email" name="email" value={form.email} onChange={handleInput} className="text-input" placeholder="admin@domain.com" required />
                                {errors.email && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.email}</span>}
                            </div>
                            <div className="input-group">
                                <label className="input-label">Authorized Signatory</label>
                                <input type="text" name="full_name" value={form.full_name} onChange={handleInput} className="text-input" placeholder="Full Legal Name" required />
                                {errors.full_name && <span style={{ color: '#b00', fontSize: '10px' }}>{errors.full_name}</span>}
                            </div>
                        </div>

                        {errors.non_field_errors && <div style={{ color: '#b00', fontSize: '12px', marginTop: '10px' }}>{Array.isArray(errors.non_field_errors) ? errors.non_field_errors.join(' ') : errors.non_field_errors}</div>}

                        <button type="submit" className="btn-primary" disabled={isLoading} style={{ width: '100%', padding: '16px 32px', marginTop: '20px', cursor: isLoading ? 'not-allowed' : 'pointer', opacity: isLoading ? 0.7 : 1 }}>
                            {isLoading ? 'Processing...' : 'Initialize Registration'}
                        </button>
                    </div>

                    <div style={{ display: 'flex' }}>
                        <div className="sidebar-right">
                            <div className="info-card">
                                <h3>Vetting Process</h3>
                                <p>All new registrations undergo a 48-hour manual review. Ensure all documentation is accurate to avoid rejection of the entity profile.</p>
                            </div>

                            <div className="info-card">
                                <h3>Required Files</h3>
                                <p>Please prepare the following for the next step:</p>
                                <ul style={{ fontSize: '11px', marginTop: '12px', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px', textTransform: 'uppercase', fontWeight: 600 }}>
                                    <li>• Articles of Incorporation</li>
                                    <li>• Proof of Address</li>
                                    <li>• VAT / Tax Certificate</li>
                                </ul>
                            </div>

                            <div style={{ marginTop: 'auto' }}>
                                <button
                                    type="button"
                                    className="btn-outline"
                                    style={{ width: '100%' }}
                                    onClick={() => {
                                        const { password: _p, password_confirm: _pc, ...safeDraft } = form; void _p; void _pc;
                                        localStorage.setItem('co_reg_draft', JSON.stringify(safeDraft));
                                        addToast('Draft saved. Your progress will be restored when you return.', 'success');
                                    }}
                                >
                                    Save Draft
                                </button>
                                <p style={{ fontSize: '10px', opacity: 0.5, marginTop: '12px', textAlign: 'center', textTransform: 'uppercase', minHeight: '14px' }}>
                                    {localStorage.getItem('co_reg_draft') ? 'Draft saved to browser' : ''}
                                </p>
                            </div>
                        </div>
                        <VerticalLabel text="Entity Onboarding // Protocol 09" />
                    </div>
                </div>
            </form>
        </DashboardLayout>
    );
};

export default CompanyRegistration;
