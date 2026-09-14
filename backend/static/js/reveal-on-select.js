(function () {
  var selects = document.querySelectorAll('select[data-reveals]');
  if (!selects.length) return;

  selects.forEach(function (select) {
    var box = document.querySelector(select.dataset.reveals);
    if (!box) return;
    var trigger = select.dataset.revealOn || '';
    var fields = box.querySelectorAll('input, select, textarea');

    function sync() {
      var show = select.value === trigger;
      box.hidden = !show;
      fields.forEach(function (field) {
        field.disabled = !show;
        if (show) {
          field.setAttribute('required', 'required');
        } else {
          field.removeAttribute('required');
        }
      });
      if (show && fields.length) fields[0].focus({ preventScroll: true });
    }

    select.addEventListener('change', sync);
    sync();
    if (document.activeElement && box.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  });
})();
