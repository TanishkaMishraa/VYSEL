import type { CSSProperties, ReactNode } from 'react';
import { Badge, Icon, Tabs, type TabItem } from '@vysel/ui';
import { WEIGHTS, samplePalette } from '@/lib/sample-report';
import { FaceMap } from './FaceMap';
import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';

interface Step {
  id: string;
  title: string;
  body: string;
  limit: string;
  visual: ReactNode;
}

const STEPS: Step[] = [
  {
    id: 'selfie',
    title: 'Selfie & preferences',
    body: 'Take one front-facing selfie and, if you like, set a budget and style. A face guide and quick checks catch blur, low light or tilt before anything is analysed.',
    limit: 'Blurry, dark or off-angle photos trigger a retake prompt instead of a guess.',
    visual: (
      <div className="flex flex-wrap items-center justify-center gap-8">
        <div className="lp-phone" aria-hidden="true">
          <span className="lp-phone__guide" />
        </div>
        <ul className="lp-checks" aria-label="Photo checks">
          {['Face centred', 'Even light', 'Sharp focus'].map((c) => (
            <li key={c}>
              <Icon name="check" />
              {c}
            </li>
          ))}
        </ul>
      </div>
    ),
  },
  {
    id: 'estimate',
    title: 'Feature estimation',
    body: 'Facial landmarks give proportions such as face length and cheekbone and jaw width, which map to an estimated face shape. Sampled skin pixels give a tone and undertone estimate.',
    limit: 'Shape boundaries are fuzzy and lighting shifts colour, so every result carries a confidence and an “estimate” label.',
    visual: <FaceMap labels={false} className="max-w-[15rem]" />,
  },
  {
    id: 'rules',
    title: 'Recommendation logic',
    body: 'Transparent rules score each option on how well it fits your features, your style and your budget. No black box: every pick comes with its reason.',
    limit: 'Rules first. Machine learning only once it is trained and evaluated on suitable data.',
    visual: (
      <div className="lp-weights">
        {[
          ['Fit to your features', WEIGHTS.fit],
          ['Your style', WEIGHTS.style],
          ['Your budget', WEIGHTS.budget],
        ].map(([label, v]) => (
          <div className="lp-weight" key={label as string}>
            <div className="lp-weight__head">
              <span>{label}</span>
              <span className="vy-numeric vy-caption">{Math.round((v as number) * 100)}%</span>
            </div>
            <div className="lp-bar" aria-hidden="true">
              <span style={{ '--lp-v': v } as CSSProperties} />
            </div>
          </div>
        ))}
        <p className="vy-caption">Illustrative weights</p>
      </div>
    ),
  },
  {
    id: 'dna',
    title: 'Your Style DNA',
    body: 'A ranked set of picks for hair, eyewear and makeup, plus a colour palette. Each pick has a one-line reason, so you can see why it was suggested.',
    limit: 'Guidance, not objective truth. Change your preferences to explore alternatives.',
    visual: (
      <div className="vy-card vy-card--gilded w-full max-w-[18rem]">
        <p className="vy-overline">Style DNA · sample</p>
        <span className="lp-dots">
          {samplePalette.map((c) => (
            <span key={c.name} className="lp-dot-swatch" style={{ '--lp-c': c.hex } as CSSProperties} />
          ))}
        </span>
        <p className="vy-card__title">Soft layers</p>
        <p className="vy-card__body">Balanced proportions carry layered volume without widening the face.</p>
        <div className="vy-card__footer">
          <Badge tone="estimate">Estimate</Badge>
        </div>
      </div>
    ),
  },
];

export function HowItWorks() {
  const items: TabItem[] = STEPS.map((s, i) => ({
    id: s.id,
    label: (
      <>
        <span className="lp-tab-num">0{i + 1}</span>
        {s.title}
      </>
    ),
    content: (
      <div className="lp-step">
        <div className="lp-step__visual">{s.visual}</div>
        <div className="flex flex-col gap-5">
          <span className="lp-step__num" aria-hidden="true">
            0{i + 1}
          </span>
          <h3 className="vy-h3">{s.title}</h3>
          <p className="vy-body">{s.body}</p>
          <p className="lp-step__limit">
            <Icon name="info" />
            <span>
              <strong>Limits we design for.</strong> {s.limit}
            </span>
          </p>
        </div>
      </div>
    ),
  }));

  return (
    <section className="vy-section" aria-labelledby="how-title" id="how-it-works">
      <div className="vy-container flex flex-col gap-16">
        <Reveal>
          <SectionHeading
            id="how-title"
            eyebrow="How it works"
            title={
              <>
                From one selfie to <span className="vy-emphasis">your Style DNA</span>
              </>
            }
            lead="Four steps, each one explained, including what it can't do yet."
          />
        </Reveal>
        <Reveal delay={120}>
          <Tabs items={items} label="How VYSEL works" orientation="vertical" />
        </Reveal>
      </div>
    </section>
  );
}
