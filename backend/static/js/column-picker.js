// Add and remove the custom columns on the scholarship form.
//
// The ticked catalogue columns need no script — they are plain checkboxes that
// post their own values. Only the office's own columns are repeatable, and they
// are one text input each: the name is what the table heading reads, and the
// server derives the storage key from it (see api/scholar_columns.custom_key),
// so renaming a column back to what it was finds the values already typed.
(function () {
  var list = document.getElementById('customColumns');
  var addButton = document.getElementById('addCustomColumn');
  if (!list || !addButton) return;

  function newRow() {
    var row = document.createElement('div');
    row.className = 'col-picker__row';

    var input = document.createElement('input');
    input.name = 'extra_columns';
    input.placeholder = 'e.g. Batch, Adviser';

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-outline col-picker__remove';
    remove.textContent = 'Remove';

    row.appendChild(input);
    row.appendChild(remove);
    return { row: row, input: input };
  }

  addButton.addEventListener('click', function () {
    var made = newRow();
    list.appendChild(made.row);
    made.input.focus();
  });

  // Delegated, so it covers the rows rendered by the server as well as the ones
  // added above. An empty row is dropped server-side either way, but removing
  // it here is what tells the office the column is gone.
  list.addEventListener('click', function (event) {
    var button = event.target.closest('.col-picker__remove');
    if (button) button.parentElement.remove();
  });
})();
