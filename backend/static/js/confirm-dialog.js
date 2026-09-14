(function () {
  var dialog, titleEl, msgEl, goEl, cancelEl;
  var pending = null;

  function build() {
    dialog = document.getElementById('confirmDialog');
    if (!dialog) return false;
    titleEl = document.getElementById('confirmTitle');
    msgEl = document.getElementById('confirmMessage');
    goEl = document.getElementById('confirmGo');
    cancelEl = document.getElementById('confirmCancel');

    goEl.addEventListener('click', function () {
      var el = pending;
      close();
      if (!el) return;
      el.dataset.confirmed = '1';
      if (el.tagName === 'FORM') {
        if (typeof el.requestSubmit === 'function') el.requestSubmit();
        else el.submit();
      } else {
        el.click();
      }
    });

    cancelEl.addEventListener('click', close);
    dialog.querySelector('.confirm-backdrop').addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !dialog.hidden) close();
    });
    return true;
  }

  function open(el) {
    pending = el;
    titleEl.textContent = el.dataset.confirm || 'Are you sure?';
    msgEl.textContent = el.dataset.confirmDetail || '';
    msgEl.hidden = !el.dataset.confirmDetail;
    goEl.textContent = el.dataset.confirmLabel || 'Confirm';
    dialog.dataset.tone = el.dataset.confirmTone || 'default';
    dialog.hidden = false;
    goEl.focus();
  }

  function close() {
    dialog.hidden = true;
    pending = null;
  }

  function intercept(e) {
    var el = e.target.closest('[data-confirm]');
    if (!el) return;
    if (el.dataset.confirmed === '1') {
      delete el.dataset.confirmed;
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    open(el);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!build()) return;
    document.addEventListener('submit', intercept, true);
    document.addEventListener('click', function (e) {
      var el = e.target.closest('[data-confirm]');
      if (el && el.tagName !== 'FORM') intercept(e);
    }, true);
  });
})();
