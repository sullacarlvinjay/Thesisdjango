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
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) close(overlay);
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    var doc = document.getElementById('docViewer');
    if (doc && !doc.hidden) return;
    closeAll();
  });
})();
