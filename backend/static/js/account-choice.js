(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('#addScholarModal form');
    if (!form) return;

    var radios = form.querySelectorAll('input[name="create_account"]');
    var note = document.getElementById('accountChoiceNote');
    if (!radios.length) return;

    function fields() {
      return {
        email: form.querySelector('input[name="email"]'),
        studentId: form.querySelector('input[name="student_id"]')
      };
    }

    function apply() {
      var wants = form.querySelector('input[name="create_account"]:checked');
      var on = wants && wants.value === 'yes';
      var f = fields();

      [f.email, f.studentId].forEach(function (el) {
        if (!el) return;
        if (on) el.setAttribute('required', 'required');
        else el.removeAttribute('required');
        var label = el.closest('div') && el.closest('div').querySelector('label');
        if (label) label.classList.toggle('is-required', on);
      });

      if (note) {
        note.hidden = !on;
        var sid = f.studentId && f.studentId.value.trim();
        note.textContent = sid
          ? 'They will sign in with the email above. Their first password is their student number, ' + sid + '.'
          : 'They will sign in with the email above. Their first password is their student number.';
      }
    }

    radios.forEach(function (r) { r.addEventListener('change', apply); });
    var sid = fields().studentId;
    if (sid) sid.addEventListener('input', apply);
    apply();
  });
})();
