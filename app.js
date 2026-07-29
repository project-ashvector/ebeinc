(() => {
  const menuButton = document.querySelector('.menu-button');
  const nav = document.querySelector('.site-nav');
  menuButton?.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(open));
  });
  nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    nav.classList.remove('open');
    menuButton?.setAttribute('aria-expanded', 'false');
  }));

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

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveals = document.querySelectorAll('.reveal');
  if (prefersReduced || !('IntersectionObserver' in window)) {
    reveals.forEach(el => el.classList.add('visible'));
  } else {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });
    reveals.forEach(el => observer.observe(el));
  }
})();
