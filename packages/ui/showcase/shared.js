/* Shared by index.html and preview.html. Vanilla JS mirrors of the React behaviours. */
(function () {
  // Keep in sync with packages/ui/src/components/Icon.tsx (checked by scripts/validate-design-system.mjs).
  const ICONS = {
    check: 'M5 12.5l4.5 4.5L19 7.5',
    close: 'M6 6l12 12M18 6L6 18',
    alert: 'M12 8v5m0 3.5v.01M10.3 3.9L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
    info: 'M12 11v6m0-9.5v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    facet: 'M12 3l5 9-5 9-5-9z',
    menu: 'M4 7h16M4 12h16M4 17h16',
    camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 16.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
    arrowRight: 'M5 12h14m-5-5l5 5-5 5',
  };

  const icon = (name) =>
    `<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${ICONS[name]}"/></svg>`;

  const wordmark = () => {
    const b = window.VYSEL_BRAND.wordmark;
    return `<svg viewBox="${b.viewBox}" fill="currentColor" aria-hidden="true" focusable="false"><path d="${b.d}"/></svg>`;
  };

  function hydrate(root) {
    root.querySelectorAll('[data-icon]').forEach((el) => {
      if (el.dataset.hydrated) return;
      el.insertAdjacentHTML('afterbegin', icon(el.dataset.icon));
      el.dataset.hydrated = '1';
    });
    root.querySelectorAll('[data-brand="wordmark"]').forEach((el) => {
      if (!el.dataset.hydrated) { el.innerHTML = wordmark(); el.dataset.hydrated = '1'; }
    });

    // Nav disclosure
    root.querySelectorAll('.vy-nav__toggle').forEach((btn) => {
      btn.addEventListener('click', () => {
        const nav = btn.closest('.vy-nav');
        const open = nav.dataset.open !== 'true';
        nav.dataset.open = String(open);
        btn.setAttribute('aria-expanded', String(open));
        btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
        btn.querySelector('svg').outerHTML = icon(open ? 'close' : 'menu');
      });
    });

    // Tabs: roving tabindex + arrows/Home/End
    root.querySelectorAll('[data-tabs]').forEach((tabs) => {
      const list = tabs.querySelector('[role="tablist"]');
      const all = [...list.querySelectorAll('[role="tab"]')];
      const select = (tab, focus) => {
        all.forEach((t) => {
          const on = t === tab;
          t.setAttribute('aria-selected', String(on));
          t.tabIndex = on ? 0 : -1;
          tabs.querySelector('#' + t.getAttribute('aria-controls')).hidden = !on;
        });
        if (focus) tab.focus();
      };
      all.forEach((t) => t.addEventListener('click', () => select(t)));
      list.addEventListener('keydown', (e) => {
        const i = all.indexOf(document.activeElement);
        const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: all.length - 1 }[e.key];
        if (next === undefined || i < 0) return;
        e.preventDefault();
        select(all[(next + all.length) % all.length], true);
      });
    });

    // Modals: native dialog; backdrop click closes.
    root.querySelectorAll('[data-open-modal]').forEach((btn) => {
      btn.addEventListener('click', () => document.getElementById(btn.dataset.openModal).showModal());
    });
    root.querySelectorAll('dialog.vy-modal').forEach((d) => {
      d.addEventListener('click', (e) => { if (e.target === d) d.close(); });
      d.querySelectorAll('[data-close-modal]').forEach((b) => b.addEventListener('click', () => d.close()));
    });
  }

  window.VY = { icon, wordmark, hydrate };
})();
