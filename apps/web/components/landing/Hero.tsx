import type { CSSProperties } from 'react';
import Link from 'next/link';
import { Badge, Card, Icon, buttonClassName } from '@vysel/ui';
import { site } from '@/lib/site';
import { samplePalette, sampleFeatures } from '@/lib/sample-report';
import { FaceMap } from './FaceMap';

const TRUST = ['Consent before any photo is analysed', 'Photos deleted after analysis by default', 'Every result labelled as an estimate'];

export function Hero() {
  return (
    <section className="lp-hero" aria-labelledby="hero-title">
      <div className="vy-container lp-hero__grid">
        <div className="vy-reveal">
          <p className="vy-overline">AI-powered personal styling</p>
          <h1 className="lp-hero__title" id="hero-title">
            Style advice built from <em>your face</em>, not a trend list.
          </h1>
          <p className="vy-lead">
            One selfie. VYSEL estimates your face shape and undertone, then explains which cuts, frames and shades suit you, and why.
          </p>
          <div className="lp-hero__ctas">
            <Link href={site.cta.href} className={buttonClassName({ size: 'lg' })}>
              <span className="vy-btn__label">
                {site.cta.label}
                <Icon name="arrowRight" />
              </span>
            </Link>
            <a href="#style-dna" className={buttonClassName({ variant: 'link' })}>
              <span className="vy-btn__label">See a sample report</span>
            </a>
          </div>
          <ul className="lp-trust" aria-label="Our privacy and honesty commitments">
            {TRUST.map((t) => (
              <li key={t}>
                <Icon name="facet" />
                {t}
              </li>
            ))}
          </ul>
        </div>

        <figure className="lp-visual">
          <FaceMap />
          <Card variant="raised" className="lp-float lp-float--shape" aria-hidden="true">
            <span className="vy-overline">Face shape</span>
            <span className="lp-float__value">{sampleFeatures.faceShape.value}</span>
            <Badge tone="estimate">Estimate · {Math.round(sampleFeatures.faceShape.confidence * 100)}%</Badge>
          </Card>
          <Card variant="raised" className="lp-float lp-float--palette" aria-hidden="true">
            <span className="vy-overline">Palette</span>
            <span className="lp-dots">
              {samplePalette.map((c) => (
                <span key={c.name} className="lp-dot-swatch" style={{ '--lp-c': c.hex } as CSSProperties} />
              ))}
            </span>
          </Card>
          <figcaption className="vy-caption lp-visual__caption">
            Illustration · sample values
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
