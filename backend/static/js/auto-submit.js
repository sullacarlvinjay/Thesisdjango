(function () {
  document.querySelectorAll('form[data-auto-submit]').forEach(function (form) {
    form.addEventListener('change', function (event) {
      var control = event.target;
      if (control.tagName === 'SELECT' || control.type === 'checkbox'
          || control.type === 'radio') {
        form.submit();
      }
    });
  });
})();
