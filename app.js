(() => {
  const githubProjectPath = '/ebeinc/';
  const rootPath = window.location.hostname.endsWith('github.io') ? githubProjectPath : '/';
  const validViews = new Set(['hub', 'projects', 'capabilities', 'music', 'about', 'contact', 'resume']);
  const titles = {
    hub: 'EBE INC | Creative Technology Hub',
    projects: 'Projects | EBE INC',
    capabilities: 'Capabilities | EBE INC',
    music: 'Music | EBE INC · Ebmarah',
    about: 'About | EBE INC',
    contact: 'Contact | EBE INC',
    resume: 'Cody Richenberg Résumé | EBE INC'
  };

  // Remove /index.html, hashes, query strings, and old page paths from the visible address.
  if (window.location.pathname !== rootPath || window.location.search || window.location.hash) {
    window.history.replaceState({ ebeView: 'hub' }, '', rootPath);
  }

  const menuButton = document.querySelector('.menu-button');
  const menuLabel = menuButton?.querySelector('.sr-only');
  const nav = document.querySelector('.site-nav');
  const navBackdrop = document.querySelector('.nav-backdrop');
  const panels = [...document.querySelectorAll('[data-view-panel]')];
  const viewControls = [...document.querySelectorAll('[data-view]')];
  const navTabs = [...document.querySelectorAll('.nav-tab[data-view]')];

  const setMenuState = open => {
    nav?.classList.toggle('open', open);
    document.body.classList.toggle('nav-open', open);
    menuButton?.setAttribute('aria-expanded', String(open));
    navBackdrop?.setAttribute('tabindex', open ? '0' : '-1');
    if (menuLabel) menuLabel.textContent = open ? 'Close menu' : 'Open menu';
  };

  const closeMenu = ({ returnFocus = false } = {}) => {
    const wasOpen = nav?.classList.contains('open');
    setMenuState(false);
    if (returnFocus && wasOpen) menuButton?.focus();
  };

  menuButton?.addEventListener('click', () => {
    const open = !nav?.classList.contains('open');
    setMenuState(open);
    if (open) requestAnimationFrame(() => navTabs[0]?.focus());
  });

  navBackdrop?.addEventListener('click', () => closeMenu({ returnFocus: true }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && nav?.classList.contains('open')) {
      closeMenu({ returnFocus: true });
    }
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 980) closeMenu();
  });

  let revealObserver;
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!prefersReduced && 'IntersectionObserver' in window) {
    revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });
  }

  const activateReveals = panel => {
    const reveals = panel.querySelectorAll('.reveal:not(.visible)');
    if (prefersReduced || !revealObserver) {
      reveals.forEach(el => el.classList.add('visible'));
    } else {
      reveals.forEach(el => revealObserver.observe(el));
    }
  };

  const showView = (requested, options = {}) => {
    const view = validViews.has(requested) ? requested : 'hub';
    const { scroll = true, focus = false } = options;

    panels.forEach(panel => {
      const active = panel.dataset.viewPanel === view;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
      panel.setAttribute('aria-hidden', String(!active));
    });

    navTabs.forEach(tab => {
      if (tab.dataset.view === view) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    });

    document.body.dataset.activeView = view;
    document.title = titles[view] || titles.hub;
    sessionStorage.setItem('ebe-active-view', view);
    window.history.replaceState({ ebeView: view }, '', rootPath);
    closeMenu();

    const panel = document.querySelector(`[data-view-panel="${view}"]`);
    if (panel) activateReveals(panel);
    if (scroll) window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
    if (focus && panel) {
      const heading = panel.querySelector('h1, h2');
      if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
    }
  };

  viewControls.forEach(control => {
    control.addEventListener('click', () => showView(control.dataset.view, { focus: false }));
  });

  document.querySelectorAll('[data-scroll-target]').forEach(control => {
    control.addEventListener('click', () => {
      showView('hub', { scroll: false });
      requestAnimationFrame(() => {
        document.getElementById(control.dataset.scrollTarget)?.scrollIntoView({
          behavior: prefersReduced ? 'auto' : 'smooth', block: 'start'
        });
      });
    });
  });

  document.querySelector('[data-scroll-top]')?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
  });

  document.querySelector('[data-skip-main]')?.addEventListener('click', () => {
    const active = document.querySelector('[data-view-panel]:not([hidden])');
    const target = active?.querySelector('h1, h2') || document.getElementById('main');
    if (target) {
      target.setAttribute('tabindex', '-1');
      target.focus();
    }
  });

  const filters = [...document.querySelectorAll('.filter')];
  const cards = [...document.querySelectorAll('.project-card')];
  filters.forEach(button => button.addEventListener('click', () => {
    filters.forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    const filter = button.dataset.filter;
    cards.forEach(card => {
      const categories = (card.dataset.categories || '').split(/\s+/);
      card.hidden = filter !== 'all' && !categories.includes(filter);
    });
  }));

  const clearPrintMode = () => document.body.classList.remove('printing-resume');
  document.querySelector('[data-print-resume]')?.addEventListener('click', () => {
    showView('resume', { scroll: false });
    document.body.classList.add('printing-resume');
    setTimeout(() => window.print(), 40);
  });
  window.addEventListener('afterprint', clearPrintMode);

  const initial = validViews.has(history.state?.ebeView)
    ? history.state.ebeView
    : (validViews.has(sessionStorage.getItem('ebe-active-view')) ? sessionStorage.getItem('ebe-active-view') : 'hub');
  showView(initial, { scroll: false });
})();
