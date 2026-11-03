/** Site-wide constants. Change the CTA target here when the scan flow ships. */
export const site = {
  name: 'VYSEL',
  url: process.env.NEXT_PUBLIC_SITE_URL ?? 'https://vysel.app', // placeholder until a domain is chosen
  title: 'VYSEL — Style advice built from your face',
  description:
    'Upload one selfie. VYSEL estimates your face shape and undertone, then recommends haircuts, eyewear and makeup shades, each with a short reason why.',
  cta: { label: 'Discover your Style DNA', href: '/scan' },
  team: 'Team Terrificers · PSIT Kanpur',
  nav: [
    { href: '#how-it-works', label: 'How it works' },
    { href: '#style-dna', label: 'Style DNA' },
    { href: '#features', label: 'Features' },
  ],
} as const;
