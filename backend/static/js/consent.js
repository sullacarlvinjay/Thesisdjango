(function () {
  'use strict';

  var NOTICE_KEY = 'srms.cookie-notice';
  var UTM_KEY = 'srms.utm';
  var FIELDS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

  function read(store, key) {
    try { return store.getItem(key); } catch (e) { return null; }
  }

  function write(store, key, value) {
    try { store.setItem(key, value); } catch (e) { return; }
  }

  function captureUtm() {
    var params = new URLSearchParams(window.location.search);
    var found = {};
    var any = false;
    FIELDS.forEach(function (name) {
      var value = (params.get(name) || '').trim().slice(0, 120);
      if (value) { found[name] = value; any = true; }
    });
    if (params.get('ref')) { found.referrer = params.get('ref').slice(0, 120); any = true; }

    if (any) {
      found.landed_on = window.location.pathname;
      write(window.sessionStorage, UTM_KEY, JSON.stringify(found));
      FIELDS.concat(['ref']).forEach(function (name) { params.delete(name); });
      var query = params.toString();
      var clean = window.location.pathname + (query ? '?' + query : '') + window.location.hash;
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', clean);
      }
      return found;
    }

    var stored = read(window.sessionStorage, UTM_KEY);
    if (!stored) return null;
    try { return JSON.parse(stored); } catch (e) { return null; }
  }

  function stampForms(data) {
    if (!data) return;
    document.querySelectorAll('form[data-utm]').forEach(function (form) {
      var slot = form.querySelector('input[name="utm_payload"]');
      if (!slot) {
        slot = document.createElement('input');
        slot.type = 'hidden';
        slot.name = 'utm_payload';
        form.appendChild(slot);
      }
      slot.value = JSON.stringify(data);
    });
  }

  function cookieNotice() {
    var banner = document.querySelector('.cookie-banner');
    if (!banner) return;
    if (read(window.localStorage, NOTICE_KEY) === 'seen') {
      banner.remove();
      return;
    }
    banner.hidden = false;
    window.requestAnimationFrame(function () { banner.classList.add('is-shown'); });
    banner.addEventListener('click', function (e) {
      if (!e.target.closest('[data-cookie-ok]')) return;
      write(window.localStorage, NOTICE_KEY, 'seen');
      banner.classList.remove('is-shown');
      window.setTimeout(function () { banner.remove(); }, 260);
    });
  }

  function start() {
    stampForms(captureUtm());
    cookieNotice();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
