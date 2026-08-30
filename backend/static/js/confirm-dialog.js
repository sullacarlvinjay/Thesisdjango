/* In-page replacement for window.confirm().
 *
 * Chrome prefixes the native dialog with "127.0.0.1:8000 says…", it ignores the
 * page's dark mode, and it cannot say which scholar is about to be deleted in
 * anything but plain text. This does the same job in the portal's own styling.
 *
 * Mark up the trigger instead of writing an onsubmit handler:
 *
 *   <form data-confirm="Delete the 25-1 CHED import?"
 *         data-confirm-detail="The 12 scholars it added go with it."
 *         data-confirm-tone="danger"
 *         data-confirm-label="Delete">
 *
 * Works on a <form> (intercepts submit) or on a button/link (intercepts click).
 * Both are delegated from the document, so markup rendered later still works.
 * With JavaScript off nothing intercepts and the action proceeds — the same
 * failure mode the native confirm had.
 */
(function () {
  var dialog, titleEl, msgEl, goEl, cancelEl;
  var pending = null;                 // the element we will re-fire on confirm

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
      // Marked so the delegated handlers below let it through this time.
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
    if (el.dataset.confirmed === '1') {        // second pass, let it through
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
      // Forms are handled on submit; a button inside one must not fire twice.
      var el = e.target.closest('[data-confirm]');
      if (el && el.tagName !== 'FORM') intercept(e);
    }, true);
  });
})();
