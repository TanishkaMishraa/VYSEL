import { Icon } from '@vysel/ui';
import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';

const FEATURES = [
  {
    title: 'Personal styling',
    body: 'Haircuts and eyewear matched to the proportions of your face, not to whatever is trending this week.',
    points: ['Face shape estimated from landmark geometry', 'Hair and frame picks ranked by fit', 'A short reason for every pick'],
  },
  {
    title: 'Beauty analysis',
    body: 'Skin tone and undertone estimated from your photo, turned into a palette you can actually wear.',
    points: ['Undertone and depth, labelled as estimates', 'A five-shade palette with how to wear each', 'Makeup shades that sit within it'],
  },
  {
    title: 'Personalised picks',
    body: 'Your budget and style shape the ranking, so two people with the same face shape get different advice.',
    points: ['Budget-aware: low, mid or high', 'Style-aware: everyday, minimal or bold', 'Adjust and re-rank at any time'],
  },
];

const PRINCIPLES = [
  { title: 'Explainable', body: 'Every recommendation says why. Estimates show their confidence. Nothing is presented as objective truth.' },
  { title: 'Private by default', body: 'Consent comes first. Photos are deleted after analysis unless you choose to keep them.' },
  { title: 'Accessible', body: 'Personal guidance from one selfie, for people who cannot easily reach or afford a stylist.' },
];

export function Features() {
  return (
    <section className="vy-section" aria-labelledby="features-title" id="features">
      <div className="vy-container flex flex-col gap-16">
        <Reveal>
          <SectionHeading id="features-title" eyebrow="What you get" title="Three kinds of guidance, one selfie" />
        </Reveal>
        <div className="lp-features">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 100}>
              <article className="lp-featurecard">
                <span className="lp-step__num" aria-hidden="true">
                  0{i + 1}
                </span>
                <h3 className="vy-h3">{f.title}</h3>
                <p className="vy-body">{f.body}</p>
                <ul>
                  {f.points.map((p) => (
                    <li key={p}>
                      <Icon name="facet" />
                      {p}
                    </li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
        <Reveal>
          <div className="lp-principles" role="list" aria-label="Principles">
            {PRINCIPLES.map((p) => (
              <div className="lp-principle" role="listitem" key={p.title}>
                <p className="vy-overline">{p.title}</p>
                <p className="vy-body vy-caption">{p.body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
