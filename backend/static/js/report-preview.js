// Report preview: show the exact rows a report will export, before exporting.
//
// The office generates a workbook it then signs and submits, and until now the
// only way to see what was in it was to download it and open Excel. A button
// carrying data-preview-open="<id>" opens the .modal-overlay with that id, so
// the rows can be read on screen first.
//
// Driven entirely by attributes, so any page that wants a preview adds the
// button and the overlay and nothing else. Escape and a click on the backdrop
// close it, which is what every other dialog in this system does.
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
