/* Add Scholar: what the "portal account" choice demands of the form.
 *
 * There is no password box on this form and there should not be — the office
 * does not choose the scholar's password, the student number becomes it, and
 * the scholar is emailed to say so. That only works if both fields are actually
 * filled in, and neither is required for an import, so the requirement has to
 * follow the radio rather than sit on the input.
 *
 * The server refuses the same combination regardless (vpsea_archive_add); this
 * only moves the complaint from after the submit to before it.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('#addScholarModal form');
    if (!form) return;

    var radios = form.querySelectorAll('input[name="create_account"]');
    var note = document.getElementById('accountChoiceNote');
    if (!radios.length) return;

    function fields() {
      // Both branches of the modal name them the same; only one is rendered.
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
        // The asterisk the rest of this form uses for a required field.
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
