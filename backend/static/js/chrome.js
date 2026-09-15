(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function scrollProgress() {
    var bar = document.querySelector('.scroll-progress');
    if (!bar) return;
    var frame = null;

    function paint() {
      frame = null;
      var doc = document.documentElement;
      var span = (doc.scrollHeight - doc.clientHeight);
      var ratio = span > 40 ? Math.min(1, Math.max(0, window.scrollY / span)) : 0;
      bar.style.transform = 'scaleX(' + ratio + ')';
      bar.classList.toggle('is-lit', ratio > 0.002);
    }

    function schedule() {
      if (frame === null) frame = window.requestAnimationFrame(paint);
    }

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    paint();
  }

  function backToTop() {
    var button = document.querySelector('.to-top');
    if (!button) return;
    var frame = null;

    function paint() {
      frame = null;
      button.classList.toggle('is-shown', window.scrollY > 400);
    }

    function schedule() {
      if (frame === null) frame = window.requestAnimationFrame(paint);
    }

    window.addEventListener('scroll', schedule, { passive: true });
    button.addEventListener('click', function () {
      var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
      var main = document.getElementById('mainContent');
      if (main) main.focus({ preventScroll: true });
    });
    paint();
  }

  function skipLink() {
    var main = document.getElementById('mainContent');
    if (!main) return;
    main.addEventListener('blur', function () { main.removeAttribute('tabindex'); });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.skip-link')) return;
      main.setAttribute('tabindex', '-1');
      main.focus({ preventScroll: true });
    });
  }

  function flash(button, message) {
    if (button.dataset.flashing === '1') return;
    button.dataset.flashing = '1';
    var original = button.getAttribute('aria-label') || button.title;
    var label = button.querySelector('[data-copy-label]');
    var previous = label ? label.textContent : null;
    button.classList.add('is-copied');
    if (label) label.textContent = message;
    button.setAttribute('aria-label', message);
    window.setTimeout(function () {
      button.classList.remove('is-copied');
      if (label && previous !== null) label.textContent = previous;
      if (original) button.setAttribute('aria-label', original);
      delete button.dataset.flashing;
    }, 1600);
  }

  function textFor(button) {
    if (button.dataset.copy) return button.dataset.copy;
    var target = button.dataset.copyTarget
      ? document.querySelector(button.dataset.copyTarget) : null;
    if (!target) return '';
    if ('value' in target && target.value !== undefined) return target.value;
    return (target.textContent || '').trim();
  }

  function legacyCopy(text) {
    var pad = document.createElement('textarea');
    pad.value = text;
    pad.setAttribute('readonly', '');
    pad.className = 'copy-pad';
    document.body.appendChild(pad);
    pad.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(pad);
    return ok;
  }

  function copyToClipboard() {
    document.addEventListener('click', function (e) {
      var button = e.target.closest('[data-copy], [data-copy-target]');
      if (!button) return;
      e.preventDefault();
      var text = textFor(button);
      if (!text) return;
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(
          function () { flash(button, 'Copied'); },
          function () { flash(button, legacyCopy(text) ? 'Copied' : 'Press Ctrl+C'); });
      } else {
        flash(button, legacyCopy(text) ? 'Copied' : 'Press Ctrl+C');
      }
    });
  }

  var EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 6.2A9.9 9.9 0 0 1 12 6c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4"/><path d="M6.6 6.7A17.2 17.2 0 0 0 2 13s3.6 7 10 7a9.7 9.7 0 0 0 4.7-1.2"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

  function attachToggle(input) {
    if (input.dataset.pwWired === '1') return;
    if (input.closest('.pw-field')) return;
    input.dataset.pwWired = '1';

    var wrap = document.createElement('div');
    wrap.className = 'pw-field';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'pw-toggle';
    button.innerHTML = EYE;
    button.setAttribute('aria-label', 'Show password');
    button.setAttribute('aria-pressed', 'false');
    button.title = 'Show password';

    button.addEventListener('click', function () {
      var shown = input.type === 'text';
      input.type = shown ? 'password' : 'text';
      button.innerHTML = shown ? EYE : EYE_OFF;
      button.setAttribute('aria-pressed', shown ? 'false' : 'true');
      var label = shown ? 'Show password' : 'Hide password';
      button.setAttribute('aria-label', label);
      button.title = label;
    });

    wrap.appendChild(button);
  }

  function passwordToggles() {
    document.querySelectorAll('input[type="password"]').forEach(attachToggle);
    if (!window.MutationObserver) return;
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches('input[type="password"]')) attachToggle(node);
          if (node.querySelectorAll) {
            node.querySelectorAll('input[type="password"]').forEach(attachToggle);
          }
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  function paintThemeButtons(dark) {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      button.setAttribute('aria-pressed', dark ? 'true' : 'false');
      var label = dark ? 'Switch to light mode' : 'Switch to dark mode';
      button.setAttribute('aria-label', label);
      button.title = label;
      var moon = button.querySelector('[data-theme-moon]');
      var sun = button.querySelector('[data-theme-sun]');
      if (moon) moon.hidden = dark;
      if (sun) sun.hidden = !dark;
    });
    var meta = document.querySelector('meta[name="theme-color"]:not([media])');
    if (meta) meta.setAttribute('content', dark ? '#171c2e' : '#ffffff');
  }

  function themeToggle() {
    if (!document.querySelector('[data-theme-toggle]')) return;
    paintThemeButtons(document.documentElement.classList.contains('dark'));
    document.addEventListener('click', function (e) {
      if (!e.target.closest('[data-theme-toggle]')) return;
      var dark = document.documentElement.classList.toggle('dark');
      try { window.localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch (err) { return; }
      paintThemeButtons(dark);
    });
  }

  ready(function () {
    themeToggle();
    scrollProgress();
    backToTop();
    skipLink();
    copyToClipboard();
    passwordToggles();
  });
})();
