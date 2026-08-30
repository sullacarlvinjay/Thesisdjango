// A decision is made once.
//
// Approve, Send Back and Reject all record one, so a review modal opened on an
// application that already carries a decision shows what was decided instead of
// offering the buttons again. The server refuses a second decision either way —
// this is so the office is not offered an action that cannot succeed.
(function (window, document) {
  'use strict';

  // The statuses that mean "the office has decided". Anything else — Pending
  // Validation, Draft — is a submission still waiting on review. Kept in step
  // with DECIDED_APPLICATION_STATUSES in api/constants.py.
  var DECIDED = ['Approved', 'Rejected', 'Needs Revision'];

  // 'Needs Revision' is the stored status; 'Sent back' is what the office
  // pressed. The button says the same thing.
  var WORDING = {
    'Approved': 'Approved',
    'Rejected': 'Rejected',
    'Needs Revision': 'Sent back for resubmission'
  };

  var BADGE = {
    'Approved': 'badge-success',
    'Rejected': 'badge-destructive',
    'Needs Revision': 'badge-info'
  };

  function escapeHtml(text) {
    var el = document.createElement('div');
    el.textContent = text;
    return el.innerHTML;
  }

  // status   — the application's current status
  // formId   — the form holding the decision buttons
  // noticeId — the element that stands in for it once decided
  // remarks  — what the office wrote at the time, if anything
  function lockDecision(status, formId, noticeId, remarks) {
    var form = document.getElementById(formId);
    var notice = document.getElementById(noticeId);
    if (!form || !notice) return;

    var decided = DECIDED.indexOf(status) !== -1;
    form.hidden = decided;
    notice.hidden = !decided;
    if (!decided) return;

    var html = '<span class="badge ' + (BADGE[status] || 'badge-muted') + '">' +
      escapeHtml(WORDING[status] || status) + '</span>';
    if (remarks) {
      html += '<p class="decision-locked-remarks">' + escapeHtml(remarks) + '</p>';
    }
    html += '<p class="decision-locked-note">Decided already — a decision is ' +
      'made once and cannot be changed here.</p>';
    notice.innerHTML = html;
  }

  window.lockDecision = lockDecision;
})(window, document);
