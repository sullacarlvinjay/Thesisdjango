/* The landing page's behaviour: one dialog per scholarship, and the navbar's
 * two jump links.
 *
 * Bound once on the document rather than once per card, so ten cards and ten
 * dialogs cost one listener and the template carries no onclick= attributes.
 * A card is a button as far as the keyboard is concerned — Enter and Space open
 * it, Escape closes whatever is open — which is why the markup gives each one
 * role="button" and a tab stop.
 */
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

  /* --- The navbar's jump links -------------------------------------------
   *
   * The page is a `mandatory` scroll-snap container, and Chrome cancels a
   * smooth scroll inside one: the snap re-targets mid-animation and the page
   * simply never moves. That is why `scroll-behavior: smooth` was removed from
   * the stylesheet, and why the links landed with a jolt afterwards.
   *
   * So the snapping is lifted for the length of the animation and put back the
   * moment the page settles. It settles exactly on the snap point the link was
   * aiming at — scroll-padding-top is what the navbar's height is subtracted
   * for here — so restoring the snap moves nothing.
   *
   * None of this is load-bearing. With scripting off, on a browser without
   * smooth scrolling, or for a reader who has asked for less motion, the
   * anchor is left alone and jumps straight there the way it always did.
   */
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

    // Some browsers report smooth scrolling and then do nothing with it —
    // an automation profile with animations switched off is the usual one.
    // Having taken the anchor's own jump away, we owe the reader the landing:
    // if the page has not begun to move by now, put it there outright.
    setTimeout(function () {
      if (token === jump && Math.abs(top - from) > 2
          && Math.abs(window.pageYOffset - from) < 2) {
        window.scrollTo(0, top);
        done();
      }
    }, 180);

    // scrollend says the animation is over; Safari has not shipped it, and a
    // scroll that was already in place never fires it at all, so a timer backs
    // it up and whichever arrives first clears the other.
    var timer = setTimeout(done, 1200);
    function done() {
      clearTimeout(timer);
      window.removeEventListener('scrollend', done);
      if (token !== jump) return;    // a newer jump owns the snap now
      root.classList.remove('is-jumping');
    }
    window.addEventListener('scrollend', done);

    // Written rather than assigned: setting location.hash would scroll again,
    // instantly, on top of the animation we just started.
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

    // The backdrop itself, never the dialog sitting on top of it.
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
    e.preventDefault();     // Space would otherwise scroll the page
    openModal(card.getAttribute('data-scholarship'));
  });
})();
