/* Link Scholarship — the CHED tier question.
 *
 * CHED grants Full Merit and Half Merit under one programme and the office
 * reports the two as separate blocks, so a CHED link has to say which it is.
 * Every other programme has a single tier, so the question only appears once
 * CHED is chosen — and the select is disabled while hidden so a stale value
 * can never be posted by a student who changed their mind.
 *
 * The server validates this independently; nothing here is a security control.
 */
(function () {
  var type = document.getElementById('linkScholarshipType');
  var tier = document.getElementById('chedTier');
  if (!type || !tier) return;

  var select = tier.querySelector('select');

  function sync() {
    var isChed = type.value === 'CHED';
    tier.hidden = !isChed;
    select.disabled = !isChed;
    select.required = isChed;
    if (!isChed) select.value = '';
  }

  type.addEventListener('change', sync);
  sync();   // a re-rendered form after a validation error keeps its selection
})();
