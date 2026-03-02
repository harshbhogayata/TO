import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { blogService, getApiErrorMessage } from '../services/api';
import { useAuthStore } from '../store/authStore';
import usePageTitle from '../hooks/usePageTitle';
import './Blog.css';

const CATEGORIES = ['All Articles', 'Career Advice', 'Hiring Trends', 'Platform Updates', 'Interviews'];

const Blog = () => {
    const navigate = useNavigate();
    const { isAuthenticated, user } = useAuthStore();
    usePageTitle('Blog', 'Career advice, hiring trends, and industry insights from TalentOrbit. Stay ahead in the talent economy.');
    const [activeCategory, setActiveCategory] = useState('All Articles');
    const [articles, setArticles] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState('');

    const loadArticles = async (pageNum, cat, append = false) => {
        if (!append) setIsLoading(true);
        setLoadingMore(true);
        setError('');
        try {
            const params = { page: pageNum };
            if (cat !== 'All Articles') params.category = cat;

            const { data } = await blogService.listArticles(params);

            if (append) {
                setArticles(prev => [...prev, ...data.results]);
            } else {
                setArticles(data.results);
            }
            setHasMore(!!data.next);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Failed to load articles. Please try again.'));
        } finally {
            setLoadingMore(false);
            setIsLoading(false);
        }
    };

    useEffect(() => {
        setPage(1);
        loadArticles(1, activeCategory, false);
    }, [activeCategory]);

    const handleLoadMore = () => {
        const next = page + 1;
        setPage(next);
        loadArticles(next, activeCategory, true);
    };

    const filtered = articles;

    return (
        <div className="blog-wrapper">
            <header className="blog-main-header">
                <div className="blog-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>TALENT<br />ORBIT</div>
                <nav className="blog-top-nav">
                    <span onClick={() => navigate('/jobs')} style={{ cursor: 'pointer' }}>Jobs</span>
                    <span onClick={() => navigate('/pricing')} style={{ cursor: 'pointer' }}>Pricing</span>
                    <span onClick={() => navigate('/about')} style={{ cursor: 'pointer' }}>About</span>
                    <span className="blog-active-nav">Resources</span>
                </nav>
                <div className="blog-header-actions">
                    {isAuthenticated ? (
                        <button className="blog-btn-solid" onClick={() => {
                            const dashMap = { COMPANY: '/company', ADMIN: '/admin' };
                            navigate(dashMap[user?.role] || '/user');
                        }}>Dashboard</button>
                    ) : (
                        <>
                            <button className="blog-btn-outline" onClick={() => navigate('/auth')}>Login</button>
                            <button className="blog-btn-solid" onClick={() => navigate('/register/user')}>Register</button>
                        </>
                    )}
                </div>
            </header>

            <main className="blog-content">
                <section className="blog-hero">
                    <div className="blog-hero-content">
                        <div className="blog-post-meta">
                            <span className="blog-category">Industry Insights</span>
                            <span className="blog-date">Featured</span>
                        </div>
                        <h1 className="blog-hero-title">The Future of Creative Technical Portfolios</h1>
                        <p className="blog-hero-excerpt">How motion designers and creative coders are redefining the resume in the era of AI and algorithmic curation.</p>
                        <div className="blog-author-block">
                            <div className="blog-author-avatar"></div>
                            <div className="blog-author-info">
                                <span className="blog-author-name">Dr. Sarah Jenkins</span>
                                <span className="blog-author-role">Head of Research • TalentOrbit</span>
                            </div>
                        </div>
                    </div>
                    <div className="blog-hero-image-container">
                        <img loading="lazy" src="https://images.unsplash.com/photo-1542744173-8e7e53415bb0?q=80&w=1400&auto=format&fit=crop" className="blog-hero-img" alt="Creative technical portfolios" />
                    </div>
                </section>

                <div className="blog-category-nav">
                    {CATEGORIES.map(cat => (
                        <button
                            key={cat}
                            className={`blog-cat-btn ${activeCategory === cat ? 'active' : ''}`}
                            onClick={() => setActiveCategory(cat)}
                        >
                            {cat}
                        </button>
                    ))}
                </div>

                <section className="blog-grid">
                    {error && (
                        <div style={{ padding: '40px', fontSize: '11px', color: '#b00', textTransform: 'uppercase', fontFamily: 'var(--font-sans)' }}>
                            {error}
                        </div>
                    )}
                    {isLoading && !error && (
                        <div style={{ padding: '40px', fontSize: '11px', opacity: 0.5, textTransform: 'uppercase', fontFamily: 'var(--font-sans)' }}>
                            Loading articles...
                        </div>
                    )}
                    {!isLoading && !error && filtered.length === 0 && (
                        <div style={{ padding: '40px', fontSize: '11px', opacity: 0.4, textTransform: 'uppercase', fontFamily: 'var(--font-sans)' }}>
                            No articles in this category yet.
                        </div>
                    )}
                    {filtered.map(article => (
                        <article key={article.id} className="blog-card">
                            <img loading="lazy" src={article.img} className="blog-card-img" alt={article.alt} />
                            <div className="blog-card-content">
                                <div className="blog-post-meta">
                                    <span className="blog-category">{article.category}</span>
                                    <span className="blog-read-time">{article.readTime}</span>
                                </div>
                                <h2 className="blog-card-title">{article.title}</h2>
                                <p className="blog-card-excerpt">{article.excerpt}</p>
                                <div className="blog-card-footer">
                                    <span className="blog-author-small">By {article.author}</span>
                                    <span className="blog-date">{article.date}</span>
                                </div>
                            </div>
                        </article>
                    ))}
                </section>

                {hasMore && (
                    <div className="blog-load-more">
                        <button
                            className="blog-btn-outline"
                            onClick={handleLoadMore}
                            disabled={loadingMore}
                            style={{ opacity: loadingMore ? 0.6 : 1 }}
                        >
                            {loadingMore ? 'Retrieving Archives...' : 'Load Archives'}
                        </button>
                        <div className="blog-tape-line"></div>
                    </div>
                )}
            </main>

            <footer className="blog-footer">
                <div className="blog-footer-grid">
                    <div>
                        <div className="blog-logo" style={{ fontSize: '24px' }}>TALENT<br />ORBIT</div>
                        <p style={{ paddingTop: '20px', fontSize: '12px', opacity: 0.6 }}>© {new Date().getFullYear()} TalentOrbit Inc.<br />All rights reserved.</p>
                    </div>
                    <div>
                        <h4 className="blog-footer-heading">Product</h4>
                        <ul className="blog-footer-list">
                            <li onClick={() => navigate('/jobs')}>Job Board</li>
                            <li>Quiz System</li>
                            <li onClick={() => navigate('/pricing')}>Pricing</li>
                        </ul>
                    </div>
                    <div>
                        <h4 className="blog-footer-heading">Company</h4>
                        <ul className="blog-footer-list">
                            <li onClick={() => navigate('/about')}>About Us</li>
                            <li onClick={() => navigate('/blog')}>Resources</li>
                            <li onClick={() => navigate('/support')}>Contact</li>
                        </ul>
                    </div>
                    <div>
                        <h4 className="blog-footer-heading">Legal</h4>
                        <ul className="blog-footer-list">
                            <li onClick={() => navigate('/terms')}>Terms of Service</li>
                            <li onClick={() => navigate('/privacy')}>Privacy Policy</li>
                            <li>Cookie Settings</li>
                        </ul>
                    </div>
                </div>
            </footer>
        </div>
    );
};

export default Blog;
