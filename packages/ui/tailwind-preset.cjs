/**
 * Tailwind preset — exposes VYSEL tokens as utilities. Values point at CSS
 * variables, so themes switch at runtime with no rebuild.
 *
 *   // apps/web/tailwind.config.ts
 *   presets: [require('@vysel/ui/tailwind-preset')]
 *
 * Use utilities for page layout; use .vy-* component classes / React components
 * for UI elements so components are never re-implemented in utilities.
 */
const channel = (name) => `rgb(var(--vy-${name}) / <alpha-value>)`;

const semantic = [
  'bg', 'surface', 'surface-raised', 'surface-sunken',
  'text', 'text-muted', 'text-subtle', 'text-inverse',
  'border', 'border-emphasis',
  'accent', 'accent-hover', 'accent-pressed', 'accent-contrast', 'accent-text',
  'focus', 'success', 'warning', 'danger', 'info', 'estimate',
];

const scale = (palette, steps) => Object.fromEntries(steps.map((s) => [s, channel(`${palette}-${s}`)]));

/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        ...Object.fromEntries(semantic.map((n) => [n, channel(n)])),
        obsidian: scale('obsidian', [500, 600, 700, 800, 900, 950]),
        porcelain: scale('porcelain', [50, 100, 200, 300, 400]),
        'rose-gold': scale('rose-gold', [200, 300, 400, 500, 600, 700, 800]),
      },
      fontFamily: {
        display: 'var(--vy-font-display)',
        editorial: 'var(--vy-font-editorial)',
        sans: 'var(--vy-font-sans)',
      },
      fontSize: {
        '2xs': 'var(--vy-text-2xs)', xs: 'var(--vy-text-xs)', sm: 'var(--vy-text-sm)', base: 'var(--vy-text-md)',
        lg: 'var(--vy-text-lg)', xl: 'var(--vy-text-xl)', '2xl': 'var(--vy-text-2xl)', '3xl': 'var(--vy-text-3xl)',
        '4xl': 'var(--vy-text-4xl)', '5xl': 'var(--vy-text-5xl)', '6xl': 'var(--vy-text-6xl)', '7xl': 'var(--vy-text-7xl)',
      },
      letterSpacing: { caps: 'var(--vy-tracking-caps)', overline: 'var(--vy-tracking-overline)' },
      spacing: { section: 'var(--vy-section-y)', gutter: 'var(--vy-gutter)' },
      maxWidth: { container: 'var(--vy-container)', narrow: 'var(--vy-container-narrow)', measure: 'var(--vy-measure)' },
      borderRadius: {
        xs: 'var(--vy-radius-xs)', sm: 'var(--vy-radius-sm)', md: 'var(--vy-radius-md)', lg: 'var(--vy-radius-lg)', pill: 'var(--vy-radius-pill)',
      },
      boxShadow: { sm: 'var(--vy-shadow-sm)', md: 'var(--vy-shadow-md)', lg: 'var(--vy-shadow-lg)', glow: 'var(--vy-shadow-glow)' },
      backgroundImage: { gilded: 'var(--vy-gilded)' },
      transitionDuration: { fast: 'var(--vy-duration-fast)', base: 'var(--vy-duration-base)', slow: 'var(--vy-duration-slow)', reveal: 'var(--vy-duration-reveal)' },
      transitionTimingFunction: { standard: 'var(--vy-ease-standard)', enter: 'var(--vy-ease-enter)', exit: 'var(--vy-ease-exit)', silk: 'var(--vy-ease-silk)' },
      zIndex: { sticky: 'var(--vy-z-sticky)', overlay: 'var(--vy-z-overlay)', modal: 'var(--vy-z-modal)', toast: 'var(--vy-z-toast)' },
    },
  },
};
