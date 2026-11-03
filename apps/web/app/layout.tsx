import type { Metadata, Viewport } from 'next';
import { Cinzel, Cormorant_Garamond, DM_Sans } from 'next/font/google';
import '@vysel/ui/tokens.css';
import '@vysel/ui/components.css';
import './globals.css';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { site } from '@/lib/site';

// Self-hosted at build time: no runtime request to Google, no layout shift.
const cinzel = Cinzel({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-cinzel', display: 'swap' });
const cormorant = Cormorant_Garamond({ subsets: ['latin'], weight: ['400', '500', '600'], style: ['normal', 'italic'], variable: '--font-cormorant', display: 'swap' });
const dmSans = DM_Sans({ subsets: ['latin'], weight: ['400', '500', '600'], variable: '--font-dm-sans', display: 'swap' });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: site.title, template: '%s · VYSEL' },
  description: site.description,
  applicationName: site.name,
  keywords: ['personal styling', 'face shape', 'undertone', 'colour palette', 'hairstyle recommendations', 'eyewear', 'makeup shades', 'Style DNA'],
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: '/',
    siteName: site.name,
    title: site.title,
    description: site.description,
    locale: 'en_IN',
  },
  twitter: { card: 'summary_large_image', title: site.title, description: site.description },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: '#0B0A0C', // --vy-obsidian-950
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="obsidian" className={`${cinzel.variable} ${cormorant.variable} ${dmSans.variable}`}>
      <body className="vy-root">
        <a className="vy-skip-link" href="#main">
          Skip to content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
