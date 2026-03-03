import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CertificateVerify.css';

const CertificateVerify = () => {
    const { certificateId } = useParams();
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [inputId, setInputId] = useState(certificateId || '');

    usePageTitle('Verify Certificate', 'Verify the authenticity of a TalentOrbit certificate.');

    const verify = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const { data } = await courseService.verifyCertificate(id);
            setResult(data);
        } catch (err) {
            if (err.response?.status === 404) {
                setError('Certificate not found. Please check the ID and try again.');
            } else {
                setError(getApiErrorMessage(err, 'Verification failed.'));
            }
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (certificateId) verify(certificateId);
        else setLoading(false);
    }, [certificateId, verify]);

    const handleManualVerify = (e) => {
        e.preventDefault();
        verify(inputId.trim());
    };

    const isValid = result?.valid !== false;

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Certificate Verification',
                status: result ? (isValid ? 'Valid ✓' : 'Invalid ✗') : 'Pending',
                info: 'Public Verification Portal',
            }}
            pageTitleLine1="Certificate"
            pageTitleLine2="Verification"
        >
            <div className="cvr-page">
                {/* Manual input */}
                {!certificateId && (
                    <form className="cvr-search-form" onSubmit={handleManualVerify}>
                        <h3>Verify a Certificate</h3>
                        <p>Enter the certificate ID to verify its authenticity.</p>
                        <div className="cvr-search-row">
                            <input
                                type="text"
                                className="cvr-search-input"
                                placeholder="Certificate ID or verification code"
                                value={inputId}
                                onChange={(e) => setInputId(e.target.value)}
                            />
                            <button type="submit" className="cvr-search-btn" disabled={!inputId.trim()}>
                                Verify
                            </button>
                        </div>
                    </form>
                )}

                {loading && (
                    <div className="cvr-skeleton">
                        <Skeleton style={{ width: '100%', maxWidth: '600px', height: '300px', margin: '32px auto', borderRadius: '12px' }} />
                    </div>
                )}

                {error && (
                    <div className="cvr-result cvr-result--invalid">
                        <div className="cvr-result__icon">✗</div>
                        <h2>Verification Failed</h2>
                        <p>{error}</p>
                    </div>
                )}

                {result && !error && (
                    <div className={`cvr-result ${isValid ? 'cvr-result--valid' : 'cvr-result--invalid'}`}>
                        <div className="cvr-result__icon">{isValid ? '✓' : '✗'}</div>
                        <h2>{isValid ? 'Certificate Verified' : 'Invalid Certificate'}</h2>
                        {isValid && (
                            <div className="cvr-result__details">
                                <div className="cvr-detail-row">
                                    <span className="cvr-detail-label">Holder</span>
                                    <span className="cvr-detail-value">{result.user_name || result.holder_name || '—'}</span>
                                </div>
                                <div className="cvr-detail-row">
                                    <span className="cvr-detail-label">Course</span>
                                    <span className="cvr-detail-value">{result.course_title || result.course?.title || '—'}</span>
                                </div>
                                <div className="cvr-detail-row">
                                    <span className="cvr-detail-label">Issued</span>
                                    <span className="cvr-detail-value">
                                        {result.issued_at ? new Date(result.issued_at).toLocaleDateString() : '—'}
                                    </span>
                                </div>
                                <div className="cvr-detail-row">
                                    <span className="cvr-detail-label">Certificate ID</span>
                                    <span className="cvr-detail-value">{result.certificate_id || certificateId}</span>
                                </div>
                                {result.grade && (
                                    <div className="cvr-detail-row">
                                        <span className="cvr-detail-label">Grade</span>
                                        <span className="cvr-detail-value">{result.grade}</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                <div className="cvr-footer">
                    <Link to="/courses" className="cvr-link">Browse Courses</Link>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CertificateVerify;
