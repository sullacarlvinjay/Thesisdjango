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
// A column can also name the wider thing its values belong to —
// <th data-filter="Program" data-filter-group="School"> — with every cell
// carrying its own in data-group. That grouping gets a dropdown of its own,
// ahead of the column's, and narrows it: pick a school and forty programme
// names drop to the six that school offers. The same pairing select-by-group.js
// makes of School and Programme on the apply form, for the same reason — a list
// nobody can scan is a list nobody uses.
//
// Filtering here rather than on the server keeps it instant and keeps it
// composable with the sort in table-sort.js, which reorders the same rows.
(function () {
  var tables = document.querySelectorAll('table[data-filterable]');
  if (!tables.length) return;

  function textOf(cell) {
    return (cell.innerText || '').trim().replace(/\s+/g, ' ');
  }

  // The group a cell says its value belongs to. Absent means the row was never
  // filed under one, which is not a category and so matches no choice.
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
    var syncs = [];

    // What a control reads off a row: the cell it was built from, either as the
    // text shown there or as the group that text belongs to.
    function valueIn(row, select) {
      var cell = row.cells[Number(select.dataset.column)];
      if (!cell) return '';
      return select.dataset.reads === 'group' ? groupOf(cell) : textOf(cell);
    }

    // The choices a column offers, in the order someone would scan them. A
    // blank or em-dash cell is not one of them: it says the value was never
    // recorded, which is not a category to narrow by.
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
      // "Any School" rather than "All School": the labels are column headings,
      // and most of them are singular.
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

    // A chosen group leaves only that group's options on the column's own
    // dropdown, so the pair can never describe a row that does not exist.
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
        // A programme left selected from another school would go on narrowing
        // the table while no longer being visible to change.
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
        // A grouping every row shares narrows nothing.
        if (groups.length > 1) group = addSelect(column, column.group, groups, 'group');
      }

      var values = choicesIn(column, textOf);
      // A column where every row says the same thing filters nothing.
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
      syncs.forEach(function (sync) { sync(); });
      if (search) search.value = '';
      apply();
    });

    apply();
  });
})();
