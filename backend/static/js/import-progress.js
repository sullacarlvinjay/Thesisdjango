(function () {
  'use strict';

  var box = document.getElementById('importProgress');
  if (!box || !box.dataset.statusUrl) { return; }

  var url = box.dataset.statusUrl;
  var message = box.querySelector('[data-role="message"]');
  var tries = 0;
  var LIMIT = 150;

  function giveUp() {
    box.classList.remove('import-progress');
    box.classList.replace('page-alert-info', 'page-alert-warn');
    if (message) {
      message.textContent = 'This import is taking longer than expected. '
        + 'Reload the page to see whether it finished.';
    }
  }

  function again() {
    tries += 1;
    if (tries < LIMIT) { window.setTimeout(check, 2000); } else { giveUp(); }
  }

  function check() {
    window.fetch(url, {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    }).then(function (response) {
      return response.ok ? response.json() : null;
    }).then(function (data) {
      if (data && data.finished) { window.location.reload(); } else { again(); }
    }).catch(again);
  }

  window.setTimeout(check, 1500);
}());
