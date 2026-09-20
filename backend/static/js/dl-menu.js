(function () {
  /* Bound once, whatever a template does. This file was included a second
     time by the archive pages on top of base.html's copy, so every button
     carried two click handlers: one opened the menu, the other closed it
     again, and the scholarship-type picker did nothing at all. */
  if (window.__dlMenuBound) return;
  window.__dlMenuBound = true;

  var buttons = document.querySelectorAll('[data-dl-menu]');
  if (!buttons.length) return;

  function closeAll(except) {
    document.querySelectorAll('.dl-menu.is-open').forEach(function (menu) {
      if (menu === except) return;
      menu.classList.remove('is-open');
      var owner = document.querySelector('[data-dl-menu="' + menu.id + '"]');
      if (owner) owner.setAttribute('aria-expanded', 'false');
    });
  }

  buttons.forEach(function (button) {
    button.setAttribute('aria-expanded', 'false');
    button.addEventListener('click', function (event) {
      event.stopPropagation();
      var menu = document.getElementById(button.getAttribute('data-dl-menu'));
      if (!menu) return;
      closeAll(menu);
      var open = menu.classList.toggle('is-open');
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });

  document.addEventListener('click', function (event) {
    if (event.target.closest && event.target.closest('.dl-menu')) return;
    closeAll();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeAll();
  });
})();
