/* The light/dark preference, read before the page is painted.
 *
 * This has to run in <head> as a plain blocking script rather than after the
 * DOM is ready: the class it sets is what decides which colour tokens srms.css
 * hands out, and a page that picks them up late flashes white before switching.
 * Deferring it would defeat the whole point.
 *
 * The preference itself is written by the portals' theme toggle. Nothing stored
 * means follow the operating system.
 */
(function () {
  'use strict';

  var stored = null;
  try {
    stored = window.localStorage.getItem('theme');
  } catch (e) {
    stored = null;          // private mode, or storage disabled — follow the OS
  }

  var dark = stored === 'dark' ||
             (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);

  if (dark) document.documentElement.classList.add('dark');
})();
