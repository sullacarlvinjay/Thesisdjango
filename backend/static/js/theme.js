(function () {
  'use strict';

  var stored = null;
  try {
    stored = window.localStorage.getItem('theme');
  } catch (e) {
    stored = null;
  }

  var dark = stored === 'dark' ||
             (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);

  if (dark) document.documentElement.classList.add('dark');
})();
