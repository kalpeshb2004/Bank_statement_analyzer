(function () {
  // Koi bhi request 401 de to login page pe bhej do
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function (...args) {
    const res = await nativeFetch(...args);
    if (res.status === 401) {
      window.location.href = '/login';
    }
    return res;
  };

  async function init() {
    const chip = document.getElementById('user-chip');
    const btn = document.getElementById('user-btn');
    const menu = document.getElementById('user-menu');
    if (!chip) return;

    const res = await fetch('/api/me');
    if (!res.ok) return; // 401 pe upar wala code redirect kar dega

    const user = await res.json();
    const name = (user.name || '').trim();
    document.getElementById('user-avatar').textContent = (name[0] || '?').toUpperCase();
    document.getElementById('user-name').textContent = name.split(' ')[0] || 'Account';
    document.getElementById('user-email').textContent = user.email;
    chip.hidden = false;

    function setMenu(open) {
      menu.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
    }
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      setMenu(menu.hidden);
    });
    document.addEventListener('click', () => setMenu(false));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') setMenu(false);
    });

    document.getElementById('logout-btn').addEventListener('click', async () => {
      await fetch('/api/logout', { method: 'POST' });
      window.location.href = '/login';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();