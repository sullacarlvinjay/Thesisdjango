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
    return;
  }

  var KEY = 'srms:form:' + form.dataset.cache;
  var status = document.getElementById('cacheStatus');

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
      say('');
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
    form.dispatchEvent(new Event('cache:restored'));
  }

  var pending;
  function scheduleSave() {
    clearTimeout(pending);
    pending = setTimeout(save, 400);
  }

  form.addEventListener('input', scheduleSave);
  form.addEventListener('change', scheduleSave);

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') { clearTimeout(pending); save(); }
  });

  form.addEventListener('submit', function () {
    clearTimeout(pending);
    store.removeItem(KEY);
  });

  restore();
})();
