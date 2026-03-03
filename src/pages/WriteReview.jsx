import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import reviewService from '../services/reviewService';
import { useReviewStore } from '../store/reviewStore';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import './WriteReview.css';

const RATING_CATEGORIES = [
    { key: 'rating_culture', label: 'Culture & Values' },
    { key: 'rating_growth', label: 'Career Growth' },
    { key: 'rating_compensation', label: 'Compensation' },
    { key: 'rating_management', label: 'Management' },
    { key: 'rating_worklife', label: 'Work-Life Balance' },
];

const EMPLOYMENT_OPTIONS = [
    { value: 'current_full', label: 'Current — Full-time' },
    { value: 'current_part', label: 'Current — Part-time' },
    { value: 'current_intern', label: 'Current — Intern' },
    { value: 'former_full', label: 'Former — Full-time' },
    { value: 'former_part', label: 'Former — Part-time' },
    { value: 'former_intern', label: 'Former — Intern' },
];

const WriteReview = () => {
    const navigate = useNavigate();
    const { companyId } = useParams();
    const { submitting, submitError, setSubmitting, setSubmitError } = useReviewStore();

    usePageTitle('Write Review', 'Share your workplace experience honestly and constructively.');

    const [form, setForm] = useState({
        is_anonymous: true,
        headline: '',
        rating_culture: 3,
        rating_growth: 3,
        rating_compensation: 3,
        rating_management: 3,
        rating_worklife: 3,
        pros: '',
        cons: '',
        employment_status: '',
        department: '',
        role_title: '',
        tenure_months: '',
    });

    const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

    const overallRating = (
        (form.rating_culture + form.rating_growth + form.rating_compensation +
            form.rating_management + form.rating_worklife) / 5
    ).toFixed(1);

    const wordCount = (form.pros.split(/\s+/).filter(Boolean).length +
        form.cons.split(/\s+/).filter(Boolean).length);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setSubmitError(null);

        try {
            const payload = {
                company: companyId,
                is_anonymous: form.is_anonymous,
                headline: form.headline,
                rating_culture: form.rating_culture,
                rating_growth: form.rating_growth,
                rating_compensation: form.rating_compensation,
                rating_management: form.rating_management,
                rating_worklife: form.rating_worklife,
                pros: form.pros,
                cons: form.cons,
                employment_status: form.employment_status || undefined,
                department: form.department || undefined,
                role_title: form.role_title || undefined,
                tenure_months: form.tenure_months ? parseInt(form.tenure_months, 10) : undefined,
            };
            await reviewService.createReview(payload);
            navigate(`/reviews/${companyId}`);
        } catch (err) {
            setSubmitError(getApiErrorMessage(err, 'Failed to submit review.'));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'TalentOrbit Workplace Intel',
                status: 'System Status: Operational',
                info: 'Submission: Secure',
            }}
            pageTitleLine1="Write"
            pageTitleLine2="Review"
            headerRightContent={
                <div className="wr-header-stats">
                    <div className="wr-stat-block">
                        <h3>Overall Score</h3>
                        <p>{overallRating} / 5</p>
                    </div>
                    <div className="wr-stat-block">
                        <h3>Word Count</h3>
                        <p>{wordCount} / 20 min</p>
                    </div>
                </div>
            }
        >
            <div className="wr-layout">
                {/* ── Form Panel ─────────────────────────────── */}
                <form className="wr-form-panel" onSubmit={handleSubmit}>
                    {submitError && <div className="wr-error-banner">{submitError}</div>}

                    {/* Anonymous toggle */}
                    <div className="wr-section">
                        <h3 className="wr-section-title">Privacy</h3>
                        <div className="wr-toggle-row">
                            <div>
                                <div className="wr-toggle-label">Anonymous Review</div>
                                <div className="wr-toggle-desc">
                                    Your identity will be hidden from the company and public
                                </div>
                            </div>
                            <label className="wr-toggle-switch">
                                <input
                                    type="checkbox"
                                    checked={form.is_anonymous}
                                    onChange={(e) => setField('is_anonymous', e.target.checked)}
                                />
                                <span className="wr-toggle-track" />
                                <span className="wr-toggle-thumb" />
                            </label>
                        </div>
                    </div>

                    {/* Headline */}
                    <div className="wr-section">
                        <h3 className="wr-section-title">Headline</h3>
                        <input
                            type="text"
                            className="wr-headline-input"
                            placeholder="Summarise your experience in one line..."
                            value={form.headline}
                            onChange={(e) => setField('headline', e.target.value)}
                            maxLength={200}
                        />
                    </div>

                    {/* Ratings */}
                    <div className="wr-section">
                        <h3 className="wr-section-title">Ratings</h3>
                        <div className="wr-rating-grid">
                            {RATING_CATEGORIES.map(({ key, label }) => (
                                <div key={key} className="wr-rating-item">
                                    <div className="wr-rating-label">
                                        <span>{label}</span>
                                        <span className="wr-rating-value">{form[key]}</span>
                                    </div>
                                    <input
                                        type="range"
                                        className="wr-rating-slider"
                                        min={1}
                                        max={5}
                                        step={1}
                                        value={form[key]}
                                        onChange={(e) => setField(key, parseInt(e.target.value, 10))}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Pros & Cons */}
                    <div className="wr-section">
                        <h3 className="wr-section-title">Your Experience</h3>
                        <div className="wr-textarea-group">
                            <div className="wr-textarea-label">
                                <span>Pros</span>
                                <span className="wr-textarea-hint">What do you enjoy?</span>
                            </div>
                            <textarea
                                className="wr-textarea"
                                placeholder="Share the positive aspects of working here..."
                                value={form.pros}
                                onChange={(e) => setField('pros', e.target.value)}
                            />
                        </div>
                        <div className="wr-textarea-group">
                            <div className="wr-textarea-label">
                                <span>Cons</span>
                                <span className="wr-textarea-hint">What could improve?</span>
                            </div>
                            <textarea
                                className="wr-textarea"
                                placeholder="Share constructive feedback for improvement..."
                                value={form.cons}
                                onChange={(e) => setField('cons', e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Employment context */}
                    <div className="wr-section">
                        <h3 className="wr-section-title">Employment Context</h3>
                        <div className="wr-field-grid">
                            <div className="wr-field-group">
                                <label className="wr-field-label">Employment Status</label>
                                <select
                                    className="wr-select"
                                    value={form.employment_status}
                                    onChange={(e) => setField('employment_status', e.target.value)}
                                >
                                    <option value="">Select status</option>
                                    {EMPLOYMENT_OPTIONS.map((opt) => (
                                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="wr-field-group">
                                <label className="wr-field-label">Department</label>
                                <input
                                    type="text"
                                    className="wr-input"
                                    placeholder="e.g. Engineering"
                                    value={form.department}
                                    onChange={(e) => setField('department', e.target.value)}
                                />
                            </div>
                            <div className="wr-field-group">
                                <label className="wr-field-label">Job Title</label>
                                <input
                                    type="text"
                                    className="wr-input"
                                    placeholder="e.g. Software Engineer"
                                    value={form.role_title}
                                    onChange={(e) => setField('role_title', e.target.value)}
                                />
                            </div>
                            <div className="wr-field-group">
                                <label className="wr-field-label">Tenure (months)</label>
                                <input
                                    type="number"
                                    className="wr-input"
                                    placeholder="e.g. 24"
                                    min={0}
                                    value={form.tenure_months}
                                    onChange={(e) => setField('tenure_months', e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        className="wr-submit-btn"
                        disabled={submitting || wordCount < 20}
                    >
                        {submitting ? 'Submitting...' : 'Submit Review'}
                    </button>
                </form>

                {/* ── Guidelines Sidebar ─────────────────────── */}
                <aside className="wr-guide-panel">
                    <div className="wr-guide-section">
                        <h4 className="wr-guide-title">Guidelines</h4>
                        <ul className="wr-guide-list">
                            <li>Be honest and constructive</li>
                            <li>Do not include personal identifiers</li>
                            <li>Avoid profanity or discriminatory language</li>
                            <li>Share specific examples when possible</li>
                            <li>Focus on your direct experience</li>
                            <li>Minimum 20 words combined in pros + cons</li>
                        </ul>
                    </div>

                    <div className="wr-guide-section">
                        <h4 className="wr-guide-title">Privacy Notice</h4>
                        <div className="wr-guide-note">
                            Anonymous reviews hide your name, profile picture, and any
                            identifying details from both the company and other users.
                            Your identity is known only to TalentOrbit for moderation
                            and fraud prevention purposes.
                        </div>
                    </div>

                    <div className="wr-guide-section">
                        <h4 className="wr-guide-title">Verification</h4>
                        <div className="wr-guide-note">
                            If your email domain matches the company domain, your review
                            will be automatically marked as "Verified Employee." This badge
                            increases trust without revealing your identity.
                        </div>
                    </div>

                    <div className="wr-guide-section">
                        <h4 className="wr-guide-title">Moderation</h4>
                        <div className="wr-guide-note">
                            All reviews are moderated before publication. Reviews are
                            typically approved within 24-48 hours. Reviews that violate
                            our community guidelines will be rejected with feedback.
                        </div>
                    </div>
                </aside>
            </div>
        </DashboardLayout>
    );
};

export default WriteReview;
