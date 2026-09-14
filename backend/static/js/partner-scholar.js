(function () {
  var form = document.getElementById('scholarForm');
  if (!form) return;

  var action = document.getElementById('scholarAction');
  var scholarId = document.getElementById('scholarId');
  var title = document.getElementById('scholarModalTitle');
  var submit = document.getElementById('scholarSubmit');

  function fields() {
    return Array.prototype.slice.call(
      form.querySelectorAll('.modal-body input, .modal-body select'));
  }

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
