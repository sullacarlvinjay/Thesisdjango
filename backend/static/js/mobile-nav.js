/* The sidebar drawer, below the lg breakpoint.
 *
 * Above lg the sidebar is part of the layout and this script does nothing. Below
 * it the aside leaves the flow and sits off-canvas, so without a way to pull it
 * back there is no navigation at all on a phone — which is what every office
 * page used to offer, the sidebar being simply display:none there.
 *
 * Open state is one class on the aside; the looks are in srms.css. Closing is
 * deliberately generous — the backdrop, Escape, following any link, and growing
 * the window past the breakpoint all count — because a drawer you cannot
 * dismiss is worse than no drawer.
 */
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

    // Following a link navigates away; closing first stops the drawer flashing
    // over the new page on a slow connection.
    sidebar.addEventListener('click', function (e) {
      if (e.target.closest('a')) close();
    });

    // Rotating a phone, or dragging a desktop window wider, must not leave the
    // body scroll-locked behind a drawer that is no longer on screen.
    var onChange = function (e) { if (e.matches) close(); };
    if (desktop.addEventListener) desktop.addEventListener('change', onChange);
    else desktop.addListener(onChange);       // Safari < 14
  });
})();
