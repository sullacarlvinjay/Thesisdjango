(function () {
  'use strict';

  /* A meter's fill is a percentage of a number the page only knows at render
     time, so it cannot be a class. Setting it here rather than in a style
     attribute is what lets the Content-Security-Policy drop 'unsafe-inline':
     a width written through the CSSOM is not an inline style. */

  function paint() {
    var bars = document.querySelectorAll('[data-meter]');
    Array.prototype.forEach.call(bars, function (bar) {
      var value = parseFloat(bar.getAttribute('data-meter'));
      if (!isFinite(value)) { value = 0; }
      bar.style.width = Math.max(0, Math.min(100, value)) + '%';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', paint);
  } else {
    paint();
  }
}());
