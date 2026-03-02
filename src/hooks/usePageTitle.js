import { useEffect } from 'react';

/**
 * usePageTitle
 * Sets document.title + meta description + Open Graph tags for SEO.
 * Automatically appends "— TalentOrbit" suffix to page title.
 *
 * @param {string} title - Page title (e.g. "Job Board")
 * @param {string} [description] - Meta description for SEO (max ~160 chars)
 */
const usePageTitle = (title, description) => {
    useEffect(() => {
        const prev = document.title;
        document.title = title ? `${title} — TalentOrbit` : 'TalentOrbit';

        // Meta description
        if (description) {
            let meta = document.querySelector('meta[name="description"]');
            const prevDesc = meta?.getAttribute('content') || '';
            if (meta) {
                meta.setAttribute('content', description);
            } else {
                meta = document.createElement('meta');
                meta.name = 'description';
                meta.content = description;
                document.head.appendChild(meta);
            }

            // Open Graph
            const ogTags = {
                'og:title': document.title,
                'og:description': description,
                'og:type': 'website',
                'og:site_name': 'TalentOrbit',
            };
            const prevOg = {};
            Object.entries(ogTags).forEach(([prop, content]) => {
                let el = document.querySelector(`meta[property="${prop}"]`);
                if (el) {
                    prevOg[prop] = el.getAttribute('content');
                    el.setAttribute('content', content);
                } else {
                    el = document.createElement('meta');
                    el.setAttribute('property', prop);
                    el.content = content;
                    document.head.appendChild(el);
                    prevOg[prop] = null;
                }
            });

            return () => {
                document.title = prev;
                if (meta) meta.setAttribute('content', prevDesc);
                Object.entries(prevOg).forEach(([prop, val]) => {
                    const el = document.querySelector(`meta[property="${prop}"]`);
                    if (el && val !== null) el.setAttribute('content', val);
                    else if (el && val === null) el.remove();
                });
            };
        }

        return () => { document.title = prev; };
    }, [title, description]);
};

export default usePageTitle;
