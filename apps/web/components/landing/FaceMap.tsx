import type { CSSProperties } from 'react';

/**
 * Hairline illustration of what VYSEL measures: landmarks, face length,
 * cheekbone and jaw width, and a skin-tone sample. Pure SVG + CSS animation
 * (no JS, no raster), so it costs nothing to load and respects reduced motion.
 */
type Pt = readonly [number, number];

const OUTLINE = 'M210 60 C300 60 345 140 345 235 C345 330 300 420 210 462 C120 420 75 330 75 235 C75 140 120 60 210 60 Z';

const POINTS: Pt[] = [
  [210, 60], [150, 80], [270, 80], [98, 150], [322, 150],
  [140, 195], [180, 190], [240, 190], [280, 195],
  [150, 222], [185, 222], [235, 222], [270, 222],
  [80, 240], [340, 240], [210, 230], [210, 290], [190, 300], [230, 300],
  [125, 300], [295, 300], [180, 345], [210, 340], [240, 345], [210, 360],
  [105, 370], [315, 370], [150, 425], [270, 425], [210, 462],
];

// Sparse mesh — suggests a landmark model without pretending to be one.
const MESH: Pt[][] = [
  [[98, 150], [140, 195], [180, 190], [210, 230], [240, 190], [280, 195], [322, 150]],
  [[80, 240], [150, 222], [185, 222], [210, 230], [235, 222], [270, 222], [340, 240]],
  [[80, 240], [125, 300], [190, 300], [210, 290], [230, 300], [295, 300], [340, 240]],
  [[105, 370], [180, 345], [210, 340], [240, 345], [315, 370]],
  [[150, 425], [210, 360], [270, 425]],
  [[125, 300], [180, 345]], [[295, 300], [240, 345]],
  [[150, 80], [140, 195]], [[270, 80], [280, 195]], [[210, 60], [210, 230]],
];

const line = (pts: Pt[]) => 'M' + pts.map(([x, y]) => `${x} ${y}`).join(' L');

export function FaceMap({ labels = true, className }: { labels?: boolean; className?: string }) {
  return (
    <svg
      className={['lp-facemap', className].filter(Boolean).join(' ')}
      viewBox="0 0 420 500"
      role="img"
      aria-label="Illustration of the proportions VYSEL measures from a selfie: facial landmarks, face length, cheekbone width and jaw width."
    >
      <path className="lp-facemap__outline lp-draw" d={OUTLINE} pathLength={1} />
      {MESH.map((pts, i) => (
        <path key={i} className="lp-facemap__mesh lp-draw" d={line(pts)} pathLength={1} style={{ '--d': `${0.5 + i * 0.06}s` } as CSSProperties} />
      ))}
      {POINTS.map(([x, y], i) => (
        <circle key={i} className="lp-facemap__point lp-appear" cx={x} cy={y} r={2.2} style={{ '--d': `${0.6 + i * 0.025}s` } as CSSProperties} />
      ))}

      {/* Measurements */}
      <g className="lp-appear" style={{ '--d': '1.2s' } as CSSProperties}>
        <path className="lp-facemap__measure lp-facemap__measure--dashed" d="M80 240 H340" />
        <path className="lp-facemap__measure lp-facemap__measure--dashed" d="M105 370 H315" />
        <path className="lp-facemap__measure" d="M385 60 V462 M378 60 H392 M378 462 H392" />
        <circle className="lp-facemap__sample" cx={295} cy={300} r={13} />
      </g>
      {labels && (
        <g className="lp-appear" style={{ '--d': '1.4s' } as CSSProperties}>
          <text className="lp-facemap__label" x={210} y={232} textAnchor="middle" dy={-14}>
            Cheekbone width
          </text>
          <text className="lp-facemap__label" x={210} y={388} textAnchor="middle">
            Jaw width
          </text>
          <text className="lp-facemap__label" x={402} y={261} textAnchor="middle" transform="rotate(90 402 261)">
            Face length
          </text>
          <text className="lp-facemap__label" x={295} y={332} textAnchor="middle">
            Skin tone
          </text>
        </g>
      )}
    </svg>
  );
}
