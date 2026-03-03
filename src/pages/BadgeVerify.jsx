import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import assessmentService from '../services/assessmentService';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './BadgeVerify.css';

const BadgeVerify = () => {
    const { badgeId } = useParams();
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [inputId, setInputId] = useState(badgeId || '');

    usePageTitle('Verify Badge', 'Verify the authenticity of a TalentOrbit skill badge.');

    const verify = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const { data } = await assessmentService.verifyBadge(id);
            setResult(data);
        } catch (err) {
            if (err.response?.status === 404) {
                setError('Badge not found. Please check the ID and try again.');
            } else {
                setError(getApiErrorMessage(err, 'Badge verification failed.'));
            }
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (badgeId) verify(badgeId);
        else setLoading(false);
    }, [badgeId, verify]);

    const handleManualVerify = (e) => {
        e.preventDefault();
        verify(inputId.trim());
    };

    const isValid = result?.valid !== false;

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Badge Verification',
                status: result ? (isValid ? 'Valid ✓' : 'Invalid ✗') : 'Pending',
                info: 'Public Verification Portal',
            }}
            pageTitleLine1="Badge"
            pageTitleLine2="Verification"
        >
            <div className="bv-page">
                {!badgeId && (
                    <form className="bv-search-form" onSubmit={handleManualVerify}>
                        <h3>Verify a Skill Badge</h3>
                        <p>Enter the badge verification ID to check its authenticity.</p>
                        <div className="bv-search-row">
                            <input
                                type="text"
                                className="bv-search-input"
                                placeholder="Badge ID or verification code"
                                value={inputId}
                                onChange={(e) => setInputId(e.target.value)}
                            />
                            <button type="submit" className="bv-search-btn" disabled={!inputId.trim()}>
                                Verify
                            </button>
                        </div>
                    </form>
                )}

                {loading && (
                    <div className="bv-skeleton">
                        <Skeleton style={{ width: '100%', maxWidth: '500px', height: '300px', margin: '32px auto', borderRadius: '12px' }} />
                    </div>
                )}

                {error && (
                    <div className="bv-result bv-result--invalid">
                        <div className="bv-result__icon">✗</div>
                        <h2>Verification Failed</h2>
                        <p>{error}</p>
                    </div>
                )}

                {result && !error && (
                    <div className={`bv-result ${isValid ? 'bv-result--valid' : 'bv-result--invalid'}`}>
                        <div className="bv-result__icon">{isValid ? '🏅' : '✗'}</div>
                        <h2>{isValid ? 'Badge Verified' : 'Invalid Badge'}</h2>
                        {isValid && (
                            <div className="bv-result__details">
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Holder</span>
                                    <span className="bv-detail-value">{result.holder_name || result.user_name || '—'}</span>
                                </div>
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Badge</span>
                                    <span className="bv-detail-value">{result.badge_name || result.name || result.title || '—'}</span>
                                </div>
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Skill</span>
                                    <span className="bv-detail-value">{result.skill || '—'}</span>
                                </div>
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Level</span>
                                    <span className="bv-detail-value">{result.level || 'Verified'}</span>
                                </div>
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Earned</span>
                                    <span className="bv-detail-value">
                                        {result.earned_at ? new Date(result.earned_at).toLocaleDateString() : '—'}
                                    </span>
                                </div>
                                <div className="bv-detail-row">
                                    <span className="bv-detail-label">Assessment</span>
                                    <span className="bv-detail-value">{result.assessment_title || '—'}</span>
                                </div>
                                {result.score != null && (
                                    <div className="bv-detail-row">
                                        <span className="bv-detail-label">Score</span>
                                        <span className="bv-detail-value">{result.score}%</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                <div className="bv-footer">
                    <Link to="/assessments" className="bv-link">Browse Assessments</Link>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default BadgeVerify;
