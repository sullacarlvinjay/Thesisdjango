(function () {
  var tables = document.querySelectorAll('table[data-sortable]');
  if (!tables.length) return;

  var TERM = /^(\d{4})-\d{4}\s+(\d)(?:st|nd|rd|th)\s+Semester/i;

  function sortKey(cell) {
    var text = (cell.innerText || '').trim();

    var term = text.match(TERM);
    if (term) return Number(term[1]) * 10 + Number(term[2]);

    if (/^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}$/.test(text)) {
      var when = Date.parse(text);
      if (!isNaN(when)) return when;
    }

    if (/^-?\d+(\.\d+)?$/.test(text)) return parseFloat(text);

    return text.toLowerCase();
  }

  function compare(a, b) {
    if (typeof a === 'number' && typeof b === 'number') return a - b;
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
