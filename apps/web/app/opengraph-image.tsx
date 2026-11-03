import { ImageResponse } from 'next/og';
import paths from '@vysel/ui/brand-paths.json';

export const alt = 'VYSEL — Style advice built from your face';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
// Edge runtime: also avoids a Windows path bug in @vercel/og's Node build (Next 14).
export const runtime = 'edge';

// Brand values inlined: ImageResponse cannot read CSS variables.
const OBSIDIAN = '#0B0A0C';
const PORCELAIN = '#F7F1EA';
const ROSE_GOLD = '#D9A68D';

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: OBSIDIAN, gap: 48 }}>
        <svg width={540} height={155} viewBox={paths.wordmark.viewBox}>
          <path d={paths.wordmark.d} fill={PORCELAIN} />
        </svg>
        <div style={{ display: 'flex', width: 80, height: 1, background: ROSE_GOLD }} />
        <div style={{ color: PORCELAIN, fontSize: 40, fontStyle: 'italic', fontFamily: 'serif', opacity: 0.85 }}>Style advice built from your face, not a trend list.</div>
      </div>
    ),
    size,
  );
}
