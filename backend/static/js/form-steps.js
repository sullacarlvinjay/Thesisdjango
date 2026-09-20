(function () {
  'use strict';

  var FORM = '[data-steps]';
  var STEP = '[data-step]';

  /* A form re-rendered with server errors carries no data-steps attribute, so
     no stepper is built and every section is shown at once. Grouping is for
     the first pass through a long form; once something is wrong, hiding any
     of it behind a Continue button hides the thing that needs fixing. */

  function stepsIn(form) {
    return Array.prototype.filter.call(
      form.querySelectorAll(STEP),
      function (step) { return step.closest(FORM) === form; });
  }

  function visibleSteps(form) {
    return stepsIn(form).filter(function (step) {
      return !step.hasAttribute('hidden') || step.dataset.stepActive === 'true';
    });
  }

  function stepIsEmpty(step) {
    var kids = step.children;
    if (!kids.length) return true;
    for (var i = 0; i < kids.length; i += 1) {
      if (!kids[i].hasAttribute('hidden')) return false;
    }
    return true;
  }

  function liveSteps(form) {
    return stepsIn(form).filter(function (step) {
      return step.dataset.stepSkip !== 'true' && !stepIsEmpty(step);
    });
  }

  function fieldsIn(step) {
    return Array.prototype.filter.call(
      step.querySelectorAll('input, select, textarea'),
      function (field) {
        return field.type !== 'hidden' && !field.disabled && field.willValidate;
      });
  }

  function reachable(field) {
    return field.offsetParent !== null || field.type === 'file';
  }

  function firstInvalid(step) {
    var fields = fieldsIn(step);
    for (var i = 0; i < fields.length; i += 1) {
      if (reachable(fields[i]) && !fields[i].checkValidity()) return fields[i];
    }
    return null;
  }

  function label(step, index) {
    return step.dataset.stepLabel || 'Step ' + (index + 1);
  }

  function buildProgress(form, steps) {
    var nav = document.createElement('ol');
    nav.className = 'form-steps__track';
    nav.setAttribute('aria-label', 'Registration progress');
    steps.forEach(function (step, index) {
      var item = document.createElement('li');
      item.className = 'form-steps__dot';
      item.dataset.stepDot = String(index);
      var mark = document.createElement('span');
      mark.className = 'form-steps__mark';
      mark.textContent = String(index + 1);
      var text = document.createElement('span');
      text.className = 'form-steps__name';
      text.textContent = label(step, index);
      item.appendChild(mark);
      item.appendChild(text);
      nav.appendChild(item);
    });
    return nav;
  }

  function buildControls() {
    var bar = document.createElement('div');
    bar.className = 'form-steps__controls';

    var back = document.createElement('button');
    back.type = 'button';
    back.className = 'btn btn-outline';
    back.dataset.stepBack = '';
    back.textContent = 'Back';

    var count = document.createElement('p');
    count.className = 'form-steps__count';
    count.dataset.stepCount = '';

    var next = document.createElement('button');
    next.type = 'button';
    next.className = 'btn btn-primary';
    next.dataset.stepNext = '';
    next.textContent = 'Continue';

    bar.appendChild(back);
    bar.appendChild(count);
    bar.appendChild(next);
    return bar;
  }

  function Stepper(form) {
    this.form = form;
    this.steps = stepsIn(form);
    this.index = 0;
    if (this.steps.length < 2) return;

    this.track = buildProgress(form, this.steps);
    this.controls = buildControls();
    this.steps[0].parentNode.insertBefore(this.track, this.steps[0]);
    var last = this.steps[this.steps.length - 1];
    last.parentNode.insertBefore(this.controls, last.nextSibling);

    this.submit = form.querySelector('[data-step-submit]')
      || form.querySelector('button[type="submit"]');
    this.back = this.controls.querySelector('[data-step-back]');
    this.next = this.controls.querySelector('[data-step-next]');
    this.count = this.controls.querySelector('[data-step-count]');

    form.__stepper = this;
    this.bind();
    this.openFirstProblem();
  }

  Stepper.prototype.bind = function () {
    var self = this;
    this.back.addEventListener('click', function () { self.move(-1); });
    this.next.addEventListener('click', function () { self.move(1); });
    this.track.addEventListener('click', function (event) {
      var dot = event.target.closest('[data-step-dot]');
      if (!dot) return;
      var wanted = parseInt(dot.dataset.stepDot, 10);
      if (wanted < self.index) self.show(wanted);
      else self.advanceTo(wanted);
    });
    this.form.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      var field = event.target;
      if (field.tagName === 'TEXTAREA' || field.type === 'submit') return;
      if (self.index < self.lastLive()) {
        event.preventDefault();
        self.move(1);
      }
    });
    this.form.addEventListener('change', function () { self.refresh(); });

    if (window.MutationObserver) {
      this.watcher = new MutationObserver(function () { self.refresh(); });
      this.steps.forEach(function (step) {
        Array.prototype.forEach.call(step.children, function (card) {
          self.watcher.observe(card, { attributes: true,
                                       attributeFilter: ['hidden'] });
        });
      });
    }
  };

  Stepper.prototype.refresh = function () {
    if (liveSteps(this.form).indexOf(this.steps[this.index]) === -1) {
      this.show(this.index);
      return;
    }
    this.paint();
  };

  Stepper.prototype.lastLive = function () {
    var live = liveSteps(this.form);
    return this.steps.indexOf(live[live.length - 1]);
  };

  Stepper.prototype.openFirstProblem = function () {
    var start = 0;
    for (var i = 0; i < this.steps.length; i += 1) {
      if (this.steps[i].dataset.stepError === 'true') { start = i; break; }
    }
    this.show(start);
  };

  Stepper.prototype.show = function (index) {
    var live = liveSteps(this.form);
    if (!live.length) return;
    var target = this.steps[index];
    if (!target || live.indexOf(target) === -1) {
      target = live[0];
      index = this.steps.indexOf(target);
    }
    this.index = index;
    this.steps.forEach(function (step, i) {
      var on = i === index;
      step.hidden = !on;
      step.dataset.stepActive = on ? 'true' : 'false';
    });
    this.paint();
    if (this.track.scrollIntoView) {
      this.track.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
  };

  Stepper.prototype.paint = function () {
    var live = liveSteps(this.form);
    var position = live.indexOf(this.steps[this.index]);
    var last = position === live.length - 1;

    this.back.disabled = position <= 0;
    this.next.hidden = last;
    if (this.submit) this.submit.hidden = !last;
    this.count.textContent = 'Step ' + (position + 1) + ' of ' + live.length;

    var self = this;
    this.steps.forEach(function (step, i) {
      var dot = self.track.querySelector('[data-step-dot="' + i + '"]');
      if (!dot) return;
      var place = live.indexOf(step);
      dot.hidden = place === -1;
      var mark = dot.querySelector('.form-steps__mark');
      if (mark && place > -1) mark.textContent = String(place + 1);
      dot.classList.toggle('is-current', i === self.index);
      dot.classList.toggle('is-done', place > -1 && place < position);
    });
  };

  Stepper.prototype.move = function (direction) {
    if (direction > 0 && !this.validate()) return;
    var live = liveSteps(this.form);
    var position = live.indexOf(this.steps[this.index]) + direction;
    if (position < 0 || position >= live.length) return;
    this.show(this.steps.indexOf(live[position]));
  };

  Stepper.prototype.advanceTo = function (wanted) {
    while (this.index < wanted) {
      var before = this.index;
      this.move(1);
      if (this.index === before) return;
    }
  };

  Stepper.prototype.validate = function () {
    var bad = firstInvalid(this.steps[this.index]);
    if (!bad) return true;
    bad.reportValidity();
    bad.focus({ preventScroll: false });
    return false;
  };

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll(FORM),
      function (form) { new Stepper(form); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  window.FormSteps = { Stepper: Stepper, stepsIn: stepsIn, fieldsIn: fieldsIn,
                       visibleSteps: visibleSteps, liveSteps: liveSteps,
                       stepIsEmpty: stepIsEmpty, start: start };
})();
