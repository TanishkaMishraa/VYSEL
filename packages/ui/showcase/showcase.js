/* VYSEL design system showcase — no build step, opens from disk. */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const html = document.documentElement;
  const css = (name) => getComputedStyle(html).getPropertyValue(name).trim();
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  VY.hydrate(document);

  // ── Colour maths (WCAG 2.x) ────────────────────────────────────────────
  const channels = (v) => v.split(/\s+/).map(Number);
  const toHex = (rgb) => '#' + rgb.map((n) => n.toString(16).padStart(2, '0')).join('').toUpperCase();
  const lum = (rgb) => {
    const [r, g, b] = rgb.map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

  // ── Palette (primitives, read live from tokens.css) ───────────────────
  const PALETTES = {
    Obsidian: ['obsidian-950', 'obsidian-900', 'obsidian-800', 'obsidian-700', 'obsidian-600', 'obsidian-500'],
    Porcelain: ['porcelain-50', 'porcelain-100', 'porcelain-200', 'porcelain-300', 'porcelain-400'],
    'Rose gold': ['rose-gold-200', 'rose-gold-300', 'rose-gold-400', 'rose-gold-500', 'rose-gold-600', 'rose-gold-700', 'rose-gold-800'],
    Complementary: ['champagne-300', 'plum-400', 'plum-700', 'sage-400', 'sage-700', 'amber-400', 'amber-700', 'garnet-400', 'garnet-700', 'mist-400', 'mist-700'],
  };
  $('#palette').innerHTML = Object.entries(PALETTES).map(([group, tokens]) => `
    <h3 class="sc-sub">${group}</h3>
    <div class="sc-grid" style="--sc-min: 8.5rem">${tokens.map((t) => {
      const v = css(`--vy-${t}`);
      return `<div class="sc-swatch"><div class="sc-swatch__color" style="--sc-c: var(--vy-${t})"></div><div class="sc-swatch__meta"><span class="sc-swatch__name">${t}</span><code class="sc-tile__label">${toHex(channels(v))}</code></div></div>`;
    }).join('')}</div>`).join('');

  // ── Contrast table (semantic, per theme) ──────────────────────────────
  const PAIRS = [
    ['text', 'bg', 4.5, 'Body text'],
    ['text-muted', 'bg', 4.5, 'Secondary text'],
    ['text-muted', 'surface-raised', 4.5, 'Secondary text on cards'],
    ['accent-contrast', 'accent', 4.5, 'Primary button label'],
    ['accent-text', 'bg', 4.5, 'Links, overlines'],
    ['accent-text', 'surface', 4.5, 'Links on surface'],
    ['success', 'bg', 4.5, 'Success text'],
    ['warning', 'bg', 4.5, 'Warning text'],
    ['danger', 'bg', 4.5, 'Error text'],
    ['info', 'bg', 4.5, 'Info text'],
    ['estimate', 'bg', 4.5, 'Estimate badge'],
    ['focus', 'bg', 3, 'Focus ring (non-text)'],
    ['border-emphasis', 'bg', 3, 'Input boundary (non-text)'],
  ];
  function renderContrast() {
    $('#contrast tbody').innerHTML = PAIRS.map(([fg, bg, min, use]) => {
      const r = ratio(channels(css(`--vy-${fg}`)), channels(css(`--vy-${bg}`)));
      const pass = r >= min;
      const grade = min === 3 ? (pass ? 'Non-text AA' : 'Fail') : r >= 7 ? 'AAA' : pass ? 'AA' : 'Fail';
      return `<tr><td><code>--vy-${fg}</code> on <code>--vy-${bg}</code><br><span class="vy-caption">${use}</span></td>
        <td><span class="sc-pair" style="color: rgb(var(--vy-${fg})); background: rgb(var(--vy-${bg})); border: 1px solid rgb(var(--vy-border))">Aa</span></td>
        <td class="vy-numeric">${r.toFixed(2)}:1</td>
        <td><span class="vy-badge vy-badge--${pass ? 'success' : 'danger'}">${grade}</span></td></tr>`;
    }).join('');
    $$('[data-theme-name]').forEach((el) => { el.textContent = html.dataset.theme === 'porcelain' ? 'Porcelain' : 'Obsidian'; });
  }

  // ── Spacing & motion scales ───────────────────────────────────────────
  $('#spacing').innerHTML = ['1', '2', '3', '4', '6', '8', '12', '16', '24', '32']
    .map((s) => `<div class="sc-space"><code>--vy-space-${s}</code><span class="sc-space__bar" style="--sc-w: var(--vy-space-${s})"></span><span class="vy-caption">${parseFloat(css(`--vy-space-${s}`)) * 16}px</span></div>`)
    .join('');
  const MOTION = [['fast', 'standard'], ['base', 'standard'], ['slow', 'enter'], ['reveal', 'silk']];
  $('#motion').innerHTML = MOTION.map(([d, e]) => `
    <div><span class="sc-tile__label">--vy-duration-${d} · --vy-ease-${e}</span>
    <div class="sc-motion"><span class="sc-motion__dot" style="transition-duration: var(--vy-duration-${d}); transition-timing-function: var(--vy-ease-${e})"></span></div></div>`).join('');
  $('#motion-play').addEventListener('click', () => {
    $$('.sc-motion').forEach((m) => {
      m.style.setProperty('--sc-track', m.clientWidth + 'px');
      m.dataset.on = String(m.dataset.on !== 'true');
    });
  });

  // ── Theme & motion toggles ────────────────────────────────────────────
  const applyGlobal = () => {
    html.dataset.theme = $('input[name="theme"]:checked').value;
    html.dataset.motion = $('input[name="motion"]:checked').value;
    renderContrast();
    renderPlayground();
  };
  $$('input[name="theme"], input[name="motion"]').forEach((i) => i.addEventListener('change', applyGlobal));

  // ── Demo: loading button ──────────────────────────────────────────────
  $('#demo-loading').addEventListener('click', function () {
    if (this.getAttribute('aria-busy') === 'true') return;
    this.setAttribute('aria-busy', 'true');
    this.setAttribute('aria-disabled', 'true');
    this.insertAdjacentHTML('beforeend', '<span class="vy-spinner" aria-hidden="true"></span>');
    setTimeout(() => {
      this.removeAttribute('aria-busy');
      this.removeAttribute('aria-disabled');
      this.querySelector('.vy-spinner').remove();
    }, 1800);
  });

  // ── Demo: analysis steps (API AnalysisStage order) ────────────────────
  const STAGES = [
    ['quality_check', 'Checking light & focus'],
    ['landmarks', 'Mapping facial landmarks'],
    ['face_geometry', 'Reading proportions'],
    ['skin_tone', 'Sampling skin tone'],
    ['recommendations', 'Curating your picks'],
    ['finalizing', 'Composing your Style DNA'],
  ];
  const stepsHtml = (active) => STAGES.map(([id, label], i) => {
    const state = i < active ? 'done' : i === active ? 'active' : 'pending';
    const marker = state === 'done' ? VY.icon('check') : String(i + 1);
    return `<li class="vy-steps__item" data-state="${state}"${state === 'active' ? ' aria-current="step"' : ''}><span class="vy-steps__marker" aria-hidden="true">${marker}</span><span>${label}<span class="vy-visually-hidden"> — ${state}</span></span></li>`;
  }).join('');
  let stepTimer;
  function runSteps() {
    clearInterval(stepTimer);
    let i = 0;
    const tick = () => {
      $('#demo-steps').innerHTML = stepsHtml(i);
      const pct = Math.round((Math.min(i, STAGES.length) / STAGES.length) * 100);
      $('#demo-progress').setAttribute('aria-valuenow', pct);
      $('#demo-progress .vy-progress__bar').style.setProperty('--vy-value', pct);
      $('#demo-steps-live').textContent = STAGES[i] ? STAGES[i][1] : 'Analysis complete';
      if (i++ >= STAGES.length) clearInterval(stepTimer);
    };
    tick();
    stepTimer = setInterval(tick, 1100);
  }
  $('#demo-steps-run').addEventListener('click', runSteps);
  runSteps();

  // ── Side-nav scrollspy ────────────────────────────────────────────────
  const links = $$('.sc-side__nav a');
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      links.forEach((a) => a.setAttribute('aria-current', String(a.getAttribute('href') === '#' + en.target.id)));
    });
  }, { rootMargin: '-30% 0px -65% 0px' });
  $$('.sc-section').forEach((s) => io.observe(s));

  // ── Playground ────────────────────────────────────────────────────────
  const btnLabel = (l) => `<span class="vy-btn__label">${esc(l)}</span>`;
  const COMPONENTS = {
    Button: {
      variants: ['primary', 'secondary', 'ghost', 'link'],
      states: ['default', 'loading', 'disabled', 'small', 'large'],
      label: 'Start scan',
      html: (v, s, l) => {
        const size = s === 'small' ? ' vy-btn--sm' : s === 'large' ? ' vy-btn--lg' : '';
        const attrs = s === 'loading' ? ' aria-busy="true" aria-disabled="true"' : s === 'disabled' ? ' disabled' : '';
        return `<button class="vy-btn vy-btn--${v}${size}" type="button"${attrs}>${btnLabel(l)}${s === 'loading' ? '<span class="vy-spinner" aria-hidden="true"></span>' : ''}</button>`;
      },
      jsx: (v, s, l) => `<Button variant="${v}"${s === 'small' ? ' size="sm"' : s === 'large' ? ' size="lg"' : ''}${s === 'loading' ? ' loading' : ''}${s === 'disabled' ? ' disabled' : ''}>\n  ${l}\n</Button>`,
    },
    Badge: {
      variants: ['neutral', 'accent', 'success', 'warning', 'danger', 'info', 'estimate'],
      states: ['default', 'with dot'],
      label: 'Estimate · 72%',
      html: (v, s, l) => `<span class="vy-badge${v === 'neutral' ? '' : ' vy-badge--' + v}">${s === 'with dot' ? '<span class="vy-badge__dot" aria-hidden="true"></span>' : ''}${esc(l)}</span>`,
      jsx: (v, s, l) => `<Badge tone="${v}"${s === 'with dot' ? ' dot' : ''}>${l}</Badge>`,
    },
    Card: {
      variants: ['default', 'raised', 'gilded'],
      states: ['default', 'interactive'],
      label: 'Your Style DNA',
      html: (v, s, l) => `<div class="vy-card${v === 'default' ? '' : ' vy-card--' + v}${s === 'interactive' ? ' vy-card--interactive' : ''}" style="width:min(22rem,90vw)"><p class="vy-overline">Report</p><h3 class="vy-card__title">${esc(l)}</h3><p class="vy-card__body">Oval · Neutral · Rose, Sage, Navy.</p><div class="vy-card__footer"><span class="vy-badge vy-badge--estimate">Estimate</span></div></div>`,
      jsx: (v, s, l) => `<Card variant="${v}"${s === 'interactive' ? ' interactive as="a" href="/report"' : ''}\n  eyebrow="Report" title="${l}"\n  footer={<EstimateBadge />}>\n  Oval · Neutral · Rose, Sage, Navy.\n</Card>`,
    },
    Input: {
      variants: ['text', 'email'],
      states: ['default', 'with hint', 'error', 'disabled'],
      label: 'Display name',
      html: (v, s, l) => {
        const desc = s === 'with hint' ? ' aria-describedby="h"' : s === 'error' ? ' aria-describedby="e" aria-invalid="true"' : '';
        return `<div class="vy-field" style="width:min(22rem,90vw)"><label class="vy-label" for="i">${esc(l)}</label><input class="vy-input" id="i" type="${v}"${desc}${s === 'disabled' ? ' disabled' : ''} placeholder="${v === 'email' ? 'name@example.com' : 'Tanya'}" />${s === 'with hint' ? '<p class="vy-hint" id="h">Shown on your report.</p>' : ''}${s === 'error' ? '<p class="vy-field__error" id="e" data-icon="alert">This field is required.</p>' : ''}</div>`;
      },
      jsx: (v, s, l) => `<Field label="${l}"${s === 'with hint' ? ' hint="Shown on your report."' : ''}${s === 'error' ? ' error="This field is required."' : ''}>\n  <Input type="${v}"${s === 'disabled' ? ' disabled' : ''} />\n</Field>`,
    },
    Select: {
      variants: ['budget', 'style'],
      states: ['default', 'disabled'],
      label: 'Budget',
      html: (v, s, l) => {
        const opts = v === 'budget' ? ['Low', 'Mid', 'High'] : ['Everyday', 'Minimal', 'Classic', 'Bold', 'Formal'];
        return `<div class="vy-field" style="width:min(22rem,90vw)"><label class="vy-label" for="s">${esc(l)}</label><div class="vy-select"><select class="vy-select__control" id="s"${s === 'disabled' ? ' disabled' : ''}>${opts.map((o) => `<option>${o}</option>`).join('')}</select></div></div>`;
      },
      jsx: (v, s, l) => `<Field label="${l}">\n  <Select${s === 'disabled' ? ' disabled' : ''} options={${v}Options} />\n</Field>`,
    },
    Alert: {
      variants: ['info', 'success', 'warning', 'danger'],
      states: ['default', 'title only'],
      label: 'Low light detected',
      html: (v, s, l) => `<div class="vy-alert${v === 'info' ? '' : ' vy-alert--' + v}" style="width:min(28rem,90vw)"><span class="vy-alert__icon" aria-hidden="true" data-icon="${{ info: 'info', success: 'check' }[v] || 'alert'}"></span><div><p class="vy-alert__title">${esc(l)}</p>${s === 'default' ? '<p class="vy-alert__body">Results may be less accurate.</p>' : ''}</div></div>`,
      jsx: (v, s, l) => `<Alert tone="${v}" title="${l}">${s === 'default' ? '\n  Results may be less accurate.\n' : ''}</Alert>`,
    },
    State: {
      variants: ['empty', 'success', 'error', 'info'],
      states: ['with action', 'no action'],
      label: 'No Style DNA yet',
      html: (v, s, l) => `<section class="vy-state vy-state--${v}"><span class="vy-state__icon" aria-hidden="true" data-icon="${{ empty: 'facet', success: 'check', error: 'alert', info: 'info' }[v]}"></span><h3 class="vy-state__title">${esc(l)}</h3><p class="vy-state__desc">One selfie in soft daylight is all it takes.</p>${s === 'with action' ? '<div class="vy-state__actions"><button class="vy-btn vy-btn--primary vy-btn--sm" type="button"><span class="vy-btn__label">Start scan</span></button></div>' : ''}</section>`,
      jsx: (v, s, l) => `<StateMessage kind="${v}" title="${l}"\n  description="One selfie in soft daylight is all it takes."${s === 'with action' ? '\n  actions={<Button size="sm">Start scan</Button>}' : ''} />`,
    },
    Modal: {
      variants: ['default', 'destructive'],
      states: ['open'],
      label: 'Before we look',
      html: (v, s, l) => `<dialog class="vy-modal" open aria-labelledby="mt"><div class="vy-modal__header"><h2 class="vy-modal__title" id="mt">${esc(l)}</h2><button class="vy-btn vy-btn--ghost vy-btn--sm vy-btn--icon" type="button" aria-label="Close" data-icon="close"></button></div><div class="vy-modal__body"><p>${v === 'destructive' ? 'This permanently deletes your account, analyses and any stored photos.' : 'We analyse your selfie to estimate face shape and skin tone. The photo is deleted right after.'}</p></div><div class="vy-modal__footer"><button class="vy-btn vy-btn--ghost" type="button"><span class="vy-btn__label">Cancel</span></button><button class="vy-btn ${v === 'destructive' ? 'vy-btn--secondary' : 'vy-btn--primary'}" type="button"><span class="vy-btn__label">${v === 'destructive' ? 'Delete' : 'I agree'}</span></button></div></dialog>`,
      jsx: (v, s, l) => `<Modal open={open} onClose={close} title="${l}"${v === 'destructive' ? ' dismissible={false}' : ''}\n  footer={<>\n    <Button variant="ghost" onClick={close}>Cancel</Button>\n    <Button${v === 'destructive' ? ' variant="secondary"' : ''}>${v === 'destructive' ? 'Delete' : 'I agree'}</Button>\n  </>}>\n  …\n</Modal>`,
    },
    NavBar: {
      variants: ['default'],
      states: ['closed', 'open (mobile)'],
      label: 'New scan',
      full: true,
      html: (v, s, l) => `<header class="vy-nav" data-open="${s !== 'closed'}"><nav class="vy-container vy-nav__inner" aria-label="Primary"><a href="#" class="vy-nav__brand" aria-label="VYSEL home" data-brand="wordmark"></a><button class="vy-btn vy-btn--ghost vy-btn--icon vy-nav__toggle" type="button" aria-label="Open menu" aria-expanded="${s !== 'closed'}" data-icon="${s === 'closed' ? 'menu' : 'close'}"></button><ul class="vy-nav__links"><li><a class="vy-nav__link" href="#" aria-current="page">Scan</a></li><li><a class="vy-nav__link" href="#">My Style DNA</a></li><li><a class="vy-nav__link" href="#">History</a></li></ul><div class="vy-nav__actions"><button class="vy-btn vy-btn--primary vy-btn--sm" type="button"><span class="vy-btn__label">${esc(l)}</span></button></div></nav></header>`,
      jsx: (v, s, l) => `<NavBar\n  links={[{ href: '/scan', label: 'Scan', current: true }, …]}\n  actions={<Button size="sm">${l}</Button>}\n  renderLink={({ className, href, children }) => <Link className={className} href={href}>{children}</Link>}\n/>`,
    },
    Steps: {
      variants: STAGES.map(([id]) => id),
      states: ['in progress'],
      label: '',
      html: (v) => `<ol class="vy-steps" aria-label="Analysis progress" style="width:min(22rem,90vw)">${stepsHtml(STAGES.findIndex(([id]) => id === v))}</ol>`,
      jsx: (v) => `<Steps items={STAGES.map((s, i) => ({\n  id: s.id, label: s.label,\n  state: i < idx('${v}') ? 'done' : i === idx('${v}') ? 'active' : 'pending',\n}))} />`,
    },
  };

  const form = $('#play-form');
  const compSel = $('#pg-component');
  compSel.innerHTML = Object.keys(COMPONENTS).map((k) => `<option>${k}</option>`).join('');
  const fillOptions = () => {
    const c = COMPONENTS[compSel.value];
    $('#pg-variant').innerHTML = c.variants.map((v) => `<option>${v}</option>`).join('');
    $('#pg-state').innerHTML = c.states.map((v) => `<option>${v}</option>`).join('');
    $('#pg-label').value = c.label;
    $('#pg-label').disabled = !c.label;
  };
  const frame = $('#pg-frame');
  let frameReady = false;
  function renderPlayground() {
    const c = COMPONENTS[compSel.value];
    const v = $('#pg-variant').value, s = $('#pg-state').value, l = $('#pg-label').value || c.label;
    const width = form.pgWidth.value;
    frame.style.width = width === '100%' ? '100%' : width + 'px';
    $('#pg-code').textContent = c.jsx(v, s, l);
    if (frameReady) {
      frame.contentWindow.postMessage({ type: 'vy-preview', html: c.html(v, s, l), theme: form.pgTheme.value, motion: html.dataset.motion, full: !!c.full }, '*');
    }
  }
  window.addEventListener('message', (e) => {
    if (e.data && e.data.type === 'vy-preview-ready') { frameReady = true; renderPlayground(); }
  });
  compSel.addEventListener('change', () => { fillOptions(); renderPlayground(); });
  form.addEventListener('input', (e) => { if (e.target !== compSel) renderPlayground(); });
  form.addEventListener('submit', (e) => e.preventDefault());
  $('#pg-copy').addEventListener('click', async function () {
    try { await navigator.clipboard.writeText($('#pg-code').textContent); } catch { /* file:// may block clipboard */ }
    const label = this.querySelector('.vy-btn__label');
    label.textContent = 'Copied';
    setTimeout(() => { label.textContent = 'Copy'; }, 1400);
  });

  // Deep links: ?theme=porcelain&motion=reduced
  const params = new URLSearchParams(location.search);
  ['theme', 'motion'].forEach((k) => {
    const el = params.get(k) && $(`input[name="${k}"][value="${params.get(k)}"]`);
    if (el) el.checked = true;
  });

  fillOptions();
  applyGlobal();
})();
