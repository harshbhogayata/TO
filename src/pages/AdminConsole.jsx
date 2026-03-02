import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import DashboardLayout from '../layouts/DashboardLayout';
import { adminService, getApiErrorMessage } from '../services/api';
import { Play } from 'lucide-react';
import usePageTitle from '../hooks/usePageTitle';
import './AdminConsole.css';

const AdminConsole = () => {
    const { addToast } = useToast();
    usePageTitle('Admin Console', 'Platform administration — manage users, jobs, and system health.');
    const [stats, setStats] = useState(null);
    const [users, setUsers] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [tab, setTab] = useState('users');
    const [isLoading, setIsLoading] = useState(true);
    const [search, setSearch] = useState('');

    useEffect(() => {
        const load = async () => {
            try {
                const [statsRes, usersRes, jobsRes] = await Promise.all([
                    adminService.stats(),
                    adminService.listUsers(),
                    adminService.listJobs(),
                ]);
                setStats(statsRes.data);
                setUsers(usersRes.data.results || usersRes.data);
                setJobs(jobsRes.data.results || jobsRes.data);
            } catch (err) {
                addToast(getApiErrorMessage(err, 'Failed to load admin data.'), 'error');
            } finally {
                setIsLoading(false);
            }
        };
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleVerify = async (id) => {
        try {
            await adminService.verifyUser(id);
            setUsers(prev => prev.map(u => u.id === id ? { ...u, is_verified: true } : u));
        } catch (err) { addToast(getApiErrorMessage(err, 'Verify failed.'), 'error'); }
    };

    const handleDeactivate = async (id) => {
        if (!window.confirm('Deactivate this user?')) return;
        try {
            await adminService.deactivateUser(id);
            setUsers(prev => prev.filter(u => u.id !== id));
        } catch (err) { addToast(getApiErrorMessage(err, 'Deactivate failed.'), 'error'); }
    };

    const handleToggleJob = async (id) => {
        try {
            const { data } = await adminService.toggleJob(id);
            setJobs(prev => prev.map(j => j.id === id ? { ...j, status: data.status } : j));
        } catch (err) { addToast(getApiErrorMessage(err, 'Toggle failed.'), 'error'); }
    };

    const searchUsers = async () => {
        try {
            const { data } = await adminService.listUsers({ search });
            setUsers(data.results || data);
        } catch (err) { addToast(getApiErrorMessage(err, 'Search failed.'), 'error'); }
    };

    // Client-side filter removed — searchUsers() handles server-side filtering.
    // When search is cleared, reload full list.
    const handleSearchChange = (e) => {
        setSearch(e.target.value);
        if (!e.target.value) {
            adminService.listUsers().then(({ data }) => setUsers(data.results || data)).catch((err) => addToast(getApiErrorMessage(err, 'Failed to load users.'), 'error'));
        }
    };

    return (
        <DashboardLayout
            tapeBarProps={{
                title: "TalentOrbit Admin Console v2.1",
                status: isLoading ? "Loading..." : `${stats?.talent_count ?? 0} Talent / ${stats?.company_count ?? 0} Companies`,
                info: `Open Roles: ${stats?.open_jobs ?? '—'} / Applications: ${stats?.total_applications ?? '—'}`
            }}
            pageTitleLine1="Admin"
            pageTitleLine2="Console"
            headerRightContent={
                <div className="header-stats">
                    <div className="stat-block"><h3>Talent Users</h3><p>{isLoading ? '—' : stats?.talent_count}</p></div>
                    <div className="stat-block"><h3>Companies</h3><p>{isLoading ? '—' : stats?.company_count}</p></div>
                    <div className="stat-block"><h3>Open Jobs</h3><p>{isLoading ? '—' : stats?.open_jobs}</p></div>
                    <div className="stat-block"><h3>Applications</h3><p>{isLoading ? '—' : stats?.total_applications}</p></div>
                </div>
            }
        >
            <div className="admin-layout">
                {/* Tab Nav */}
                <div className="admin-tabs">
                    {['users', 'jobs'].map(t => (
                        <button
                            key={t}
                            className={`admin-tab ${tab === t ? 'active' : ''}`}
                            onClick={() => setTab(t)}
                        >
                            {t === 'users' ? 'User Management' : 'Job Listings'}
                        </button>
                    ))}
                </div>

                {tab === 'users' && (
                    <div className="admin-panel">
                        <div className="list-header">
                            <h2>All Users</h2>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <input
                                    type="text"
                                    placeholder="Search..."
                                    value={search}
                                    onChange={handleSearchChange}
                                    onKeyDown={e => e.key === 'Enter' && searchUsers()}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', background: 'transparent', fontFamily: 'var(--font-sans)', fontSize: '11px' }}
                                />
                                <button className="btn-outline" onClick={searchUsers}>Search</button>
                            </div>
                        </div>

                        {isLoading && <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>Loading...</div>}

                        {users.map(u => (
                            <div key={u.id} className="data-row">
                                <div className="row-info">
                                    <span className="row-title">{u.full_name || u.email}</span>
                                    <span className="row-meta">{u.email} • {u.role} {u.is_verified ? '✓ Verified' : '○ Unverified'}</span>
                                </div>
                                <div style={{ display: 'flex', gap: '6px' }}>
                                    {!u.is_verified && (
                                        <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px' }} onClick={() => handleVerify(u.id)}>Verify</button>
                                    )}
                                    <button className="btn-outline" style={{ padding: '6px 10px', fontSize: '10px', color: '#900', borderColor: '#900' }} onClick={() => handleDeactivate(u.id)}>Deactivate</button>
                                </div>
                            </div>
                        ))}

                        {!isLoading && users.length === 0 && (
                            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>No users found.</div>
                        )}
                    </div>
                )}

                {tab === 'jobs' && (
                    <div className="admin-panel">
                        <div className="list-header"><h2>All Listings</h2></div>

                        {isLoading && <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>Loading...</div>}

                        {jobs.map(j => (
                            <div key={j.id} className="data-row">
                                <div className="row-info">
                                    <span className="row-title">{j.title} <span className="badge" style={{ marginLeft: '8px', fontSize: '9px' }}>{j.status?.toUpperCase()}</span></span>
                                    <span className="row-meta">{j.company_name} • {j.work_mode} • {j.application_count} applications</span>
                                </div>
                                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                    <Play size={12} style={{ opacity: 0.5 }} />
                                    <button
                                        className="btn-outline"
                                        style={{ padding: '6px 10px', fontSize: '10px', color: j.status === 'open' ? '#900' : '#060', borderColor: j.status === 'open' ? '#900' : '#060' }}
                                        onClick={() => handleToggleJob(j.id)}
                                    >
                                        {j.status === 'open' ? 'Close' : 'Reopen'}
                                    </button>
                                </div>
                            </div>
                        ))}

                        {!isLoading && jobs.length === 0 && (
                            <div style={{ padding: '32px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase' }}>No jobs found.</div>
                        )}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
};

export default AdminConsole;
