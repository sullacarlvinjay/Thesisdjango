/* Per-grantee rows on /unifast/liquidation/.
 *
 * Two conveniences, and deliberately nothing more. Every figure this touches
 * lands in a form field the officer can still read, change and choose not to
 * submit — the page saves nothing until they press Save, which is the whole
 * reason the "billed amount" button is allowed to exist at all. A liquidation
 * that filled itself in would be a liquidation that cannot detect the thing it
 * is for.
 *
 * Listeners are delegated from the table, so rows re-rendered by a later
 * server round trip keep working without rebinding.
 */
(function () {
  'use strict';

  var table = document.querySelector('[data-liquidation-rows]');
  if (!table) return;

  var RELEASED = 'Released';

  function rowFor(el) {
    return el.closest('tr');
  }

  function fieldsIn(row) {
    return {
      status: row.querySelector('[data-field="status"]'),
      amount: row.querySelector('[data-field="amount"]'),
      date: row.querySelector('[data-field="date"]'),
      receipt: row.querySelector('[data-field="receipt"]')
    };
  }

  /* Only a release carries an amount and a date. The server enforces this too
   * — it stores neither on a row that is not Released — so this is here to
   * stop an officer typing into a box whose value is about to be dropped,
   * not as the rule itself. */
  function syncRow(row) {
    var f = fieldsIn(row);
    if (!f.status) return;
    var released = f.status.value === RELEASED;
    [f.amount, f.date, f.receipt].forEach(function (input) {
      if (!input) return;
      input.disabled = !released;
      if (!released) input.value = '';
    });
  }

  table.addEventListener('change', function (event) {
    if (event.target.matches('[data-field="status"]')) syncRow(rowFor(event.target));
  });

  /* "Fill in the billed amount" — the ordinary case, where everybody was paid
   * exactly what CHED was billed for. It fills the boxes; the officer reviews
   * the rows and submits them, or does not. Rows already marked are left
   * alone: overwriting a Returned row with a release would be this button
   * quietly undoing somebody's work. */
  var fill = document.querySelector('[data-fill-billed]');
  if (fill) {
    fill.addEventListener('click', function () {
      Array.prototype.forEach.call(
        table.querySelectorAll('tr[data-entitled]'),
        function (row) {
          var f = fieldsIn(row);
          if (!f.status || f.status.value === RELEASED) return;
          if (row.dataset.recorded === '1') return;

          f.status.value = RELEASED;
          syncRow(row);
          if (f.amount) f.amount.value = row.dataset.entitled;
          if (f.date && !f.date.value) f.date.value = fill.dataset.fillBilled || '';
        }
      );
    });
  }

  Array.prototype.forEach.call(table.querySelectorAll('tr[data-entitled]'), syncRow);
})();
