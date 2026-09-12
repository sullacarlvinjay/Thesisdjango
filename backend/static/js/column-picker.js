// Add and remove the custom columns on the scholarship form, and say what each
// one holds.
//
// The ticked catalogue columns need no script — they are plain checkboxes that
// post their own values. Only the office's own columns are repeatable, and a
// row of them is three fields: the name, which is what the table heading reads
// and what the server derives the storage key from (see
// api/scholar_columns.custom_key, so renaming a column back to what it was
// finds the values already typed); the kind of data it holds; and, for a choice
// list, the options.
//
// The three post as parallel lists read by position, so every row has to post
// all three even when one is not being used. The options box is therefore
// hidden rather than removed when the kind is not a choice list — a removed
// field posts nothing and would slide every kind after it onto the wrong
// column.
(function () {
  var list = document.getElementById('customColumns');
  var addButton = document.getElementById('addCustomColumn');
  if (!list || !addButton) return;

  // The kinds come from the server rather than being listed again here: they
  // are the same list the <select>s rendered above were built from, and a
  // second copy in this file is one that can disagree with the one the server
  // validates against.
  var types = (list.dataset.customTypes || '').split('|').filter(Boolean)
    .map(function (pair) {
      var at = pair.indexOf(':');
      return { key: pair.slice(0, at), label: pair.slice(at + 1) };
    });

  function optionsBox(row) {
    return row.querySelector('[data-custom-options]');
  }

  function syncOptions(row) {
    var select = row.querySelector('select[name="extra_types"]');
    var box = optionsBox(row);
    if (select && box) box.hidden = select.value !== 'choice';
  }

  function newRow() {
    var row = document.createElement('div');
    row.className = 'col-picker__row';
    row.setAttribute('data-custom-column', '');

    var name = document.createElement('input');
    name.name = 'extra_columns';
    name.placeholder = 'e.g. Batch, Adviser';
    name.setAttribute('aria-label', 'Column name');

    var kind = document.createElement('select');
    kind.name = 'extra_types';
    kind.setAttribute('aria-label', 'What this column holds');
    types.forEach(function (type) {
      var option = document.createElement('option');
      option.value = type.key;
      option.textContent = type.label;
      kind.appendChild(option);
    });

    var options = document.createElement('input');
    options.name = 'extra_options';
    options.placeholder = 'e.g. Full, Partial';
    options.setAttribute('data-custom-options', '');
    options.setAttribute('aria-label', 'Choices, separated by commas');
    options.hidden = true;

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-outline col-picker__remove';
    remove.textContent = 'Remove';

    row.appendChild(name);
    row.appendChild(kind);
    row.appendChild(options);
    row.appendChild(remove);
    return { row: row, input: name };
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
    if (button) button.closest('.col-picker__row').remove();
  });

  // Choosing a choice list is what asks for the options, so the box appears the
  // moment it is chosen rather than sitting empty beside every other kind.
  list.addEventListener('change', function (event) {
    if (event.target.name !== 'extra_types') return;
    var row = event.target.closest('.col-picker__row');
    syncOptions(row);
    var box = optionsBox(row);
    if (box && !box.hidden) box.focus();
  });
})();


// Reordering the archive table's columns.
//
// The order the boxes post in is the order the table reads, so moving a row
// here is the whole edit — there is no separate "position" field to keep in
// step with it. The numbers are recomputed after every change rather than
// stored, because a stored number is one more thing that can disagree with the
// list it describes.
(function () {
  var list = document.getElementById('columnPicker');
  if (!list) return;

  function items() {
    return Array.prototype.slice.call(list.querySelectorAll('.col-picker__item'));
  }

  function renumber() {
    var n = 0;
    items().forEach(function (item) {
      var box = item.querySelector('input[type="checkbox"]');
      var badge = item.querySelector('.col-picker__no');
      item.classList.toggle('is-off', !box.checked);
      badge.textContent = box.checked ? String(++n) : '';
    });
  }

  list.addEventListener('click', function (event) {
    var button = event.target.closest('.col-picker__move');
    if (!button) return;
    var item = button.closest('.col-picker__item');
    var sibling = button.dataset.move === 'up'
      ? item.previousElementSibling
      : item.nextElementSibling;
    if (!sibling) return;
    if (button.dataset.move === 'up') list.insertBefore(item, sibling);
    else list.insertBefore(sibling, item);
    renumber();
  });

  list.addEventListener('change', function (event) {
    // A column just ticked belongs at the end of the table rather than wherever
    // it happened to sit in the unused block — joining the middle would quietly
    // renumber every column after it.
    var box = event.target;
    if (box.type !== 'checkbox') return;
    if (box.checked) {
      var item = box.closest('.col-picker__item');
      var lastOn = items().filter(function (i) {
        return i !== item && i.querySelector('input').checked;
      }).pop();
      if (lastOn) list.insertBefore(item, lastOn.nextElementSibling);
    }
    renumber();
  });

  renumber();
})();
