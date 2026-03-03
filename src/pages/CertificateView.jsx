import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import DashboardLayout from '../layouts/DashboardLayout';
import courseService from '../services/courseService';
import { getApiErrorMessage } from '../services/api';
import usePageTitle from '../hooks/usePageTitle';
import Skeleton from '../components/Skeleton';
import './CertificateView.css';

const CertificateView = () => {
    const { certId } = useParams();
    const [cert, setCert] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const certRef = useRef(null);

    usePageTitle('Certificate', 'View and share your earned certificate.');

    const fetchCert = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await courseService.myCertificates();
            const list = data.results || data;
            const found = list.find((c) => String(c.id) === String(certId));
            if (found) {
                setCert(found);
            } else {
                setError('Certificate not found.');
            }
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load certificate.'));
        } finally {
            setLoading(false);
        }
    }, [certId]);

    useEffect(() => { fetchCert(); }, [fetchCert]);

    const handlePrint = () => {
        window.print();
    };

    const handleShare = () => {
        const url = `${window.location.origin}/certificates/verify/${cert?.certificate_id || cert?.id}`;
        if (navigator.share) {
            navigator.share({ title: 'My TalentOrbit Certificate', url });
        } else {
            navigator.clipboard.writeText(url);
            alert('Verification link copied to clipboard!');
        }
    };

    if (loading) {
        return (
            <DashboardLayout pageTitleLine1="Certificate" pageTitleLine2="View">
                <div className="cv-skeleton">
                    <Skeleton style={{ width: '100%', maxWidth: '700px', height: '500px', margin: '40px auto', borderRadius: '12px' }} />
                </div>
            </DashboardLayout>
        );
    }

    if (error) {
        return (
            <DashboardLayout pageTitleLine1="Certificate" pageTitleLine2="View">
                <div className="cv-error">{error}</div>
            </DashboardLayout>
        );
    }

    return (
        <DashboardLayout
            tapeBarProps={{
                title: 'Certificate of Completion',
                status: 'Verified ✓',
                info: `ID: ${cert?.certificate_id || cert?.id}`,
            }}
            pageTitleLine1="Certificate"
            pageTitleLine2="View"
        >
            <div className="cv-page">
                {/* Certificate display */}
                <div className="cv-certificate" ref={certRef}>
                    <div className="cv-certificate__border">
                        <div className="cv-certificate__inner">
                            <div className="cv-certificate__logo">TalentOrbit</div>
                            <h1 className="cv-certificate__heading">Certificate of Completion</h1>
                            <p className="cv-certificate__subtext">This certifies that</p>
                            <h2 className="cv-certificate__name">{cert?.user_name || cert?.user?.name || '—'}</h2>
                            <p className="cv-certificate__subtext">has successfully completed</p>
                            <h3 className="cv-certificate__course">{cert?.course_title || cert?.course?.title || '—'}</h3>
                            <div className="cv-certificate__details">
                                <span>Issued: {new Date(cert?.issued_at || cert?.created_at).toLocaleDateString()}</span>
                                <span>ID: {cert?.certificate_id || cert?.id}</span>
                            </div>
                            {cert?.grade && (
                                <div className="cv-certificate__grade">Grade: {cert.grade}</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="cv-actions">
                    <button className="cv-action-btn" onClick={handlePrint}>🖨 Print</button>
                    <button className="cv-action-btn" onClick={handleShare}>🔗 Share</button>
                    {cert?.pdf_url && (
                        <a className="cv-action-btn" href={cert.pdf_url} target="_blank" rel="noreferrer">
                            📥 Download PDF
                        </a>
                    )}
                    <Link to="/my-learning" className="cv-action-btn cv-action-btn--secondary">
                        ← Back to My Learning
                    </Link>
                </div>

                {/* Verification info */}
                <div className="cv-verify-info">
                    <p>
                        Verify this certificate:{' '}
                        <Link to={`/certificates/verify/${cert?.certificate_id || cert?.id}`}>
                            {window.location.origin}/certificates/verify/{cert?.certificate_id || cert?.id}
                        </Link>
                    </p>
                </div>
            </div>
        </DashboardLayout>
    );
};

export default CertificateView;
