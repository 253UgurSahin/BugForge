/* Tidewatch, level 2: Polished. The motion that needs a script; ../shared/app.js still does the work
   (the lamp, the dialog, the table) and this file only shapes how it looks while it happens:
   - sections arrive once as they come into view (IntersectionObserver), a few items at a time;
   - the four readings and the card figures count up, in tabular figures, at a fixed width;
   - the night lamp is a View Transition: the new page shows in a circle that grows from the switch;
     without View Transitions the colours cross-fade; with reduced motion it is one plain fade;
   - the tide table and the plan note leave with a short fade instead of vanishing.
   Times and curves are read from the tokens in level.css. Nothing here runs a loop that does not end.
   Without this script nothing is hidden: html[data-motion] is what lets level.css hide what arrives. */
(function () {
  "use strict";
  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var style = getComputedStyle(root);
  function token(name) { return style.getPropertyValue(name).trim(); }
  function ms(name) {
    var value = token(name);
    return /ms$/.test(value) ? parseFloat(value) : parseFloat(value) * 1000;
  }
  function still() { return reduce.matches || !Element.prototype.animate; }
  var stagger = ms("--duration-stagger") || 45;

  /* ---- figures count up -------------------------------------------------------------------- */
  function format(value, figure) {
    if (figure.time) {
      var minutes = Math.round(value);
      return String(Math.floor(minutes / 60)).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
    }
    return value.toFixed(figure.decimals).padStart(figure.pad, "0");
  }
  function countUp(el, delay) {
    var text = el.textContent.trim();
    var time = /^(\d+):(\d\d)$/.exec(text);
    var figure = {
      time: Boolean(time),
      decimals: time ? 0 : (text.split(".")[1] || "").length,
      pad: Number(el.getAttribute("data-pad")) || 0
    };
    var target = time ? Number(time[1]) * 60 + Number(time[2]) : parseFloat(text);
    if (!isFinite(target) || target === 0) return;
    var duration = ms("--duration-slower") * 1.5;
    /* the real figure for screen readers, the counting copy for the eye; both go back after */
    var spoken = document.createElement("span");
    spoken.className = "sr";
    spoken.textContent = text;
    el.parentNode.insertBefore(spoken, el);
    el.setAttribute("aria-hidden", "true");
    /* a fixed width, set from the final figure, so nothing beside it moves while it counts */
    el.style.display = "inline-block";
    el.style.minWidth = el.getBoundingClientRect().width + "px";
    el.style.textAlign = "right";
    el.textContent = format(0, figure);
    var start = null;
    function step(now) {
      if (start === null) start = now + delay;
      var progress = Math.max(0, Math.min((now - start) / duration, 1));
      var eased = 1 - Math.pow(1 - progress, 3);                       /* a soft landing */
      el.textContent = progress < 1 ? format(target * eased, figure) : text;
      if (progress < 1) { requestAnimationFrame(step); return; }
      el.removeAttribute("aria-hidden");
      el.removeAttribute("style");
      spoken.remove();
    }
    requestAnimationFrame(step);
  }

  /* ---- sections arrive once ----------------------------------------------------------------- */
  if ("IntersectionObserver" in window) {
    root.setAttribute("data-motion", "on");               /* from here on, level.css may hide what arrives */
    var targets = [];
    document.querySelectorAll("[data-arrive]").forEach(function (el) {
      var kind = el.getAttribute("data-arrive");
      if (kind === "group") {
        Array.prototype.forEach.call(el.children, function (child) { child.classList.add("arrive"); targets.push(child); });
      } else {
        el.classList.add(el.classList.contains("section__head") ? "arrive-head" : "arrive");
        targets.push(el);
      }
    });
    document.querySelectorAll(".tide__window, .tide__times > span").forEach(function (el) {
      var list = el.parentNode.querySelectorAll(el.classList.contains("tide__window") ? ".tide__window" : ":scope > span");
      el.style.setProperty("--n", String(Array.prototype.indexOf.call(list, el)));
    });

    var arrive = new IntersectionObserver(function (entries) {
      var batch = entries.filter(function (entry) { return entry.isIntersecting; })
        .map(function (entry) { return entry.target; })
        .sort(function (a, b) { return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1; });
      batch.forEach(function (el, index) {
        arrive.unobserve(el);                               /* once: scrolling back does not replay it */
        var delay = Math.min(index, 7) * stagger * 2;       /* at most eight steps, then together */
        el.style.setProperty("--m-delay", delay + "ms");
        el.classList.add("is-visible");
        if (still()) return;                                /* reduced: the figures simply stand there */
        el.querySelectorAll("[data-count]").forEach(function (figure, n) {
          countUp(figure, delay + ms("--duration-fast") + n * stagger);
        });
      });
    }, { threshold: 0.15 });
    targets.forEach(function (el) { arrive.observe(el); });
  }

  /* ---- leaving: the tide table and the plan note fade out before they are hidden ------------- */
  var passing = false;
  function passOn(button) { passing = true; button.click(); passing = false; }
  var leaving = new WeakMap();                            /* what is on its way out, per element */
  function leave(el, then) {
    if (leaving.has(el)) return;
    var out = el.animate(
      [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(" + token("--size-shift-sm") + ")" }],
      { duration: ms("--duration-base"), easing: token("--ease-exit") }
    );
    leaving.set(el, out);
    out.onfinish = function () { leaving.delete(el); then(); };
  }

  /* a new plan while the old note is still leaving: the note stays, with the new words */
  document.getElementById("plan").addEventListener("close", function () {
    var note = document.getElementById("plan-status");
    if (leaving.has(note)) { leaving.get(note).cancel(); leaving.delete(note); }
  });

  window.addEventListener("click", function (event) {
    if (passing || !event.target.closest) return;
    var toggle = event.target.closest("#table-toggle");
    if (toggle) {
      var table = document.getElementById("tide-table");
      if (leaving.has(table)) {                            /* changed their mind: it stays */
        leaving.get(table).cancel(); leaving.delete(table); event.stopImmediatePropagation(); return;
      }
      if (table.hidden || still()) return;                 /* opening: app.js shows it, level.css brings it in */
      event.stopImmediatePropagation();
      leave(table, function () { passOn(toggle); });
      return;
    }
    var close = event.target.closest("[data-close-status]");
    if (close && !still()) {
      var note = document.getElementById("plan-status");
      event.stopImmediatePropagation();
      leave(note, function () { note.hidden = true; });
      return;
    }
    if (event.target.closest("#theme-switch")) relamp(event);
  }, true);

  /* ---- the night lamp: the light spreads from the switch ------------------------------------- */
  function relamp(event) {
    var lamp = document.getElementById("theme-switch");
    if (!document.startViewTransition) {                   /* app.js switches; the colours cross-fade */
      if (reduce.matches) return;
      root.classList.add("is-relamping");
      setTimeout(function () { root.classList.remove("is-relamping"); }, ms("--duration-slow") + ms("--duration-fast"));
      return;
    }
    event.stopImmediatePropagation();
    var box = lamp.getBoundingClientRect();
    var x = box.left + box.width / 2;
    var y = box.top + box.height / 2;
    var reach = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    root.setAttribute("data-vt", reduce.matches ? "fade" : "lamp");
    var change = document.startViewTransition(function () { passOn(lamp); });
    change.ready.then(function () {
      if (reduce.matches) return;                          /* reduced: the browser's own cross-fade */
      root.animate(
        { clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + reach + "px at " + x + "px " + y + "px)"] },
        { duration: ms("--duration-lamp"), easing: token("--ease-move"), pseudoElement: "::view-transition-new(root)" }
      );
    }).catch(function () { /* skipped: the theme has changed all the same */ });
    function done() { root.removeAttribute("data-vt"); }
    change.finished.then(done, done);
  }
})();
