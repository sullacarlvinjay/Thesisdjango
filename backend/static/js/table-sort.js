// Click a column heading to sort the table by it.
//
// Applies to any <table data-sortable>. Every heading becomes a sort control
// except ones marked data-no-sort — an actions column has nothing to order by.
//
// Sorting happens in the page rather than on the server because these tables
// are one screen of rows the office is already looking at: re-fetching to
// reorder them would cost a round trip and lose the search box's filtering.
(function () {
  var tables = document.querySelectorAll('table[data-sortable]');
  if (!tables.length) return;

  // "2026-2027 1st Semester" has to sort as a term, not as text: without this
  // the 2nd semester of 2025 lands after the 1st of 2026.
  var TERM = /^(\d{4})-\d{4}\s+(\d)(?:st|nd|rd|th)\s+Semester/i;

  function sortKey(cell) {
    var text = (cell.innerText || '').trim();

    var term = text.match(TERM);
    if (term) return Number(term[1]) * 10 + Number(term[2]);

    // A date the table printed as "Aug 29, 2026".
    if (/^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}$/.test(text)) {
      var when = Date.parse(text);
      if (!isNaN(when)) return when;
    }

    // A plain number, including a GWA or a year level. Anything with letters
    // in it stays text, so a student number like 23-1-00286 is not read as
    // arithmetic.
    if (/^-?\d+(\.\d+)?$/.test(text)) return parseFloat(text);

    return text.toLowerCase();
  }

  function compare(a, b) {
    if (typeof a === 'number' && typeof b === 'number') return a - b;
    // Blanks and em-dashes sort last whichever way the column is pointing, so
    // a missing value never pushes a real one off the top of the list.
    var aEmpty = a === '' || a === '—';
    var bEmpty = b === '' || b === '—';
    if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
    return String(a).localeCompare(String(b), undefined, { numeric: true });
  }

  tables.forEach(function (table) {
    var head = table.tHead && table.tHead.rows[0];
    var body = table.tBodies[0];
    if (!head || !body) return;

    var headings = Array.prototype.slice.call(head.cells);

    headings.forEach(function (th, index) {
      if (th.hasAttribute('data-no-sort') || !th.textContent.trim()) return;
      th.classList.add('is-sortable');
      th.tabIndex = 0;
      th.setAttribute('role', 'button');
      th.setAttribute('aria-sort', 'none');

      function sort() {
        var ascending = th.dataset.sort !== 'asc';

        // Only real rows: an empty-state row spans the table and has no cell
        // in this column to compare.
        var rows = Array.prototype.slice.call(body.rows).filter(function (r) {
          return r.cells.length === headings.length;
        });
        var others = Array.prototype.slice.call(body.rows).filter(function (r) {
          return r.cells.length !== headings.length;
        });

        rows.sort(function (rowA, rowB) {
          var result = compare(sortKey(rowA.cells[index]), sortKey(rowB.cells[index]));
          return ascending ? result : -result;
        });

        headings.forEach(function (other) {
          if (other !== th) {
            delete other.dataset.sort;
            other.setAttribute('aria-sort', 'none');
          }
        });
        th.dataset.sort = ascending ? 'asc' : 'desc';
        th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');

        rows.forEach(function (row) { body.appendChild(row); });
        others.forEach(function (row) { body.appendChild(row); });
      }

      th.addEventListener('click', sort);
      th.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          sort();
        }
      });
    });
  });
})();
