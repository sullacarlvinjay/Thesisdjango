(function () {
  var tables = document.querySelectorAll('table[data-filterable]');
  if (!tables.length) return;

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(fn, wait);
    };
  }

  function textOf(cell) {
    return (cell.innerText || '').trim().replace(/\s+/g, ' ');
  }

  function groupOf(cell) {
    return (cell.dataset.group || '').trim();
  }

  tables.forEach(function (table) {
    var head = table.tHead && table.tHead.rows[0];
    var body = table.tBodies[0];
    if (!head || !body) return;

    var headings = Array.prototype.slice.call(head.cells);
    var columns = [];
    headings.forEach(function (th, index) {
      if (th.hasAttribute('data-filter')) {
        columns.push({
          index: index,
          label: th.dataset.filter || th.textContent.trim(),
          group: th.dataset.filterGroup || '',
        });
      }
    });
    if (!columns.length) return;

    function dataRows() {
      return Array.prototype.slice.call(body.rows).filter(function (r) {
        return r.cells.length === headings.length;
      });
    }
    function placeholderRows() {
      return Array.prototype.slice.call(body.rows).filter(function (r) {
        return r.cells.length !== headings.length;
      });
    }

    var bar = table.parentElement.querySelector('[data-filter-bar]')
           || (table.closest('.card') || document).querySelector('[data-filter-bar]');
    if (!bar) return;

    var search = null;
    if (bar.dataset.filterSearch) {
      search = document.querySelector(bar.dataset.filterSearch);
    }

    var selects = [];
    var syncs = [];

    function valueIn(row, select) {
      var cell = row.cells[Number(select.dataset.column)];
      if (!cell) return '';
      return select.dataset.reads === 'group' ? groupOf(cell) : textOf(cell);
    }

    function choicesIn(column, read) {
      var values = [];
      dataRows().forEach(function (row) {
        var cell = row.cells[column.index];
        var value = cell ? read(cell) : '';
        if (value && value !== '—' && values.indexOf(value) === -1) values.push(value);
      });
      return values.sort(function (a, b) {
        return a.localeCompare(b, undefined, { numeric: true });
      });
    }

    function addSelect(column, label, values, reads) {
      var select = document.createElement('select');
      select.className = 'filter-scheme__select';
      select.setAttribute('aria-label', 'Filter by ' + label);
      select.appendChild(new Option('Any ' + label, ''));
      values.forEach(function (value) {
        select.appendChild(new Option(value, value));
      });
      select.dataset.column = String(column.index);
      if (reads) select.dataset.reads = reads;
      bar.appendChild(select);
      selects.push(select);
      return select;
    }

    function narrowBy(group, select, column) {
      var owner = {};
      dataRows().forEach(function (row) {
        var cell = row.cells[column.index];
        if (cell) owner[textOf(cell)] = groupOf(cell);
      });

      function sync() {
        Array.prototype.forEach.call(select.options, function (option) {
          option.hidden = Boolean(group.value && option.value
                                  && owner[option.value] !== group.value);
        });
        var chosen = select.options[select.selectedIndex];
        if (chosen && chosen.hidden) select.value = '';
      }

      group.addEventListener('change', sync);
      syncs.push(sync);
    }

    columns.forEach(function (column) {
      var group = null;
      if (column.group) {
        var groups = choicesIn(column, groupOf);
        if (groups.length > 1) group = addSelect(column, column.group, groups, 'group');
      }

      var values = choicesIn(column, textOf);
      if (values.length < 2) return;
      var select = addSelect(column, column.label, values);
      if (group) narrowBy(group, select, column);
    });

    var count = document.createElement('span');
    count.className = 'filter-scheme__count';
    bar.appendChild(count);

    var clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'btn btn-outline filter-scheme__clear';
    clear.textContent = 'Clear';
    clear.hidden = true;
    bar.appendChild(clear);

    function apply() {
      var query = search ? search.value.trim().toLowerCase() : '';
      var active = selects.filter(function (s) { return s.value; });
      var rows = dataRows();
      var showing = 0;

      rows.forEach(function (row) {
        var matches = active.every(function (select) {
          return valueIn(row, select) === select.value;
        });
        if (matches && query) {
          matches = textOf(row).toLowerCase().indexOf(query) !== -1;
        }
        row.hidden = !matches;
        if (matches) showing += 1;
      });

      var narrowed = active.length > 0 || query !== '';
      clear.hidden = !narrowed;
      count.textContent = narrowed ? 'Showing ' + showing + ' of ' + rows.length : '';

      placeholderRows().forEach(function (row) { row.hidden = narrowed; });

      if (narrowed && showing === 0) {
        count.textContent = 'No rows match this filter';
      }
    }

    selects.forEach(function (select) { select.addEventListener('change', apply); });
    if (search) search.addEventListener('input', debounce(apply, 150));
    clear.addEventListener('click', function () {
      selects.forEach(function (select) { select.value = ''; });
      syncs.forEach(function (sync) { sync(); });
      if (search) search.value = '';
      apply();
    });

    apply();
  });
})();
