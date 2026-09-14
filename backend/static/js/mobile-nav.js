(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var sidebar = document.getElementById('appSidebar');
    var toggle = document.getElementById('sidebarToggle');
    var backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar || !toggle || !backdrop) return;

    var desktop = window.matchMedia('(min-width: 1024px)');

    function open() {
      sidebar.classList.add('is-open');
      backdrop.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
    }

    function close() {
      sidebar.classList.remove('is-open');
      backdrop.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }

    toggle.addEventListener('click', function () {
      if (sidebar.classList.contains('is-open')) close();
      else open();
    });

    backdrop.addEventListener('click', close);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar.classList.contains('is-open')) close();
    });

    sidebar.addEventListener('click', function (e) {
      if (e.target.closest('a')) close();
    });

    var onChange = function (e) { if (e.matches) close(); };
    if (desktop.addEventListener) desktop.addEventListener('change', onChange);
    else desktop.addListener(onChange);
  });
})();
