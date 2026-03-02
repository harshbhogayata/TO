/**
 * Skeleton — Brutalist content placeholder system.
 *
 * Renders animated block-style shimmer bars matching TalentOrbit's
 * editorial design language (no rounded corners, no gradients).
 *
 * Variants:
 *   <Skeleton />                    — single line (default)
 *   <Skeleton width="60%" />        — partial-width line
 *   <Skeleton height={120} />       — tall block (card placeholder)
 *   <Skeleton.Text lines={4} />     — multi-line paragraph
 *   <Skeleton.Card />               — card-shaped placeholder
 *   <Skeleton.List count={5} />     — repeated row placeholders
 *   <Skeleton.Stat />               — stat card placeholder
 */

const shimmerKeyframes = `
@keyframes sk-shimmer {
    0%   { opacity: 0.08; }
    50%  { opacity: 0.16; }
    100% { opacity: 0.08; }
}
`;

// Inject keyframes once
let injected = false;
function ensureKeyframes() {
    if (injected || typeof document === 'undefined') return;
    const style = document.createElement('style');
    style.textContent = shimmerKeyframes;
    document.head.appendChild(style);
    injected = true;
}

/** Base skeleton bar */
const Skeleton = ({ width = '100%', height = 14, style = {}, className = '' }) => {
    ensureKeyframes();
    return (
        <div
            className={className}
            aria-hidden="true"
            style={{
                width,
                height,
                background: 'var(--text-black, #1a1a1a)',
                opacity: 0.12,
                animation: 'sk-shimmer 1.4s ease-in-out infinite',
                ...style,
            }}
        />
    );
};

/** Multi-line text placeholder */
Skeleton.Text = ({ lines = 3, gap = 10, widths, style = {} }) => {
    const defaultWidths = ['100%', '92%', '78%', '85%', '66%', '94%', '70%', '88%'];
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap, ...style }}>
            {Array.from({ length: lines }, (_, i) => (
                <Skeleton
                    key={i}
                    width={widths?.[i] || defaultWidths[i % defaultWidths.length]}
                    height={12}
                />
            ))}
        </div>
    );
};
Skeleton.Text.displayName = 'Skeleton.Text';

/** Card-shaped placeholder (for job cards, blog cards, etc.) */
Skeleton.Card = ({ style = {} }) => (
    <div style={{
        border: '1px solid var(--border-color, #d4c9b8)',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        ...style,
    }}>
        <Skeleton width="45%" height={10} />
        <Skeleton width="70%" height={18} />
        <Skeleton.Text lines={2} gap={8} />
        <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <Skeleton width={72} height={22} />
            <Skeleton width={56} height={22} />
            <Skeleton width={64} height={22} />
        </div>
    </div>
);
Skeleton.Card.displayName = 'Skeleton.Card';

/** Stat card placeholder */
Skeleton.Stat = ({ style = {} }) => (
    <div style={{
        border: '1px solid var(--border-color, #d4c9b8)',
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        ...style,
    }}>
        <Skeleton width="50%" height={10} />
        <Skeleton width={48} height={28} />
    </div>
);
Skeleton.Stat.displayName = 'Skeleton.Stat';

/** Repeated row list (for job lists, notifications, threads, etc.) */
Skeleton.List = ({ count = 4, gap = 0, style = {} }) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap, ...style }}>
        {Array.from({ length: count }, (_, i) => (
            <div key={i} style={{
                padding: '20px 24px',
                borderBottom: '1px solid var(--border-color, #d4c9b8)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                animationDelay: `${i * 0.1}s`,
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Skeleton width="35%" height={10} style={{ animationDelay: `${i * 0.1}s` }} />
                    <Skeleton width={60} height={10} style={{ animationDelay: `${i * 0.1 + 0.05}s` }} />
                </div>
                <Skeleton width="60%" height={16} style={{ animationDelay: `${i * 0.1 + 0.1}s` }} />
                <Skeleton width="80%" height={11} style={{ animationDelay: `${i * 0.1 + 0.15}s` }} />
            </div>
        ))}
    </div>
);
Skeleton.List.displayName = 'Skeleton.List';

/** Thread / conversation list skeleton */
Skeleton.Threads = ({ count = 4, style = {} }) => (
    <div style={{ display: 'flex', flexDirection: 'column', ...style }}>
        {Array.from({ length: count }, (_, i) => (
            <div key={i} style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--border-color, #d4c9b8)',
                display: 'flex',
                gap: '12px',
                alignItems: 'flex-start',
            }}>
                <Skeleton width={36} height={36} style={{ flexShrink: 0, animationDelay: `${i * 0.12}s` }} />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <Skeleton width="55%" height={12} style={{ animationDelay: `${i * 0.12 + 0.05}s` }} />
                    <Skeleton width="80%" height={10} style={{ animationDelay: `${i * 0.12 + 0.1}s` }} />
                </div>
            </div>
        ))}
    </div>
);
Skeleton.Threads.displayName = 'Skeleton.Threads';

export default Skeleton;
