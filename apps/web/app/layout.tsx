import type { Metadata, Viewport } from 'next';
import '@vysel/ui/tokens.css';
import '@vysel/ui/components.css';
import './globals.css';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { site } from '@/lib/site';

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
    <html lang="en" data-theme="obsidian">
      <body className="vy-root">
        <a className="vy-skip-link" href="#main">
          Skip to content
        </a>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
