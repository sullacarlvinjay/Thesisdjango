function setCardActive(id, active) {
  var card = document.getElementById(id);
  if (!card) return;
  card.hidden = !active;
  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !active;
  });
}

function scholarshipCards() {
  return Array.prototype.slice.call(document.querySelectorAll('[data-slot]'));
}

function typeSelectFor(card) {
  return document.querySelector('[data-type-for="' + card.dataset.slot + '"]');
}

function syncScholarshipData() {
  var box = document.getElementById('hasScholarship');
  var cards = scholarshipCards();
  if (!box || !cards.length) return;

  var socioeconomic = box.closest('[data-student-only]');
  var onStudentForm = !(socioeconomic && socioeconomic.hidden);
  var declaring = box.checked && onStudentForm;

  var asking = onStudentForm && !box.checked;
  setCardActive('scholarshipEligibility', asking);
  setCardActive('tesEligibility', asking);

  var closed = 0;
  cards.forEach(function (card, index) {
    var open = declaring && (index === 0 || card.dataset.open === 'yes');
    if (!open) closed += 1;
    setCardActive(card.id, open);

    var type = typeSelectFor(card);
    if (type) {
      type.disabled = !open;
      type.required = open;
      if (!open) type.value = '';
    }

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

    var dependent = card.querySelector('[data-staff-dependent]');
    if (dependent) {
      var isStaff = open && type && type.value === 'Staff';
      dependent.hidden = !isStaff;
      dependent.querySelectorAll('input, select').forEach(function (field) {
        field.disabled = !isStaff;
        field.required = isStaff;
        if (!isStaff) field.value = '';
      });
    }
  });

  var row = document.getElementById('addScholarshipRow');
  if (row) row.hidden = !declaring || closed === 0;
}

function syncAppointmentDetails() {
  var status = document.querySelector('[data-appointment-status]');
  var block = document.querySelector('[data-regular-only]');
  if (!status || !block) return;

  var card = status.closest('[data-staff-only]');
  var regular = !(card && card.hidden) && status.value === 'Regular';

  block.hidden = !regular;
  block.querySelectorAll('input').forEach(function (field) {
    field.disabled = !regular;
    field.required = regular;
    if (!regular) field.value = '';
  });
}

function syncStaffScholarshipData() {
  var box = document.getElementById('hasStaffScholarship');
  var card = document.getElementById('staffScholarshipData');
  if (!box || !card) return;

  var block = box.closest('[data-staff-only]');
  var onStaffForm = !(block && block.hidden);
  var declaring = box.checked && onStaffForm;

  card.hidden = !declaring;
  card.querySelectorAll('input, select, textarea').forEach(function (field) {
    field.disabled = !declaring;
  });

  var proof = card.querySelector('input[name="staff_proof_document"]');
  if (proof) proof.required = declaring;
}

(function () {
  var box = document.getElementById('hasScholarship');
  if (box) box.addEventListener('change', syncScholarshipData);

  scholarshipCards().forEach(function (card) {
    card.dataset.open = card.hidden ? '' : 'yes';
    var type = typeSelectFor(card);
    if (type) type.addEventListener('change', syncScholarshipData);

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

  var appointment = document.querySelector('[data-appointment-status]');
  if (appointment) appointment.addEventListener('change', syncAppointmentDetails);

  syncScholarshipData();
  syncStaffScholarshipData();
  syncAppointmentDetails();
})();
