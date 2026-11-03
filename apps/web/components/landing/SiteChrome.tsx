import Link from 'next/link';
import { NavBar, Wordmark, buttonClassName } from '@vysel/ui';
import { site } from '@/lib/site';

export function SiteNav() {
  return (
    <NavBar
      links={site.nav.map((l) => ({ ...l }))}
      actions={
        <Link href={site.cta.href} className={buttonClassName({ size: 'sm' })}>
          <span className="vy-btn__label">Get started</span>
        </Link>
      }
    />
  );
}

export function SiteFooter() {
  return (
    <footer className="lp-footer">
      <div className="vy-container">
        <div className="lp-footer__grid">
          <div className="flex flex-col gap-4">
            <a href="#top" className="lp-footer__brand" aria-label="VYSEL, back to top">
              <Wordmark title={null} />
            </a>
            <p className="vy-caption max-w-[22rem]">
              AI-powered personal styling. Style advice built from your face, not a trend list.
            </p>
          </div>
          <nav aria-label="Footer">
            <p className="vy-overline">Explore</p>
            <ul className="lp-footer__links">
              {site.nav.map((l) => (
                <li key={l.href}>
                  <a href={l.href}>{l.label}</a>
                </li>
              ))}
              <li>
                <Link href={site.cta.href}>Start a scan</Link>
              </li>
            </ul>
          </nav>
          <div>
            <p className="vy-overline">Our commitments</p>
            <ul className="lp-footer__links">
              <li>Consent before analysis</li>
              <li>Photos deleted by default</li>
              <li>Results labelled as estimates</li>
            </ul>
          </div>
        </div>
        <div className="lp-footer__base">
          <p className="vy-caption">© {new Date().getFullYear()} VYSEL · {site.team}</p>
          <p className="vy-caption">Guidance, not objective truth.</p>
        </div>
      </div>
    </footer>
  );
}
