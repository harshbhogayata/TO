import { useState, useEffect, useRef } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import Skeleton from '../components/Skeleton';
import { intelligenceService, getApiErrorMessage } from '../services/api';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './ResumeParser.css';

const ResumeParser = () => {
    const { addToast } = useToast();
    const fileInputRef = useRef(null);
    usePageTitle('Resume Parser', 'Upload and parse resumes with AI-powered NLP extraction.');

    const [file, setFile] = useState(null);
    const [parsing, setParsing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [parsed, setParsed] = useState(null);
    const [rawText, setRawText] = useState('');
    const [confirmed, setConfirmed] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [dragOver, setDragOver] = useState(false);

    // Load previously parsed resume on mount
    useEffect(() => {
        const loadExisting = async () => {
            try {
                const { data } = await intelligenceService.getParsedResume();
                if (data && (data.parsed_skills?.length || data.parsed_experience?.length)) {
                    setParsed(data);
                    setRawText(data.raw_text || data.generated_bio || `[Resume parsed on ${data.parsed_at || 'unknown date'}]`);
                    setProgress(100);
                }
            } catch {
                // No existing parsed resume â€” that's fine
            }
        };
        loadExisting();
    }, []);

    // Simulate progress animation during parsing
    useEffect(() => {
        if (!parsing) return;
        const interval = setInterval(() => {
            setProgress(prev => prev >= 92 ? 92 : prev + Math.random() * 8);
        }, 400);
        return () => clearInterval(interval);
    }, [parsing]);

    const handleFileDrop = (e) => {
        e.preventDefault();
        setDragOver(false);
        const dropped = e.dataTransfer?.files?.[0];
        if (dropped) handleFileSelect(dropped);
    };

    const handleFileSelect = async (selectedFile) => {
        if (!selectedFile) return;

        const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
        if (!allowed.includes(selectedFile.type) && !selectedFile.name.match(/\.(pdf|docx|txt)$/i)) {
            addToast('Please upload a PDF, DOCX, or TXT file.', 'error');
            return;
        }
        if (selectedFile.size > 10 * 1024 * 1024) {
            addToast('File must be under 10MB.', 'error');
            return;
        }

        setFile(selectedFile);
        setParsing(true);
        setProgress(5);
        setParsed(null);
        setRawText('');
        setConfirmed(false);

        try {
            const formData = new FormData();
            formData.append('resume', selectedFile);

            const { data } = await intelligenceService.parseResumeAI(formData);
            setParsed(data);
            setRawText(data.raw_text || data.generated_bio || `[Parsed from ${selectedFile.name}]`);
            setProgress(100);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Resume parsing failed.'), 'error');
            setProgress(0);
        } finally {
            setParsing(false);
        }
    };

    const handleConfirm = async () => {
        if (!parsed || confirming) return;
        setConfirming(true);
        try {
            await intelligenceService.applyParsedResume({
                skills: (parsed.parsed_skills || []).map(s =>
                    typeof s === 'string' ? s : s.canonical_name || s.name || String(s)
                ),
                bio: parsed.generated_bio || '',
            });
            setConfirmed(true);
            addToast('Profile updated with parsed resume data.', 'success');
            setTimeout(() => setConfirmed(false), 3000);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to apply resume data.'), 'error');
        } finally {
            setConfirming(false);
        }
    };

    // Backend stores confidence_score as FloatField 0.0â€“1.0
    const confidence = parsed?.confidence_score != null
        ? Math.min(Math.round(parsed.confidence_score * 100), 100)
        : null;

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // NLP Engine",
                status: "Data Pipeline: OCR + NLP Parsing",
                info: parsing ? 'Status: Processing Active' : progress === 100 ? 'Status: Parse Complete' : 'Status: Awaiting Input'
            }}
            pageTitleLine1="Profile"
            pageTitleLine2="Parser"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Ingestion Engine</h3>
                        <p>V3-ALPHABET-9</p>
                    </div>
                </div>
            }
        >
            <div className="rp-grid">
                {/* â”€â”€ Left: Upload Zone â”€â”€ */}
                <div className="rp-upload-zone">
                    <span className="rp-section-label">Resume Source Ingestion</span>

                    <div
                        className={`rp-drop-box${dragOver ? ' rp-drop-box--active' : ''}`}
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleFileDrop}
                        role="button"
                        tabIndex={0}
                        aria-label="Upload resume file"
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
                    >
                        <h3>Drag &amp; Drop Resume</h3>
                        <p>PDF, DOCX OR TXT (MAX 10MB)</p>
                        {file && <p style={{ fontWeight: 600, fontSize: '11px' }}>{file.name}</p>}

                        {(parsing || progress > 0) && (
                            <div style={{ marginTop: '10px', width: '100%' }}>
                                <div className="rp-progress-info">
                                    <span>{parsing ? 'PARSING ELEMENTS...' : 'PARSE COMPLETE'}</span>
                                    <span>{Math.round(progress)}%</span>
                                </div>
                                <div className="rp-progress-bar">
                                    <div className="rp-progress-fill" style={{ width: `${progress}%` }} />
                                </div>
                            </div>
                        )}
                    </div>

                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.docx,.txt"
                        style={{ display: 'none' }}
                        onChange={(e) => handleFileSelect(e.target.files?.[0])}
                    />

                    {/* Raw Data Stream */}
                    <div>
                        <div className="rp-raw-header">
                            <span className="rp-section-label" style={{ marginBottom: 0, border: 'none' }}>Raw CV Data Stream</span>
                            <span className="rp-status-badge">
                                {parsing ? 'â— Capturing' : rawText ? 'â— Complete' : 'â— Idle'}
                            </span>
                        </div>
                        <div className="rp-raw-data">
                            {rawText || (parsing
                                ? 'Processing document...'
                                : 'Upload a resume to see raw extracted text here.')}
                        </div>
                    </div>
                </div>

                {/* â”€â”€ Right: Structured View â”€â”€ */}
                <div className="rp-structured">
                    {!parsed && !parsing ? (
                        <div className="rp-empty-structured">
                            <h3>Awaiting Input</h3>
                            <p>Upload a resume to extract structured profile data</p>
                        </div>
                    ) : parsing && !parsed ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            <Skeleton width="40%" height={10} />
                            <Skeleton width="70%" height={32} />
                            <Skeleton.Text lines={3} />
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <Skeleton width={80} height={24} />
                                <Skeleton width={80} height={24} />
                                <Skeleton width={80} height={24} />
                            </div>
                            <Skeleton.Text lines={4} />
                        </div>
                    ) : (
                        <>
                            {/* Extracted Metadata */}
                            <div>
                                <span className="rp-section-label">Extracted Profile Metadata</span>
                                <div className="rp-meta-tag">Entity: Person</div>
                                <h2 className="rp-extracted-name">
                                    {parsed?.contact_info?.name || parsed?.contact_info?.email || 'Candidate'}
                                </h2>
                                <p className="rp-extracted-title">
                                    {parsed?.generated_bio || (parsed?.total_experience_years
                                        ? `${parsed.total_experience_years} years experience`
                                        : 'Profile analysis complete')}
                                </p>
                            </div>

                            {/* Skills */}
                            {parsed?.parsed_skills?.length > 0 && (
                                <div>
                                    <span className="rp-section-label">
                                        Identified Skills{confidence ? ` (NLP Confidence ${confidence}%)` : ''}
                                    </span>
                                    <div className="rp-skill-tags">
                                        {parsed.parsed_skills.map((skill, i) => (
                                            <span key={i} className="rp-skill-tag">
                                                {typeof skill === 'string' ? skill : skill.canonical_name || skill.name || String(skill)}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Work History */}
                            {parsed?.parsed_experience?.length > 0 && (
                                <div>
                                    <span className="rp-section-label">Work History Timeline</span>
                                    <div className="rp-timeline">
                                        {parsed.parsed_experience.map((exp, i) => (
                                            <div key={i} className="rp-timeline-item">
                                                <div className="rp-timeline-dot" />
                                                <h4 className="rp-timeline-company">
                                                    {exp.company || 'Company'}
                                                </h4>
                                                <p className="rp-timeline-role">
                                                    {[exp.title, exp.start_date && exp.end_date ? `${exp.start_date} â€“ ${exp.end_date}` : null, exp.duration_months ? `${exp.duration_months}mo` : null].filter(Boolean).join(' â€¢ ')}
                                                </p>
                                                {exp.description && (
                                                    <p className="rp-timeline-highlight">
                                                        "{exp.description.slice(0, 200)}"
                                                    </p>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Education */}
                            {parsed?.parsed_education?.length > 0 && (
                                <div>
                                    <span className="rp-section-label">Education</span>
                                    {parsed.parsed_education.map((edu, i) => (
                                        <p key={i} style={{ fontSize: '13px', marginBottom: '4px' }}>
                                            <strong>{edu.institution || 'Institution'}</strong>
                                            {edu.degree && ` â€” ${edu.degree}`}
                                            {edu.field && ` in ${edu.field}`}
                                            {edu.graduation_year && ` (${edu.graduation_year})`}
                                        </p>
                                    ))}
                                </div>
                            )}

                            {/* Confirm Button */}
                            <div style={{ marginTop: 'auto' }}>
                                <button
                                    className={`rp-confirm-btn${confirmed ? ' rp-confirm-btn--success' : ''}`}
                                    onClick={handleConfirm}
                                    disabled={confirming || confirmed}
                                >
                                    {confirmed ? 'âœ“ Mapped to Database' : confirming ? 'Processing...' : 'Confirm & Map to Database'}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </DashboardLayout>
    );
};

export default ResumeParser;




