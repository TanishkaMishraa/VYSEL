import type { Config } from 'tailwindcss';

const config: Config = {
  presets: [require('@vysel/ui/tailwind-preset')],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', '../../packages/ui/src/**/*.{ts,tsx}'],
  // Components are styled by @vysel/ui CSS; Tailwind handles page layout only.
  corePlugins: { preflight: false },
};

export default config;
