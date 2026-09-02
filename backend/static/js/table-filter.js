// Filter schemes: narrow a table to one category at a time.
//
// Pick "School of Engineering" and the table shows those rows and no others —
// the same move as picking a set in a relic filter. Any number of columns can
// be narrowed at once, and the bar says how much of the list survived.
//
// A <table data-filterable> drives it. Each <th data-filter> becomes a control
// whose options are the values actually in that column, so the list can never
// offer a choice that matches nothing, and the office never has to know in
// advance which schools or semesters are represented.
//
// Filtering here rather than on the server keeps it instant and keeps it
// composable with the sort in table-sort.js, which reorders the same rows.
(function () {
  var tables = document.querySelectorAll('table[data-filterable]');
  if (!tables.length) return;

  function textOf(cell) {
    return (cell.innerText || '').trim().replace(/\s+/g, ' ');
  }

  tables.forEach(function (table) {
    var head = table.tHead && table.tHead.rows[0];
    var body = table.tBodies[0];
    if (!head || !body) return;

    var headings = Array.prototype.slice.call(head.cells);
    var columns = [];
    headings.forEach(function (th, index) {
      if (th.hasAttribute('data-filter')) {
        columns.push({ index: index, label: th.dataset.filter || th.textContent.trim() });
      }
    });
    if (!columns.length) return;

    // Only rows with a cell in every column; an empty-state row spans them all.
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
    columns.forEach(function (column) {
      var values = [];
      dataRows().forEach(function (row) {
        var value = textOf(row.cells[column.index]);
        if (value && value !== '—' && values.indexOf(value) === -1) values.push(value);
      });
      // A column where every row says the same thing filters nothing.
      if (values.length < 2) return;
      values.sort(function (a, b) {
        return a.localeCompare(b, undefined, { numeric: true });
      });

      var select = document.createElement('select');
      select.className = 'filter-scheme__select';
      select.setAttribute('aria-label', 'Filter by ' + column.label);
      // "Any School" rather than "All School": the labels are column headings,
      // and most of them are singular.
      select.appendChild(new Option('Any ' + column.label, ''));
      values.forEach(function (value) {
        select.appendChild(new Option(value, value));
      });
      select.dataset.column = String(column.index);
      bar.appendChild(select);
      selects.push(select);
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
          return textOf(row.cells[Number(select.dataset.column)]) === select.value;
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

      // The "nothing here yet" row would sit under a filtered-out list and read
      // as if the queue were empty, so it only shows when the queue really is.
      placeholderRows().forEach(function (row) { row.hidden = narrowed; });

      if (narrowed && showing === 0) {
        count.textContent = 'No rows match this filter';
      }
    }

    selects.forEach(function (select) { select.addEventListener('change', apply); });
    if (search) search.addEventListener('input', apply);
    clear.addEventListener('click', function () {
      selects.forEach(function (select) { select.value = ''; });
      if (search) search.value = '';
      apply();
    });

    apply();
  });
})();
