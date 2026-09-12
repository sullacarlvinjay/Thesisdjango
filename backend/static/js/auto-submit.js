// A form that submits itself when one of its controls changes.
//
// <form data-auto-submit> ... <select name="sy"> ... </form> — pick a term and
// the page reloads on it, with no Go button to find. The form still works
// without this: it is a plain GET form, and the <noscript> button beside the
// control is what submits it when there is no scripting to save the click.
//
// An attribute rather than onchange= in the markup, so the template stays
// structure and this stays behaviour — and so the next form that wants it says
// so in one word.
(function () {
  document.querySelectorAll('form[data-auto-submit]').forEach(function (form) {
    form.addEventListener('change', function (event) {
      // Only the controls that name a value; a file input or a button would
      // submit a form nobody has finished filling in.
      var control = event.target;
      if (control.tagName === 'SELECT' || control.type === 'checkbox'
          || control.type === 'radio') {
        form.submit();
      }
    });
  });
})();
