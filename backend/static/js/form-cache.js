/* Keeps what you typed if you wander off and come back.
 *
 * This replaces "Save as Draft", which needed a deliberate click and created a
 * half-finished Application row the office then had to look at. Here nothing is
 * sent to the server: answers are written to this browser's localStorage as you
 * type, put back when you return, and thrown away once the form is submitted.
 *
 * Opt a form in with data-cache="<a name unique to that form>". The name is the
 * storage key, so changing it abandons anything already saved under the old one.
 *
 * Files are the one thing that cannot come back. A browser will not let a page
 * put a file back into a file input — that would let any site re-upload
 * whatever you last chose — so uploads have to be picked again. The form says
 * so rather than letting anyone assume otherwise.
 */
(function () {
  'use strict';

  var form = document.querySelector('form[data-cache]');
  if (!form) return;

  var store;
  try {
    store = window.localStorage;
    store.setItem('srms:probe', '1');
    store.removeItem('srms:probe');
  } catch (e) {
    return;                 // private mode, or storage disabled — no cache, no error
  }

  var KEY = 'srms:form:' + form.dataset.cache;
  var status = document.getElementById('cacheStatus');

  // Passwords are never written down. Hidden fields carry the CSRF token, which
  // is per-session and must not be restored from an older one. Files cannot be
  // restored at all.
  var SKIP_TYPES = ['file', 'password', 'hidden', 'submit', 'button', 'reset'];

  function cacheable(el) {
    return el.name &&
           SKIP_TYPES.indexOf(el.type) === -1 &&
           !el.disabled &&
           el.dataset.noCache === undefined;
  }

  function fields() {
    return Array.prototype.filter.call(
      form.querySelectorAll('input, select, textarea'), cacheable);
  }

  function collect() {
    var data = {};
    fields().forEach(function (el) {
      if (el.type === 'checkbox') {
        data[el.name] = el.checked;
      } else if (el.type === 'radio') {
        if (el.checked) data[el.name] = el.value;
      } else {
        data[el.name] = el.value;
      }
    });
    return data;
  }

  function apply(data) {
    var restored = 0;
    fields().forEach(function (el) {
      if (!(el.name in data)) return;
      var saved = data[el.name];
      if (el.type === 'checkbox') {
        if (el.checked !== saved) { el.checked = saved; restored++; }
      } else if (el.type === 'radio') {
        if (el.value === saved && !el.checked) { el.checked = true; restored++; }
      } else if (saved !== '' && el.value !== saved) {
        el.value = saved;
        restored++;
      }
    });
    return restored;
  }

  function say(message) {
    if (status) status.textContent = message;
  }

  function save() {
    try {
      store.setItem(KEY, JSON.stringify({ at: Date.now(), data: collect() }));
      say('Your answers are kept on this device. Uploads still need choosing again.');
    } catch (e) {
      say('');              // quota full — not worth interrupting anyone over
    }
  }

  function restore() {
    var raw = store.getItem(KEY);
    if (!raw) return;
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      store.removeItem(KEY);
      return;
    }
    var restored = apply(parsed.data || {});
    if (!restored) return;

    say('Picked up where you left off. Uploads still need choosing again.');
    // Anything driven by a field's value — the eligibility panel here — has to
    // recompute off what was just put back.
    form.dispatchEvent(new Event('cache:restored'));
  }

  var pending;
  function scheduleSave() {
    clearTimeout(pending);
    pending = setTimeout(save, 400);
  }

  form.addEventListener('input', scheduleSave);
  form.addEventListener('change', scheduleSave);

  // Leaving the tab is exactly the moment worth catching, and the debounce may
  // not have fired yet.
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') { clearTimeout(pending); save(); }
  });

  // Submitted answers live on the server now; keeping a copy would only refill
  // a form the applicant has finished with.
  form.addEventListener('submit', function () {
    clearTimeout(pending);
    store.removeItem(KEY);
  });

  restore();
})();
