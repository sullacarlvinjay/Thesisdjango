(function () {
  'use strict';

  var picker = document.querySelector('[data-logo-picker]');
  var preview = document.querySelector('[data-logo-preview]');
  if (!picker || !preview) return;

  var fallback = preview.getAttribute('src');

  picker.addEventListener('change', function () {
    preview.setAttribute(
      'src', picker.value ? '/media/logos/' + picker.value + '?v=2' : fallback);
  });
})();
