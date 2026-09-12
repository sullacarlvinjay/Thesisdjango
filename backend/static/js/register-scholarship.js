/* Registration — the scholarships a student already holds.
 *
 * All of it hangs off the "I already hold a scholarship" box in the
 * Socioeconomic block:
 *
 *  1. Ticking it opens the first Scholarship Data card, which is where the
 *     award number, the proof document and the notes live. Untick it and the
 *     card closes and its fields are disabled — a hidden input still posts, and
 *     half a declaration is worse than none.
 *  2. A student may hold more than one, so there is more than one card. "I hold
 *     another scholarship" opens the next; Remove closes one again. Only the
 *     first is opened by the checkbox, and unticking that box closes all of
 *     them — declaring nothing cannot leave a second declaration standing.
 *  3. CHED is awarded at two tiers under one programme and every masterlist
 *     reports the two as separate blocks, so a CHED award has to say which. No
 *     other programme has tiers, so the question only appears for CHED, and it
 *     is asked per card because two cards can name two different programmes.
 *  4. The same tick closes the two eligibility cards at the foot of the form.
 *     They ask what a student might qualify for, which somebody already holding
 *     an award has just answered — and asking anyway invited two accounts of
 *     the same fact that could disagree. Their fields are disabled with them,
 *     for the reason in (1).
 *
 * (1) and (4) are opposites of one another and share the reading of the box, so
 * they are computed together rather than by two listeners that could disagree
 * about the state for a frame.
 *
 * The server validates independently (see _declared_scholarships in
 * api/student_views.py) and treats every eligibility field as optional, so a
 * form posted with these disabled records nothing rather than failing; nothing
 * here is a security control.
 *
 * syncScholarshipData is global because register.html calls it when the account
 * type flips back to Student — the cards must not come back in the wrong state
 * on their own. syncStaffScholarshipData is global for the mirror of that
 * reason, and both are called from the same place.
 */
/* Show or hide one card and take its fields with it.
 *
 * Disabling matters as much as hiding: a hidden input still posts its value, so
 * a student who typed a GPA and then ticked the box would have recorded an
 * answer to a question the form had stopped asking them. It is also what closes
 * a Scholarship Data card properly — the card's own has_scholarship input goes
 * with it, which is the whole of what tells the server the card was used.
 */
function setCardActive(id, active) {
  var card = document.getElementById(id);
  if (!card) return;
  card.hidden = !active;
  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !active;
  });
}

/* The Scholarship Data cards, in the order they are filled in. */
function scholarshipCards() {
  return Array.prototype.slice.call(document.querySelectorAll('[data-slot]'));
}

/* The programme dropdown belonging to one card.
 *
 * Found by data-type-for rather than by looking inside the card, because the
 * first card's dropdown is not inside it: it sits up in the Socioeconomic block
 * beside the box that opens the card, where the question was always asked.
 */
function typeSelectFor(card) {
  return document.querySelector('[data-type-for="' + card.dataset.slot + '"]');
}

function syncScholarshipData() {
  var box = document.getElementById('hasScholarship');
  var cards = scholarshipCards();
  if (!box || !cards.length) return;

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

  var closed = 0;
  cards.forEach(function (card, index) {
    // The first card is the checkbox's. The rest are opened one at a time by
    // the button below them, and every one of them shuts when the first does:
    // a student who says they hold nothing holds nothing.
    var open = declaring && (index === 0 || card.dataset.open === 'yes');
    if (!open) closed += 1;
    setCardActive(card.id, open);

    var type = typeSelectFor(card);
    if (type) {
      type.disabled = !open;
      type.required = open;
      if (!open) type.value = '';
    }

    // The proof is what the office verifies against their records, so it is the
    // one field in a card that is not optional.
    var proof = card.querySelector('input[type="file"]');
    if (proof) proof.required = open;

    var tier = card.querySelector('[data-ched-tier]');
    if (tier) {
      var isChed = open && type && type.value === 'CHED';
      tier.hidden = !isChed;
      var select = tier.querySelector('select');
      if (select) {
        select.disabled = !isChed;
        select.required = isChed;
        if (!isChed) select.value = '';
      }
    }
  });

  // Offered only while there is a card left to open, and never before the first
  // one is: "another scholarship" makes no sense to a student who has not
  // named a first.
  var row = document.getElementById('addScholarshipRow');
  if (row) row.hidden = !declaring || closed === 0;
}

/* The staff half of the same question, and a shorter one.
 *
 * One programme is on offer there, so there is no type to choose, no tier to
 * reveal and no second card: the BiPSU Staff Scholarship is the one award an
 * employee can already hold and the office can check. Ticking the box opens the
 * proof and notes, and unticking it closes them and disables their fields for
 * the reason in (1) above.
 *
 * There is no eligibility card to close in step: those two ask what a student
 * might qualify for, and neither is on the staff form at all.
 */
function syncStaffScholarshipData() {
  var box = document.getElementById('hasStaffScholarship');
  var card = document.getElementById('staffScholarshipData');
  if (!box || !card) return;

  // As on the student side, nothing is declared while the staff blocks are out
  // of sight: selectType hides them before calling this, so a box ticked before
  // the switch cannot survive it.
  var block = box.closest('[data-staff-only]');
  var onStaffForm = !(block && block.hidden);
  var declaring = box.checked && onStaffForm;

  card.hidden = !declaring;
  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !declaring;
  });

  // The proof is the whole evidence for an award the office did not record
  // itself, so it is the one field here that is not optional.
  var proof = card.querySelector('input[name="staff_proof_document"]');
  if (proof) proof.required = declaring;
}

(function () {
  var box = document.getElementById('hasScholarship');
  if (box) box.addEventListener('change', syncScholarshipData);

  // A card coming back from a validation error is rendered open by the server,
  // so its state is read off the page rather than assumed shut. Everything
  // after that is this flag, which sync() reads.
  scholarshipCards().forEach(function (card) {
    card.dataset.open = card.hidden ? '' : 'yes';
    var type = typeSelectFor(card);
    if (type) type.addEventListener('change', syncScholarshipData);

    // Removing a card clears it as well as closing it. Leaving the answers
    // behind would mean a student who removed one and added it again for a
    // different programme was posting the first one's award number. The card's
    // own has_scholarship input is the exception — it is what the card *is*,
    // not something the student typed, and sync() disables it on the way out.
    var remove = card.querySelector('[data-drop-slot]');
    if (remove) {
      remove.addEventListener('click', function () {
        card.dataset.open = '';
        card.querySelectorAll('input, select, textarea').forEach(function (field) {
          if (field.type !== 'hidden') field.value = '';
        });
        syncScholarshipData();
      });
    }
  });

  var add = document.getElementById('addScholarship');
  if (add) {
    add.addEventListener('click', function () {
      var next = scholarshipCards().filter(function (card, index) {
        return index > 0 && card.dataset.open !== 'yes';
      })[0];
      if (next) next.dataset.open = 'yes';
      syncScholarshipData();
      if (next) {
        var type = typeSelectFor(next);
        if (type) type.focus();
      }
    });
  }

  var staffBox = document.getElementById('hasStaffScholarship');
  if (staffBox) staffBox.addEventListener('change', syncStaffScholarshipData);

  // A form coming back from a validation error keeps what was chosen, so these
  // have to read the rendered state rather than assume a blank form.
  syncScholarshipData();
  syncStaffScholarshipData();
})();
