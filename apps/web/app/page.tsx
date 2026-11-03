import { Features } from '@/components/landing/Features';
import { FinalCta } from '@/components/landing/FinalCta';
import { Hero } from '@/components/landing/Hero';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { SiteFooter, SiteNav } from '@/components/landing/SiteChrome';
import { StyleDnaSection } from '@/components/landing/StyleDnaSection';
import { site } from '@/lib/site';

// Structured data: describes the site only — no ratings, prices or claims.
const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    { '@type': 'WebSite', name: site.name, url: site.url, description: site.description },
    { '@type': 'Organization', name: site.name, url: site.url, logo: `${site.url}/icon.svg` },
  ],
};

export default function HomePage() {
  return (
    <>
      <SiteNav />
      <main id="main">
        <span id="top" />
        <Hero />
        <HowItWorks />
        <StyleDnaSection />
        <Features />
        <FinalCta />
      </main>
      <SiteFooter />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    </>
  );
}
