/* The skeleton loading screen.
 *
 * Marks the document as loading before the first paint, then takes the
 * placeholder down once the real page can stand on its own. Load it in <head>
 * as a plain blocking script: the class has to land before anything is painted,
 * or the reader sees exactly the half-dressed page the screen exists to hide.
 * On this site that page is worth hiding — the layout comes from the Tailwind
 * CDN, which is JavaScript, so until it has run the markup is unstyled.
 *
 * It waits for the page to finish loading AND for the webfont to arrive, so the
 * reveal is not immediately followed by every line of text reflowing. Two
 * guards keep the wait sane: MIN_VISIBLE, because a placeholder that flickers
 * for 80ms reads as a glitch rather than a loading screen, and MAX_WAIT,
 * because a CDN that never answers must not hold the page hostage.
 *
 * The markup lives in the template — it is structure — and the looks are in
 * section 16 of srms.css. Include this script only on a page that carries a
 * .page-skeleton element, since .is-loading also holds the scroll still.
 */
(function () {
  'use strict';

  var MIN_VISIBLE = 300;    // ms the screen stays up even when loading is instant
  var MAX_WAIT    = 5000;   // ms after which the page is revealed regardless

  var root = document.documentElement;
  var startedAt = Date.now();
  var revealed = false;

  root.classList.add('is-loading');

  function reveal() {
    if (revealed) return;
    revealed = true;
    root.classList.remove('is-loading');

    /* The placeholder fades out in CSS, but a tab that is not being drawn -- a
       background tab, a phone that has locked -- never advances that
       transition, so the node itself is what actually goes. A shade later than
       the fade, so the fade is what you see when the page is on screen. */
    setTimeout(function () {
      var el = document.querySelector('.page-skeleton');
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }, 400);
  }

  /* Never blink: hold the screen for the rest of MIN_VISIBLE if the page beat
     it there. */
  function revealWhenSeen() {
    setTimeout(reveal, Math.max(0, MIN_VISIBLE - (Date.now() - startedAt)));
  }

  function whenFontsReady(next) {
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(next, next);
    } else {
      next();               // an older browser simply reveals a moment earlier
    }
  }

  function onLoaded() { whenFontsReady(revealWhenSeen); }

  if (document.readyState === 'complete') onLoaded();
  else window.addEventListener('load', onLoaded);

  setTimeout(reveal, MAX_WAIT);
})();
