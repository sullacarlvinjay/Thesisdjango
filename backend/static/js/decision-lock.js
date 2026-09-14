(function (window, document) {
  'use strict';

  var DECIDED = ['Approved', 'Rejected', 'Needs Revision'];

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
