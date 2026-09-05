// Open a dialog that is already on the page.
//
// A button carrying data-preview-open="<id>" opens the .modal-overlay with that
// id; anything with data-preview-close inside one closes it, as do Escape and a
// click on the backdrop — which is what every other dialog here does.
//
// Driven entirely by attributes, so a page adds the button and the overlay and
// nothing else. Used where the dialog's contents are rendered by the server
// rather than assembled in JavaScript: the TES report preview, and the link
// request review form, whose imported-row checkboxes are built per request and
// would be miserable to rebuild from data attributes.
(function () {
  var openers = document.querySelectorAll('[data-preview-open]');
  if (!openers.length) return;

  function close(overlay) {
    overlay.classList.remove('open');
  }

  function closeAll() {
    document.querySelectorAll('.modal-overlay.open').forEach(close);
  }

  openers.forEach(function (button) {
    button.addEventListener('click', function () {
      var overlay = document.getElementById(button.getAttribute('data-preview-open'));
      if (overlay) overlay.classList.add('open');
    });
  });

  document.querySelectorAll('[data-preview-close]').forEach(function (button) {
    button.addEventListener('click', function () {
      var overlay = button.closest('.modal-overlay');
      if (overlay) close(overlay);
    });
  });

  document.querySelectorAll('.modal-overlay[data-preview]').forEach(function (overlay) {
    // Only the backdrop itself, never a click that started inside the sheet.
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) close(overlay);
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeAll();
  });
})();
