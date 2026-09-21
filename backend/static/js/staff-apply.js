(function () {
  'use strict';

  function calcAge(dob) {
    if (!dob) return '';
    var today = new Date();
    var birth = new Date(dob);
    var age = today.getFullYear() - birth.getFullYear();
    var m = today.getMonth() - birth.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age -= 1;
    return age >= 0 ? age : '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    var bdField = document.getElementById('birthDateField');
    var ageField = document.getElementById('ageField');
    if (bdField && ageField) {
      if (bdField.value) ageField.value = calcAge(bdField.value);
      bdField.addEventListener('change', function () {
        ageField.value = calcAge(bdField.value);
      });
    }

    var radios = document.querySelectorAll('[data-applicant-kind]');
    if (!radios.length) return;
    radios.forEach(function (radio) {
      radio.addEventListener('change', function () {
        if (!radio.checked) return;
        window.location.href = '/nsu-staff/apply/?applicant_kind=' +
          encodeURIComponent(radio.value);
      });
    });
  });
})();
