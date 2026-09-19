(function () {
  'use strict';

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(fn, wait);
    };
  }

  function normalise(text) {
    return String(text || '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();
  }

  function haystack(item) {
    if (!item.dataset.searchText) {
      item.dataset.searchText = normalise(item.textContent);
    }
    return item.dataset.searchText;
  }

  function matches(item, terms) {
    var text = haystack(item);
    return terms.every(function (term) { return text.indexOf(term) !== -1; });
  }

  function wire(input) {
    var items = Array.prototype.slice.call(
      document.querySelectorAll(input.dataset.search));
    if (!items.length) {
      var host = input.closest('[data-search-host]');
      if (host) host.hidden = true;
      return;
    }

    var sections = Array.prototype.slice.call(
      document.querySelectorAll(input.dataset.searchSection || '[data-search-section]'));
    var empty = input.dataset.searchEmpty
      ? document.querySelector(input.dataset.searchEmpty) : null;
    var counter = input.dataset.searchCount
      ? document.querySelector(input.dataset.searchCount) : null;
    var clear = input.parentNode.querySelector('[data-search-clear]');

    function apply() {
      var query = normalise(input.value);
      var terms = query ? query.split(' ') : [];
      var shown = 0;

      items.forEach(function (item) {
        var hit = !terms.length || matches(item, terms);
        item.hidden = !hit;
        if (hit) shown += 1;
      });

      sections.forEach(function (section) {
        var live = section.querySelectorAll(input.dataset.search);
        var any = Array.prototype.some.call(live, function (el) { return !el.hidden; });
        section.hidden = !any;
      });

      if (empty) {
        empty.hidden = shown !== 0;
        var label = empty.querySelector('[data-search-term]');
        if (label) label.textContent = input.value.trim();
      }
      if (counter) {
        counter.textContent = terms.length
          ? shown + (shown === 1 ? ' match' : ' matches')
          : '';
      }
      if (clear) clear.hidden = !input.value;
    }

    input.addEventListener('input', debounce(apply, 150));
    input.addEventListener('search', apply);
    if (clear) {
      clear.addEventListener('click', function () {
        input.value = '';
        apply();
        input.focus();
      });
    }
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !input.value) return;
      input.value = '';
      apply();
    });
    apply();
  }

  function shortcut() {
    var first = document.querySelector('input[data-search]');
    if (!first) return;
    document.addEventListener('keydown', function (e) {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
      var active = document.activeElement;
      if (active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName)) return;
      if (active && active.isContentEditable) return;
      e.preventDefault();
      first.focus();
      first.select();
    });
  }

  function start() {
    document.querySelectorAll('input[data-search]').forEach(wire);
    shortcut();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
