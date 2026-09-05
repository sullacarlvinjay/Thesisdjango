/* Registration — the scholarship a student already holds.
 *
 * Three reveals, all driven by the "I already hold a scholarship" box in the
 * Socioeconomic block:
 *
 *  1. Ticking it opens the Scholarship Data card, which is where the award
 *     number, the proof document and the notes live. Untick it and the card
 *     closes and its fields are disabled — a hidden input still posts, and half
 *     a declaration is worse than none.
 *  2. CHED is awarded at two tiers under one programme and every masterlist
 *     reports the two as separate blocks, so a CHED award has to say which. No
 *     other programme has tiers, so the question only appears for CHED.
 *  3. The same tick closes the two eligibility cards at the foot of the form.
 *     They ask what a student might qualify for, which somebody already holding
 *     an award has just answered — and asking anyway invited two accounts of
 *     the same fact that could disagree. Their fields are disabled with them,
 *     for the reason in (1).
 *
 * (1) and (3) are opposites of one another and share the reading of the box, so
 * they are computed together rather than by two listeners that could disagree
 * about the state for a frame.
 *
 * The server validates independently (see _declared_scholarship in
 * api/student_views.py) and treats every eligibility field as optional, so a
 * form posted with these disabled records nothing rather than failing; nothing
 * here is a security control.
 *
 * syncScholarshipData is global because register.html calls it when the account
 * type flips back to Student — the cards must not come back in the wrong state
 * on their own.
 */
/* Show or hide one card and take its fields with it.
 *
 * Disabling matters as much as hiding: a hidden input still posts its value, so
 * a student who typed a GPA and then ticked the box would have recorded an
 * answer to a question the form had stopped asking them.
 */
function setCardActive(id, active) {
  var card = document.getElementById(id);
  if (!card) return;
  card.hidden = !active;
  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !active;
  });
}

function syncScholarshipData() {
  var box = document.getElementById('hasScholarship');
  var type = document.getElementById('scholarshipType');
  var card = document.getElementById('scholarshipData');
  if (!box || !type || !card) return;

  // Nothing is declared while the student blocks are out of sight — the whole
  // question belongs to a student registration, and selectType calls this after
  // hiding them so a box ticked before the switch cannot survive it.
  var socioeconomic = box.closest('[data-student-only]');
  var onStudentForm = !(socioeconomic && socioeconomic.hidden);
  var declaring = box.checked && onStudentForm;

  // Asked only of a student who holds nothing yet. Note this is not simply
  // !declaring: on a staff registration both of these are false, and reading it
  // the short way would reveal two student cards on the staff form.
  var asking = onStudentForm && !box.checked;
  setCardActive('scholarshipEligibility', asking);
  setCardActive('tesEligibility', asking);

  card.hidden = !declaring;
  type.disabled = !declaring;
  type.required = declaring;
  if (!declaring) type.value = '';

  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !declaring;
  });

  // The proof is what the office verifies against their records, so it is the
  // one field in the card that is not optional.
  var proof = card.querySelector('input[name="proof_document"]');
  if (proof) proof.required = declaring;

  var tier = document.getElementById('chedTier');
  if (tier) {
    var isChed = declaring && type.value === 'CHED';
    tier.hidden = !isChed;
    var select = tier.querySelector('select');
    if (select) {
      select.disabled = !isChed;
      select.required = isChed;
      if (!isChed) select.value = '';
    }
  }
}

(function () {
  var box = document.getElementById('hasScholarship');
  var type = document.getElementById('scholarshipType');
  if (!box || !type) return;
  box.addEventListener('change', syncScholarshipData);
  type.addEventListener('change', syncScholarshipData);
  // A form coming back from a validation error keeps what was chosen, so this
  // has to read the rendered state rather than assume a blank form.
  syncScholarshipData();
})();
