# Landing Page — Phase 1.5

The marketing page at `/`, built with Next.js 14 (App Router), TypeScript and the `@vysel/ui` design system.

```bash
npm install          # from the repo root (npm workspaces)
npm run dev          # http://localhost:3000
npm run build        # production build + type check
```

## Concept: "The Reveal"

A quiet, editorial walk from one selfie to a finished Style DNA. The story is told with the product's real mechanics, not with stock photos or claims:

- **No faces, no stock imagery.** The hero shows a hairline diagram of what VYSEL actually measures: landmarks, face length, cheekbone and jaw width, and a skin sample. It is pure SVG drawn on with CSS.
- **Honesty is a design feature.** Every inferred value carries a dashed *estimate* badge. Each How-It-Works step names its limits. The sample report is labelled *illustrative* in three places.
- **One accent, one tonal shift.** The page is obsidian with rose-gold details. The final CTA band switches to the Porcelain theme (`data-theme="porcelain"`) to mark the close.

## Section flow

| # | Section | Component | Purpose | Interaction |
|---|---|---|---|---|
| — | Nav | `SiteNav` → `NavBar` | Orientation, persistent CTA | Sticky translucent bar; mobile disclosure menu closes on link tap |
| 1 | Hero | `Hero`, `FaceMap` | Promise + how it works at a glance | Face map draws on; floating "Face shape / Palette" cards settle in |
| 2 | How it works | `HowItWorks` | Four steps, each with "limits we design for" | Vertical WAI-ARIA tabs (↑/↓/Home/End); a visual per step |
| 3 | Style DNA | `StyleDnaSection`, `StyleDnaReport` | Show the output and why it's personal | Budget/style chips re-rank picks live; palette radio group; category tabs; scroll reveal |
| 4 | Features | `Features` | Personal styling, beauty analysis, personalised picks + principles | Hairline accent draws on hover/focus |
| 5 | Final CTA | `FinalCta` | Convert; state the honest product status | Porcelain band |
| — | Footer | `SiteFooter` | Navigation, commitments, credit | — |

CTAs point to `site.cta.href` (`/scan`). Signed-in users can enter their own feature estimates and create a saved recommendation report. A photo may be previewed locally, but is not uploaded or analyzed; automated facial analysis is not implemented.

## File map

```
apps/web/
├─ app/
│  ├─ layout.tsx            fonts (next/font), metadata, viewport, skip link
│  ├─ page.tsx              section composition + JSON-LD
│  ├─ globals.css           token font overrides + landing (lp-*) styles
│  ├─ scan/page.tsx         user-entered estimates and report creation; local-only optional photo preview
│  ├─ reports/[id]/page.tsx private report, feedback, sharing controls and print-to-PDF
│  ├─ shared/[token]/page.tsx token-gated public report view
│  ├─ dashboard/page.tsx    signed-in overview, saved preferences and report history
│  ├─ settings/page.tsx     account and preference management
│  ├─ opengraph-image.tsx   generated 1200×630 OG image from wordmark paths
│  ├─ icon.png · apple-icon.png · favicon.ico   app icons (from packages/ui/assets/brand/vysel-logo.png)
│  ├─ robots.ts · sitemap.ts
├─ components/landing/
│  ├─ Hero.tsx · FaceMap.tsx · HowItWorks.tsx
│  ├─ StyleDnaSection.tsx · StyleDnaReport.tsx (client)
│  ├─ Features.tsx · FinalCta.tsx · SiteChrome.tsx (nav + footer)
│  ├─ SectionHeading.tsx · Reveal.tsx (client)
└─ lib/
   ├─ site.ts               name, URL, CTA, nav — single place to edit
   ├─ sample-report.ts      ILLUSTRATIVE data + transparent ranking rule
   └─ reports.ts            Report, feature and recommendation API types
```

**Reuse rule:** UI elements come from `@vysel/ui`: Button/`buttonClassName`, Card, Badge/EstimateBadge, ChoiceChips, Tabs, Confidence, Alert, StateMessage, NavBar, Wordmark/Monogram. Landing CSS (`lp-*`) covers only layout and bespoke visuals, and uses tokens only. Tailwind is limited to layout utilities (preflight disabled so it never fights component CSS).

Design-system additions made for this phase: `Tabs orientation="vertical"` and `onChange`, `buttonClassName()` for styled links, and auto-closing `NavBar` menus.

## Sample data — illustrative only

`lib/sample-report.ts` mirrors the API's `StyleDNA` schema (face shape, undertone, skin depth, palette, ranked picks) and matches the OpenAPI example. It is **not** a real person's result and is not model output. The UI says so with a badge in the report header, an `Alert` at its foot, and the hero caption.

Ranking is a transparent rule, mirroring the MVP recommender in the product deck:

```
score = 0.6 × fit + 0.25 × (matches style ? 1 : 0.4) + 0.15 × (within budget ? 1 : 0.2)
```

The weights are illustrative and are shown as such in How-It-Works step 3.

**Content rules** (from the brief, enforced in copy review): no testimonials, user counts, accuracy percentages or partner logos. Privacy statements are phrased as commitments, and product status is stated plainly ("in early development").

## Interaction & motion

| Interaction | Implementation | Reduced motion |
|---|---|---|
| Face map draw-on | SVG `pathLength=1` + `stroke-dashoffset` keyframes, staggered via `--d` | Rendered complete, no animation |
| Scroll reveal | `Reveal`: off-screen blocks fade/rise once via IntersectionObserver. On-screen or no-JS content is never hidden | Disabled |
| Re-ranking | List keyed by preferences → staggered fade-in (`--i`) | Instant |
| Palette | Radio group; arrow keys move selection; detail panel is `aria-live` | Colour change only |
| Hover | Swatch lift, feature hairline draw, nav underline | Transforms removed |

All durations and easings come from motion tokens, and nothing loops except the spinner.

## Responsive design

| Width | Layout |
|---|---|
| < 480 | Single column; floating hero cards tuck inside the visual; chips wrap |
| 480–767 | Single column; nav collapses to a menu; How-It-Works tabs scroll horizontally above the panel |
| 768–1023 | Vertical tabs beside the panel; three-column features; report stacks |
| ≥ 1024 | Two-column hero; report in two columns (features + traits / palette + picks) |

## Accessibility

- Skip link, landmark regions (`nav`, `main`, `footer`), one `h1`, and every section labelled by its `h2`.
- Tabs follow the WAI-ARIA pattern (roving tabindex, arrow keys, Home/End). The palette is a `radiogroup`.
- Confidence meters use `role="meter"` with `aria-valuetext`. Re-ranking announces its context via `aria-live`.
- Decorative floating cards are `aria-hidden`; the face map has a descriptive `aria-label`.
- Contrast: all token pairs meet WCAG AA in both themes (`npm run ds:validate`).
- Focus rings come from the design system (`--vy-focus`), visible on every interactive element.

## Performance & SEO

- **Raster only for the logo.** The app icon (`vysel-logo.png`) is the one raster asset, served through `next/image`; illustration and UI icons are inline SVG, and the OG image is generated at build time.
- **Fonts** are self-hosted by `next/font` with `display: swap` (no request to Google at runtime) and only the weights in use.
- **JS:** only `StyleDnaReport`, `Reveal`, `Tabs` and `NavBar` are client components; everything else is server-rendered HTML.
- **Metadata:** title template, description, canonical, Open Graph and Twitter cards, `theme-color`, `robots.txt`, `sitemap.xml`, and JSON-LD (`WebSite` and `Organization` only, with no ratings or offers).
- **Headers:** `nosniff`, `Referrer-Policy`, `Permissions-Policy` (camera allowed for self only, ready for the scan), `X-Frame-Options: DENY`.
- Set `NEXT_PUBLIC_SITE_URL` in production; `https://vysel.app` is a placeholder.

## Remaining issues / next steps

- Choose a real domain and set `NEXT_PUBLIC_SITE_URL`.
- Add consent-gated upload and automated image analysis (Phase 2); the current report uses self-entered estimates and the optional photo preview is local-only.
- Copy review with the team, especially the privacy commitments, which must match the shipped behaviour.
- Add analytics only after a consent decision; none are included.
- Validate the illustrative palette and picks with the planned user interviews before using them in marketing beyond this page.
