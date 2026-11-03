import Image from 'next/image';
import Link from 'next/link';
import { buttonClassName } from '@vysel/ui';
import logo from '@vysel/ui/assets/brand/vysel-logo.png';
import { site } from '@/lib/site';
import { Reveal } from './Reveal';

/** Closing band in the Porcelain theme — a deliberate tonal shift before the footer. */
export function FinalCta() {
  return (
    <section className="lp-band vy-section" data-theme="porcelain" aria-labelledby="cta-title">
      <Reveal className="vy-container vy-container--narrow lp-band__inner">
        <Image src={logo} alt="" className="lp-band__mono" sizes="72px" />
        <h2 className="vy-h2" id="cta-title">
          Meet your <span className="vy-emphasis">Style DNA</span>.
        </h2>
        <p className="vy-lead">One selfie and a few preferences. A palette and picks explained in plain language.</p>
        <div className="flex flex-wrap items-center justify-center gap-6">
          <Link href={site.cta.href} className={buttonClassName({ size: 'lg' })}>
            <span className="vy-btn__label">{site.cta.label}</span>
          </Link>
          <a href="#style-dna" className={buttonClassName({ variant: 'link' })}>
            <span className="vy-btn__label">Revisit the sample</span>
          </a>
        </div>
        <p className="vy-caption">You can create a report from your own estimates or choose to analyze a selfie.</p>
      </Reveal>
    </section>
  );
}
