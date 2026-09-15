(function () {
  'use strict';

  var SAFETY_MS = 30000;
  var bar = null;
  var barTimer = null;
  var safety = null;
  var navigating = false;

  function progressBar() {
    if (bar) return bar;
    bar = document.createElement('div');
    bar.className = 'route-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    return bar;
  }

  function startProgress() {
    var el = progressBar();
    window.clearTimeout(barTimer);
    el.classList.remove('is-done');
    void el.offsetWidth;
    el.classList.add('is-active');
  }

  function stopProgress() {
    if (!bar) return;
    bar.classList.remove('is-active');
    bar.classList.add('is-done');
    barTimer = window.setTimeout(function () {
      if (bar) bar.classList.remove('is-done');
    }, 320);
  }

  function isControl(el) {
    return /^(SELECT|INPUT|TEXTAREA)$/.test(el.tagName);
  }

  function attachSpinner(el) {
    if (!el.offsetParent && el.type !== 'hidden' && el.offsetWidth === 0) return;
    if (el.nextElementSibling
        && el.nextElementSibling.classList.contains('control-spinner')) return;
    var spinner = document.createElement('span');
    spinner.className = 'control-spinner';
    spinner.setAttribute('role', 'status');
    spinner.setAttribute('aria-label', 'Loading');
    el.parentNode.insertBefore(spinner, el.nextSibling);
  }

  function detachSpinner(el) {
    var next = el.nextElementSibling;
    if (next && next.classList.contains('control-spinner')) next.remove();
  }

  function markBusy(el, label) {
    if (!el || el.classList.contains('is-busy')) return;
    el.classList.add('is-busy');
    el.setAttribute('aria-busy', 'true');
    if (isControl(el)) {
      attachSpinner(el);
      return;
    }
    if (label && !el.dataset.busyLabel) {
      el.dataset.busyLabel = el.textContent;
      el.textContent = label;
    }
  }

  function clearBusy(el) {
    if (!el) return;
    el.classList.remove('is-busy');
    el.removeAttribute('aria-busy');
    if (isControl(el)) detachSpinner(el);
    if (el.dataset.busyLabel) {
      el.textContent = el.dataset.busyLabel;
      delete el.dataset.busyLabel;
    }
  }

  function releaseAll() {
    navigating = false;
    window.clearTimeout(safety);
    document.querySelectorAll('.is-busy').forEach(clearBusy);
    document.querySelectorAll('form[aria-busy]').forEach(function (form) {
      form.removeAttribute('aria-busy');
      delete form.dataset.busy;
    });
    stopProgress();
  }

  function beginNavigation() {
    navigating = true;
    startProgress();
    window.clearTimeout(safety);
    safety = window.setTimeout(releaseAll, SAFETY_MS);
  }

  function opensElsewhere(el) {
    var target = el.getAttribute('target');
    return (target && target !== '_self') || el.hasAttribute('download');
  }

  function submitterFor(form, event) {
    if (event && event.submitter) return event.submitter;
    return form.querySelector(
      'button[type="submit"], input[type="submit"], button:not([type])');
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM' || e.defaultPrevented) return;
    if (form.hasAttribute('data-no-loading')) return;

    if (form.dataset.busy === '1') {
      e.preventDefault();
      return;
    }

    var button = submitterFor(form, e);
    if (button && button.hasAttribute('formnovalidate')) return;
    if (button && opensElsewhere(button)) return;
    if (opensElsewhere(form)) return;

    form.dataset.busy = '1';
    form.setAttribute('aria-busy', 'true');
    markBusy(button, button && button.dataset.busyText);
    beginNavigation();
  });

  function reloadsOnChange(control) {
    if (control.tagName === 'SELECT') return true;
    return control.tagName === 'INPUT'
        && /^(checkbox|radio|file)$/.test(control.type);
  }

  document.addEventListener('change', function (e) {
    var control = e.target;
    if (!control || !control.form) return;
    var form = control.form;
    if (form.hasAttribute('data-no-loading')) return;
    if (!reloadsOnChange(control)) return;

    var ours = form.hasAttribute('data-auto-submit')
            || control.hasAttribute('data-submits');
    var inline = /submit\s*\(/.test(control.getAttribute('onchange') || '');
    if (!ours && !inline) return;

    markBusy(control);
    form.setAttribute('aria-busy', 'true');
    beginNavigation();

    if (ours && form.dataset.busy !== '1') {
      form.dataset.busy = '1';
      form.submit();
    }
  });

  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var link = e.target.closest('a[data-loading]');
    if (!link || opensElsewhere(link)) return;
    var href = link.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#' || /^(mailto|tel|javascript):/i.test(href)) return;
    markBusy(link, link.dataset.busyText);
    beginNavigation();
  });

  window.addEventListener('pageshow', releaseAll);
  window.addEventListener('pagehide', function () { navigating = false; });

  window.srmsLoading = { start: beginNavigation, stop: releaseAll, busy: markBusy, idle: clearBusy };
})();
