import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';
import { StyleDnaReport } from './StyleDnaReport';

export function StyleDnaSection() {
  return (
    <section className="vy-section" aria-labelledby="dna-title" id="style-dna">
      <div className="vy-container flex flex-col gap-14">
        <Reveal>
          <SectionHeading
            id="dna-title"
            eyebrow="Style DNA · sample report"
            title={
              <>
                Not a lookup table. <span className="vy-emphasis">A ranking that listens.</span>
              </>
            }
            lead="A lookup gives every oval face the same list. Change the budget or style below and watch the picks re-rank, each with its reason."
          />
        </Reveal>
        <Reveal delay={120}>
          <StyleDnaReport />
        </Reveal>
      </div>
    </section>
  );
}
