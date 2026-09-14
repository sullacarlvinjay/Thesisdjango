(function () {
  'use strict';

  function openModal(id) {
    var el = document.getElementById('modal-' + id);
    if (el) el.classList.add('open');
  }

  function closeModal(id) {
    var el = document.getElementById('modal-' + id);
    if (el) el.classList.remove('open');
  }

  function closeAll() {
    var open = document.querySelectorAll('.modal-overlay.open');
    for (var i = 0; i < open.length; i++) open[i].classList.remove('open');
  }

  var root = document.documentElement;
  var canAnimate = 'scrollBehavior' in root.style
                && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var jump = 0;

  function jumpTo(target, hash) {
    var nav = document.querySelector('.landing-nav');
    var top = target.getBoundingClientRect().top + window.pageYOffset
            - (nav ? nav.getBoundingClientRect().height : 0);

    top = Math.max(0, Math.round(top));
    var from = window.pageYOffset;

    var token = ++jump;
    root.classList.add('is-jumping');
    window.scrollTo({ top: top, behavior: 'smooth' });

    setTimeout(function () {
      if (token === jump && Math.abs(top - from) > 2
          && Math.abs(window.pageYOffset - from) < 2) {
        window.scrollTo(0, top);
        done();
      }
    }, 180);

    var timer = setTimeout(done, 1200);
    function done() {
      clearTimeout(timer);
      window.removeEventListener('scrollend', done);
      if (token !== jump) return;
      root.classList.remove('is-jumping');
    }
    window.addEventListener('scrollend', done);

    if (window.history && history.replaceState) history.replaceState(null, '', hash);
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('.landing-jump-link');
    if (link && canAnimate) {
      var hash = link.getAttribute('href') || '';
      var target = hash.charAt(0) === '#' && document.getElementById(hash.slice(1));
      if (target) {
        e.preventDefault();
        jumpTo(target, hash);
        return;
      }
    }

    var closer = e.target.closest('[data-close-modal]');
    if (closer) {
      closeModal(closer.getAttribute('data-close-modal'));
      return;
    }

    if (e.target.classList && e.target.classList.contains('modal-overlay')) {
      e.target.classList.remove('open');
      return;
    }

    var card = e.target.closest('[data-scholarship]');
    if (card) openModal(card.getAttribute('data-scholarship'));
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAll();
      return;
    }
    if (e.key !== 'Enter' && e.key !== ' ') return;

    var card = e.target.closest && e.target.closest('[data-scholarship]');
    if (!card) return;
    e.preventDefault();
    openModal(card.getAttribute('data-scholarship'));
  });
})();
