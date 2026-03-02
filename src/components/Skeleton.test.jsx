import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Skeleton from './Skeleton';

describe('Skeleton', () => {
    it('renders a base skeleton bar', () => {
        const { container } = render(<Skeleton />);
        const el = container.firstChild;
        expect(el).toBeTruthy();
        expect(el.getAttribute('aria-hidden')).toBe('true');
        expect(el.style.width).toBe('100%');
    });

    it('renders with custom width and height', () => {
        const { container } = render(<Skeleton width="60%" height={24} />);
        const el = container.firstChild;
        expect(el.style.width).toBe('60%');
        expect(el.style.height).toBe('24px');
    });
});

describe('Skeleton.Text', () => {
    it('renders the correct number of lines', () => {
        const { container } = render(<Skeleton.Text lines={5} />);
        const bars = container.querySelectorAll('[aria-hidden="true"]');
        expect(bars.length).toBe(5);
    });
});

describe('Skeleton.Card', () => {
    it('renders a card-shaped skeleton', () => {
        const { container } = render(<Skeleton.Card />);
        expect(container.firstChild).toBeTruthy();
        // Should have border styling
        expect(container.firstChild.style.border).toContain('1px solid');
    });
});

describe('Skeleton.List', () => {
    it('renders the correct number of row placeholders', () => {
        const { container } = render(<Skeleton.List count={3} />);
        const rows = container.firstChild.children;
        expect(rows.length).toBe(3);
    });
});

describe('Skeleton.Stat', () => {
    it('renders a stat card skeleton', () => {
        const { container } = render(<Skeleton.Stat />);
        expect(container.firstChild).toBeTruthy();
        const bars = container.querySelectorAll('[aria-hidden="true"]');
        expect(bars.length).toBe(2); // label + value
    });
});
