import { useEffect } from 'react';

/**
 * usePageTitle
 * Sets document.title for SEO and browser tab clarity.
 * Automatically appends "— TalentOrbit" suffix.
 */
const usePageTitle = (title) => {
    useEffect(() => {
        const prev = document.title;
        document.title = title ? `${title} — TalentOrbit` : 'TalentOrbit';
        return () => { document.title = prev; };
    }, [title]);
};

export default usePageTitle;
