/* The landing page's behaviour: one dialog per scholarship.
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

  document.addEventListener('click', function (e) {
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
