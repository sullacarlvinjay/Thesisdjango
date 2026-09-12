/* The seal preview on the scholarship form.
 *
 * One job: show the chosen seal beside the dropdown, so the office is picking a
 * picture rather than a filename. Nothing here is saved and nothing validates —
 * the view checks the posted name against the files that actually exist, since
 * this value ends up in an <img src>.
 *
 * The blank option means "work it out from the programme's type", which only
 * the server knows the answer to. Rather than duplicate that map in JavaScript
 * and let the two drift, the preview falls back to the seal the page was
 * rendered with, which is already the right one.
 */
(function () {
  'use strict';

  var picker = document.querySelector('[data-logo-picker]');
  var preview = document.querySelector('[data-logo-preview]');
  if (!picker || !preview) return;

  // What the server resolved for this programme, captured before any change so
  // clearing the box can put it back.
  var fallback = preview.getAttribute('src');

  picker.addEventListener('change', function () {
    preview.setAttribute(
      'src', picker.value ? '/media/logos/' + picker.value : fallback);
  });
})();
