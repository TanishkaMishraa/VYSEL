import type { Metadata } from 'next';
import Link from 'next/link';
import { StateMessage, buttonClassName } from '@vysel/ui';
import { SiteNav } from '@/components/landing/SiteChrome';

export const metadata: Metadata = {
  title: 'Scan — coming soon',
  robots: { index: false, follow: true },
};

/** Placeholder so CTAs never dead-end. Replaced by the real scan flow in a later phase. */
export default function ScanPage() {
  return (
    <>
      <SiteNav />
      <main id="main" className="vy-section">
        <div className="vy-container">
          <StateMessage
            kind="empty"
            title="The selfie scan is coming soon"
            description="VYSEL is in early development. Meanwhile, explore the sample Style DNA to see what your report will look like."
            actions={
              <Link href="/#style-dna" className={buttonClassName()}>
                <span className="vy-btn__label">See the sample report</span>
              </Link>
            }
          />
        </div>
      </main>
    </>
  );
}
