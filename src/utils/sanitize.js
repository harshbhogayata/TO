/**
 * src/utils/sanitize.js
 * DOMPurify-based sanitization utilities for user-generated and AI-generated content.
 *
 * Usage:
 *   import { sanitizeHTML, sanitizePlainText } from '../utils/sanitize';
 *   const clean = sanitizeHTML(dirtyHtml);          // Allows safe tags
 *   const plain = sanitizePlainText(dirtyString);    // Strips ALL tags
 */
import DOMPurify from 'dompurify';

const ALLOWED_TAGS = [
    'b', 'i', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'a', 'blockquote', 'code', 'pre', 'span',
];

const ALLOWED_ATTR = ['href', 'target', 'rel', 'class'];

/**
 * Sanitize HTML content — allows a safe subset of tags.
 * Use for rich-text editors (PolicyManager), AI-generated descriptions, etc.
 */
export const sanitizeHTML = (dirty) => {
    if (!dirty) return '';
    return DOMPurify.sanitize(dirty, {
        ALLOWED_TAGS,
        ALLOWED_ATTR,
        ALLOW_DATA_ATTR: false,
    });
};

/**
 * Strip ALL HTML — returns plain text only.
 * Use for search inputs, form fields, chat messages, etc.
 */
export const sanitizePlainText = (dirty) => {
    if (!dirty) return '';
    return DOMPurify.sanitize(dirty, { ALLOWED_TAGS: [] });
};
