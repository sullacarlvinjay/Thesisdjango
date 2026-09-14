(function () {
  var agree = document.getElementById('termsAgree');
  var box = document.getElementById('acceptTerms');
  if (!agree || !box) return;

  agree.addEventListener('click', function () {
    box.checked = true;
    box.dispatchEvent(new Event('change', { bubbles: true }));
    var overlay = agree.closest('.modal-overlay');
    if (overlay) overlay.classList.remove('open');
  });
})();
