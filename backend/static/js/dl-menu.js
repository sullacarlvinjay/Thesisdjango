// A button that opens the menu sitting under it.
//
// <button data-dl-menu="dlMenu"> opens <div id="dlMenu" class="dl-menu">; a
// click anywhere else closes it, and so does Escape. Open state is a class
// rather than an inline display, so the stylesheet keeps the last word on where
// the menu sits — which is what lets it stretch across the toolbar on a phone
// instead of hanging off the right edge of the card.
//
// Attribute-driven, one listener on the document, no ids hard-coded here: a
// page adds the button and the menu and nothing else.
(function () {
  var buttons = document.querySelectorAll('[data-dl-menu]');
  if (!buttons.length) return;

  function closeAll(except) {
    document.querySelectorAll('.dl-menu.is-open').forEach(function (menu) {
      if (menu === except) return;
      menu.classList.remove('is-open');
      var owner = document.querySelector('[data-dl-menu="' + menu.id + '"]');
      if (owner) owner.setAttribute('aria-expanded', 'false');
    });
  }

  buttons.forEach(function (button) {
    button.setAttribute('aria-expanded', 'false');
    button.addEventListener('click', function (event) {
      event.stopPropagation();   // or the document listener closes it again
      var menu = document.getElementById(button.getAttribute('data-dl-menu'));
      if (!menu) return;
      closeAll(menu);
      var open = menu.classList.toggle('is-open');
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });

  // A click inside the menu is a click on one of its links, which is navigating
  // away — leaving it open until then means the pointer never falls off it.
  document.addEventListener('click', function (event) {
    if (event.target.closest && event.target.closest('.dl-menu')) return;
    closeAll();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeAll();
  });
})();
