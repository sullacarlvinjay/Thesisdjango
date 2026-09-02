// A School dropdown that narrows the Programme dropdown under it.
//
// <select data-filters="#completeProgram"> takes its choices from that select's
// own <optgroup> labels, and picking one shows that group alone. The same move
// the registration form makes between School and Course, except the pairs are
// already in the DOM, so there is no list to keep in step in two places.
//
// Forty programmes that all open with "BACHELOR OF SCIENCE IN" cannot be
// scanned as one list. Nobody has to remember how their course is spelled to
// find it — they pick the school they are in, and read six options instead.
//
// With JavaScript off the School box does nothing and every programme is still
// there under its own heading, which is a working form either way.
(function () {
  var filters = document.querySelectorAll('select[data-filters]');
  if (!filters.length) return;

  filters.forEach(function (schoolSelect) {
    var target = document.querySelector(schoolSelect.dataset.filters);
    if (!target) return;

    var groups = Array.prototype.slice.call(target.getElementsByTagName('optgroup'));
    if (!groups.length) return;

    groups.forEach(function (group) {
      schoolSelect.appendChild(new Option(group.label, group.label));
    });

    function apply() {
      var wanted = schoolSelect.value;
      groups.forEach(function (group) {
        var show = !wanted || group.label === wanted;
        group.hidden = !show;
        Array.prototype.forEach.call(group.children, function (option) {
          option.hidden = !show;
        });
      });
      // A programme left selected from another school would still be the answer
      // that gets submitted while no longer being visible to change.
      var chosen = target.options[target.selectedIndex];
      if (chosen && chosen.value && chosen.hidden) target.value = '';
    }

    // A programme already chosen — editing an application — sets the school it
    // belongs to, so the form opens on the group the student is looking for.
    var current = target.options[target.selectedIndex];
    if (current && current.value && current.parentElement.tagName === 'OPTGROUP') {
      schoolSelect.value = current.parentElement.label;
    }

    schoolSelect.addEventListener('change', apply);
    apply();
  });
})();
