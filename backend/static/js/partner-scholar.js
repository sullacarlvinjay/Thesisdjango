/* The partner portal's one scholar dialog, opened for adding and for editing.
 *
 * One dialog rather than two, because it is the same eleven questions either
 * way and two copies drift apart the first time a column moves. What changes
 * between them is the title, the submit label, and two hidden inputs — so that
 * is all this does.
 *
 * The values come off the Edit button's own data- attributes rather than from a
 * fetch: the row is already on the page, and a dialog that has to wait for the
 * network to show what is in front of you is a slower way to say the same
 * thing.
 *
 * Opening is templates/../modal-open.js's job — every button here carries
 * data-preview-open — so this listens on the same clicks and only fills in.
 * Nothing here is a permission check: api/student_views.partner_scholars
 * decides what this account may actually touch, and it looks the row up in a
 * way that cannot find one belonging to somebody else.
 */
(function () {
  var form = document.getElementById('scholarForm');
  if (!form) return;

  var action = document.getElementById('scholarAction');
  var scholarId = document.getElementById('scholarId');
  var title = document.getElementById('scholarModalTitle');
  var submit = document.getElementById('scholarSubmit');

  // The dialog's own fields, by the name they post under. Read off the form so
  // adding a question to the template is enough — a list here would be a second
  // place to remember.
  function fields() {
    return Array.prototype.slice.call(
      form.querySelectorAll('.modal-body input, .modal-body select'));
  }

  /* 'last_name' -> 'lastName', which is how a data-last-name attribute reads
     back off dataset. */
  function camel(name) {
    return name.replace(/_([a-z])/g, function (_, c) { return c.toUpperCase(); });
  }

  function clear() {
    fields().forEach(function (field) { field.value = ''; });
  }

  document.querySelectorAll('[data-scholar-add]').forEach(function (button) {
    button.addEventListener('click', function () {
      clear();
      action.value = 'add';
      scholarId.value = '';
      title.textContent = 'Add a scholar';
      submit.textContent = 'Add scholar';
    });
  });

  document.querySelectorAll('[data-scholar-edit]').forEach(function (button) {
    button.addEventListener('click', function () {
      clear();
      action.value = 'edit';
      scholarId.value = button.getAttribute('data-scholar-edit');
      fields().forEach(function (field) {
        var value = button.dataset[camel(field.name)];
        if (value !== undefined) field.value = value;
      });
      var name = [button.dataset.firstName, button.dataset.lastName]
        .filter(Boolean).join(' ');
      title.textContent = name ? 'Edit ' + name : 'Edit scholar';
      submit.textContent = 'Save changes';
    });
  });
})();
