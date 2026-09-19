(function () {
  'use strict';

  var MIN_VISIBLE = 300;
  var MAX_WAIT    = 5000;

  var root = document.documentElement;
  var startedAt = Date.now();
  var revealed = false;

  root.classList.add('is-loading');

  function reveal() {
    if (revealed) return;
    revealed = true;
    root.classList.remove('is-loading');

    setTimeout(function () {
      var el = document.querySelector('.page-loader, .page-skeleton');
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }, 600);
  }

  function revealWhenSeen() {
    setTimeout(reveal, Math.max(0, MIN_VISIBLE - (Date.now() - startedAt)));
  }

  function whenFontsReady(next) {
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(next, next);
    } else {
      next();
    }
  }

  function onLoaded() { whenFontsReady(revealWhenSeen); }

  if (document.readyState === 'complete') onLoaded();
  else window.addEventListener('load', onLoaded);

  setTimeout(reveal, MAX_WAIT);
})();
