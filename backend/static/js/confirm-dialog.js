(function () {
  var dialog, titleEl, msgEl, goEl, cancelEl, iconEl, consequenceEl;
  var pending = null;
  var lastFocus = null;

  function build() {
    dialog = document.getElementById('confirmDialog');
    if (!dialog) return false;
    titleEl = document.getElementById('confirmTitle');
    msgEl = document.getElementById('confirmMessage');
    goEl = document.getElementById('confirmGo');
    cancelEl = document.getElementById('confirmCancel');
    iconEl = document.getElementById('confirmIcon');
    consequenceEl = document.getElementById('confirmConsequence');

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
    lastFocus = document.activeElement;
    titleEl.textContent = el.dataset.confirm || 'Are you sure?';
    msgEl.textContent = el.dataset.confirmDetail || '';
    msgEl.hidden = !el.dataset.confirmDetail;

    var consequence = el.dataset.confirmConsequence || '';
    if (consequenceEl) {
      consequenceEl.textContent = consequence;
      consequenceEl.hidden = !consequence;
    }

    goEl.textContent = el.dataset.confirmLabel || 'Confirm';
    var tone = el.dataset.confirmTone || 'default';
    dialog.dataset.tone = tone;
    if (iconEl) iconEl.hidden = tone === 'default';
    dialog.hidden = false;

    /* The cancel button takes focus, not the one that does the thing. A
       hazard warning whose dangerous button is already focused is one
       stray Enter away from not being a warning at all. */
    cancelEl.focus();
  }

  function close() {
    dialog.hidden = true;
    pending = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
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
