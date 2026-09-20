(function () {
  'use strict';

  function priorityOf(headerRow) {
    var levels = [];
    for (var i = 0; i < headerRow.cells.length; i++) {
      levels.push(headerRow.cells[i].getAttribute('data-priority') || '');
    }
    return levels;
  }

  function tag(cells, levels) {
    for (var i = 0; i < cells.length && i < levels.length; i++) {
      if (levels[i]) cells[i].classList.add('col-' + levels[i]);
    }
  }

  function apply(table) {
    var headerRow = table.tHead ? table.tHead.rows[0] : null;
    if (!headerRow) return;

    var levels = priorityOf(headerRow);
    tag(headerRow.cells, levels);

    for (var b = 0; b < table.tBodies.length; b++) {
      var rows = table.tBodies[b].rows;
      for (var r = 0; r < rows.length; r++) tag(rows[r].cells, levels);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var tables = document.querySelectorAll('table[data-priority-columns]');
    for (var i = 0; i < tables.length; i++) apply(tables[i]);
  });
})();
