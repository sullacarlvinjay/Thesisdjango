// Show a follow-up box when a dropdown is set to the one option that needs it.
//
// A <select data-reveals="#someBox" data-reveal-on="Other"> shows #someBox
// while "Other" is chosen and hides it otherwise. Used by the TES form, where
// picking a disability CHED's list does not name means typing it out instead.
//
// The box is hidden with the `hidden` attribute rather than a class, so a
// browser with the stylesheet still loading never flashes it, and the field
// inside is disabled while it is out of sight — a hidden input still posts, and
// a stale value from a choice the student changed their mind about would go to
// CHED as their answer.
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
        // Required only while it is the question actually being asked.
        if (show) {
          field.setAttribute('required', 'required');
        } else {
          field.removeAttribute('required');
        }
      });
      if (show && fields.length) fields[0].focus({ preventScroll: true });
    }

    // Bound before the first sync so a value the server sent back — an "Other"
    // being corrected — comes up with its box already open.
    select.addEventListener('change', sync);
    sync();
    // Nothing should be focused on load; only a change the person made earns it.
    if (document.activeElement && box.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  });
})();
