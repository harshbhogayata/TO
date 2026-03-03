import { useState, useEffect, useCallback } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import Skeleton from '../components/Skeleton';
import { intelligenceService, authService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../contexts/ToastContext';
import usePageTitle from '../hooks/usePageTitle';
import './SkillTaxonomy.css';

const PROFICIENCY_LABELS = ['Foundational', 'Professional', 'Architect'];

const SkillTaxonomy = () => {
    const { user } = useAuthStore();
    const { addToast } = useToast();
    usePageTitle('Skill Browser', 'Explore the master skill taxonomy and add skills to your profile.');

    const [categories, setCategories] = useState([]);
    const [selectedRoot, setSelectedRoot] = useState(null);
    const [subcategories, setSubcategories] = useState([]);
    const [selectedSub, setSelectedSub] = useState(null);
    const [skillDetail, setSkillDetail] = useState(null);
    const [activeProfLevel, setActiveProfLevel] = useState(1);
    const [addedToProfile, setAddedToProfile] = useState(false);
    const [adding, setAdding] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [subLoading, setSubLoading] = useState(false);
    const [detailLoading, setDetailLoading] = useState(false);
    const [totalSkills, setTotalSkills] = useState(0);

    // Load root categories on mount
    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await intelligenceService.getSkillTaxonomy({ parent: 'root' });
                const cats = data?.results || data || [];
                setCategories(cats);
                setTotalSkills(data?.count || cats.length);

                // Auto-select first category
                if (cats.length > 0) {
                    handleRootSelect(cats[0]);
                }
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load skill taxonomy.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleRootSelect = useCallback(async (category) => {
        setSelectedRoot(category);
        setSelectedSub(null);
        setSkillDetail(null);
        setAddedToProfile(false);

        // Use embedded children if available (avoids extra API call)
        // Serializer embeds children as [{id, name, category}]
        if (category.children?.length > 0) {
            setSubcategories(category.children);
            handleSubSelect(category.children[0]);
            return;
        }

        // Fetch children from API when not embedded
        setSubLoading(true);
        try {
            const { data } = await intelligenceService.getSkillTaxonomy({
                parent: category.id,
            });
            const subs = data?.results || data || [];
            setSubcategories(subs);
            if (subs.length > 0) handleSubSelect(subs[0]);
        } catch {
            setSubcategories([]);
        } finally {
            setSubLoading(false);
        }
    }, []);

    const handleSubSelect = useCallback(async (sub) => {
        setSelectedSub(sub);
        setActiveProfLevel(1);
        setAddedToProfile(false);

        // If sub is a full serialized object (from API fetch), use directly
        if (sub.proficiency_levels !== undefined || sub.related !== undefined) {
            setSkillDetail(sub);
            return;
        }

        // Otherwise it's a simplified child ({id, name, category}) — fetch full detail
        setDetailLoading(true);
        try {
            // Fetch all children of the same parent + search by exact name for precision
            const { data } = await intelligenceService.getSkillTaxonomy(
                sub.id
                    ? { parent: sub.id, page_size: 1 } // If it has children, fetch itself via parent filter won't work — use search
                    : { search: sub.name },
            );
            // The sub.id fetch via search as fallback
            let results = data?.results || data || [];
            // If fetching by parent returned children (not the skill itself), search by name instead
            if (sub.id && !results.find(r => r.id === sub.id)) {
                const { data: searchData } = await intelligenceService.getSkillTaxonomy({
                    search: sub.canonical_name || sub.name,
                });
                results = searchData?.results || searchData || [];
            }
            const match = results.find(r => r.id === sub.id) || results[0] || sub;
            setSkillDetail(match);
        } catch {
            setSkillDetail({
                canonical_name: sub.canonical_name || sub.name,
                category: sub.category || '',
                proficiency_levels: PROFICIENCY_LABELS,
                related: [],
            });
        } finally {
            setDetailLoading(false);
        }
    }, []);

    const handleAddToProfile = async () => {
        if (!skillDetail || adding) return;
        setAdding(true);

        const skillName = skillDetail.canonical_name || skillDetail.name || selectedSub?.canonical_name || selectedSub?.name;
        if (!skillName) {
            setAdding(false);
            return;
        }

        try {
            // Get current profile to merge skills
            const { data: meData } = await authService.getMe();
            const currentSkills = meData?.profile?.skills || meData?.skills || [];
            const skillSet = new Set(currentSkills.map(s => (typeof s === 'string' ? s : s.name || s).toLowerCase()));

            if (!skillSet.has(skillName.toLowerCase())) {
                const updatedSkills = [...currentSkills, skillName];
                await authService.updateTalentProfile({ skills: JSON.stringify(updatedSkills) });
                addToast(`"${skillName}" added to your profile.`, 'success');
            } else {
                addToast(`"${skillName}" is already in your profile.`, 'info');
            }

            setAddedToProfile(true);
            setTimeout(() => setAddedToProfile(false), 2500);
        } catch (err) {
            addToast(getApiErrorMessage(err, 'Failed to add skill to profile.'), 'error');
        } finally {
            setAdding(false);
        }
    };

    const formatCount = (n) => {
        if (n == null) return '';
        const num = Number(n);
        if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
        return String(num);
    };

    // Build related skill nodes with positions
    const getRelatedNodes = () => {
        const related = skillDetail?.related || skillDetail?.related_skills || [];
        if (related.length === 0) {
            const name = skillDetail?.canonical_name || skillDetail?.name || selectedSub?.canonical_name || selectedSub?.name || 'Skill';
            return [
                { label: 'Concept A', style: { top: '20%', left: '10%' } },
                { label: name, style: { top: '50%', left: '40%', background: '#222' } },
                { label: 'Concept B', style: { top: '15%', right: '15%' } },
                { label: 'Concept C', style: { bottom: '25%', left: '20%' } },
                { label: 'Concept D', style: { bottom: '10%', right: '10%' } },
            ];
        }
        const positions = [
            { top: '20%', left: '10%' },
            { top: '50%', left: '40%', background: '#222' },
            { top: '15%', right: '15%' },
            { bottom: '25%', left: '20%' },
            { bottom: '10%', right: '10%' },
        ];
        return related.slice(0, 5).map((node, i) => ({
            label: typeof node === 'string' ? node : node.label || node.name,
            style: node.position || node.style || positions[i] || positions[0],
        }));
    };

    const isTalent = user?.role === 'TALENT';

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit // Skill Taxonomy",
                status: `Master Taxonomy Index: Updated ${new Date().toLocaleDateString('en-US', { month: '2-digit', year: '2-digit' })}`,
                info: "Status: Database Synced"
            }}
            pageTitleLine1="Skill"
            pageTitleLine2="Browser"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block">
                        <h3>Total Skills</h3>
                        <p>{totalSkills > 0 ? `${formatCount(totalSkills)} Entries` : '—'}</p>
                    </div>
                </div>
            }
        >
            {isLoading ? (
                <div style={{ display: 'flex', flex: 1, gap: '1px' }}>
                    <div style={{ width: '280px', borderRight: '1px solid var(--border-color)' }}>
                        <Skeleton.List count={6} />
                    </div>
                    <div style={{ width: '320px', borderRight: '1px solid var(--border-color)' }}>
                        <Skeleton.List count={5} />
                    </div>
                    <div style={{ flex: 1, padding: '40px' }}>
                        <Skeleton width="40%" height={12} />
                        <Skeleton width="60%" height={40} style={{ marginTop: '16px' }} />
                        <Skeleton.Text lines={4} style={{ marginTop: '24px' }} />
                    </div>
                </div>
            ) : (
                <div className="st-explorer">
                    {/* ── Root Categories Column ── */}
                    <div className="st-column">
                        <div className="st-column-header">Root Categories</div>
                        {categories.map((cat) => {
                            const isSelected = selectedRoot?.id === cat.id;
                            return (
                                <div
                                    key={cat.id || cat.canonical_name}
                                    className={isSelected ? 'st-list-item--selected' : 'st-list-item'}
                                    onClick={() => handleRootSelect(cat)}
                                >
                                    <span className="st-item-name">{cat.canonical_name || cat.name}</span>
                                    <span className="st-item-count">{formatCount(cat.children?.length || cat.usage_count)}</span>
                                </div>
                            );
                        })}
                        {categories.length === 0 && (
                            <div className="st-empty">No categories found.</div>
                        )}
                    </div>

                    {/* ── Subcategories Column ── */}
                    <div className="st-column">
                        <div className="st-column-header">
                            {selectedRoot?.canonical_name || selectedRoot?.name || 'Category'} / Subcategories
                        </div>
                        {subLoading ? (
                            <Skeleton.List count={5} />
                        ) : (
                            subcategories.map((sub) => {
                                const isSelected = selectedSub?.id === sub.id;
                                return (
                                    <div
                                        key={sub.id || sub.canonical_name || sub.name}
                                        className={isSelected ? 'st-list-item--selected' : 'st-list-item'}
                                        onClick={() => handleSubSelect(sub)}
                                    >
                                        <span className="st-item-name">{sub.canonical_name || sub.name}</span>
                                        <span className="st-item-count">{formatCount(sub.children?.length || sub.usage_count)}</span>
                                    </div>
                                );
                            })
                        )}
                        {!subLoading && subcategories.length === 0 && selectedRoot && (
                            <div className="st-empty">No subcategories.</div>
                        )}
                    </div>

                    {/* ── Skill Detail Pane ── */}
                    <div className="st-detail-pane">
                        {detailLoading ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                <Skeleton width="50%" height={12} />
                                <Skeleton width="70%" height={40} />
                                <Skeleton.Text lines={3} style={{ marginTop: '16px' }} />
                            </div>
                        ) : !skillDetail ? (
                            <div className="st-detail-empty">
                                <h3>Select a Skill</h3>
                                <p>Choose a category and subcategory to view details</p>
                            </div>
                        ) : (
                            <>
                                <div className="st-detail-header">
                                    <span className="st-category-path">
                                        {skillDetail.category
                                            || `${selectedRoot?.canonical_name || selectedRoot?.name || ''} > ${selectedSub?.canonical_name || selectedSub?.name || ''}`}
                                    </span>
                                    <h2 className="st-detail-title">
                                        {skillDetail.canonical_name || skillDetail.name || selectedSub?.canonical_name || selectedSub?.name}
                                    </h2>
                                </div>

                                {/* Proficiency Levels */}
                                <span className="st-section-title">Defined Proficiency Levels</span>
                                <div className="st-prof-grid">
                                    {(skillDetail.proficiency_levels || PROFICIENCY_LABELS).map((label, idx) => {
                                        const levelLabel = typeof label === 'string' ? label : label.name || PROFICIENCY_LABELS[idx];
                                        return (
                                            <div
                                                key={idx}
                                                className={activeProfLevel === idx ? 'st-prof-level--active' : 'st-prof-level'}
                                                onClick={() => setActiveProfLevel(idx)}
                                            >
                                                <span className="st-prof-num">L{idx + 1}</span>
                                                <span className="st-prof-label">{levelLabel}</span>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Related Skill Graph */}
                                <span className="st-section-title">Related Skill Graph</span>
                                <div className="st-graph">
                                    {getRelatedNodes().map((node, idx) => (
                                        <div key={idx} className="st-node" style={node.style}>
                                            {node.label}
                                        </div>
                                    ))}
                                </div>

                                {/* Add to Profile Button — only for TALENT users */}
                                {isTalent && (
                                    <>
                                        <button
                                            className={`st-add-btn${addedToProfile ? ' st-add-btn--success' : ''}`}
                                            onClick={handleAddToProfile}
                                            disabled={adding || addedToProfile}
                                        >
                                            <span>
                                                {addedToProfile
                                                    ? 'Added to Profile!'
                                                    : adding
                                                        ? 'Adding...'
                                                        : 'Add to Candidate Profile'}
                                            </span>
                                            <span>{addedToProfile ? '✓' : '→'}</span>
                                        </button>
                                        <div className="st-add-note">
                                            * Adding this skill will automatically trigger a re-calculation of current match scores.
                                        </div>
                                    </>
                                )}
                            </>
                        )}
                    </div>
                </div>
            )}
        </DashboardLayout>
    );
};

export default SkillTaxonomy;
