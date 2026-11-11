/* Tidewatch, level 4: the scripts of levels 2 and 3, kept whole; level 4 itself is hero.js and table.js.
   Two changes only: the reveal switch is html[data-reveal] (the scene kit's motion button owns
   html[data-motion]), and the dot of the day under the lamp stands a little above its ribbon (--dot-z).
   Level 3: Expressive. ../shared/app.js does the work (the lamp switch, the dialog, the table);
   this file shapes how it looks while it happens. Its first part is level 2's, unchanged: sections arrive
   once, figures count up, the night lamp spreads from its switch as a View Transition, the tide table and
   the plan note leave with a fade. Its second part, "level 3: Expressive", adds:
   - the lamp over the chart: it follows the hand on a damped cable, moves its pool and the shade on the
     tilted sheet (the CSS perspective undone, so both meet), and the shadows of the land and the slip;
     nobody pointing, it hangs over the river and walks down the pencil line as the hero scrolls away;
   - the opening: the sheet is laid on the table, its plates come down, the slip lands, all with springs;
   - the week told as you scroll: the tide curve pinned, a cursor through the days (fast at night, slow over
     daylight), each safe window hatched in as it passes, and the day's own curve flowing into the next;
   - springs (the Web Animations API with a CSS linear() curve): the slip, the passage slips, the lamp switch;
   - the kit's depth.js (../../vendor/scenes/depth.js), loaded with import(): the hero's plates, the passage
     slips and the notes. Without it, or without this script, the page is the flat level-2 page.
   Every loop runs only while something moves on screen; with reduced motion nothing here moves at all. */
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
    root.setAttribute("data-reveal", "on");               /* from here on, level.css may hide what arrives */
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

/* ================================================================ level 3: Expressive */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)");
  var style = getComputedStyle(document.documentElement);
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function token(name) { return style.getPropertyValue(name).trim(); }
  function ms(name) { var value = token(name); return /ms$/.test(value) ? parseFloat(value) : parseFloat(value) * 1000; }
  function moving() { return !reduce.matches && Boolean(Element.prototype.animate); }
  /* a real spring for element.animate(): a CSS linear() curve from a duration and a bounce (0.05 to 0.6) */
  function spring(duration, bounce) {
    var zeta = 1 - clamp(bounce, 0.05, 0.6), w = (2 * Math.PI) / (duration / 1000), wd = w * Math.sqrt(1 - zeta * zeta);
    var at = function (t) { return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + ((zeta * w) / wd) * Math.sin(wd * t)); };
    var settle = Math.log(1000 * (1 + (zeta * w) / wd)) / (zeta * w), points = [];
    for (var i = 0; i <= 40; i++) points.push(i === 40 ? 1 : +at((settle * i) / 40).toFixed(3));
    var easing = "linear(" + points.join(", ") + ")";
    var ok = window.CSS && CSS.supports && CSS.supports("transition-timing-function", easing);
    return { duration: Math.round(settle * 1000), easing: ok ? easing : token("--ease-spring") };
  }
  /* the opening, in the times level 2 uses: the pencil sets down, draws for --duration-draw, the slip lands */
  var COURSE = ms("--duration-slower") + ms("--duration-fast"), SLIP = COURSE + ms("--duration-draw") - ms("--duration-fast");

  /* ---- the lamp: it hangs over the chart and follows the hand -------------------------------- */
  var hero = document.querySelector(".hero");
  var lamp = hero && hero.querySelector(".hero__lamp");
  if (lamp) (function () {
    var scene = hero.querySelector(".hero__scene");
    var shade = hero.querySelector(".hero__shade");
    var slip = hero.querySelector(".hero__slip");
    var shadows = Array.prototype.slice.call(hero.querySelectorAll(".plate--shadow"));
    var LANDS = { "1": [528, 216], "2": [517, 770] };       /* the middle of each land mass, in chart units */
    var p = null, v = { x: 0, y: 0 }, hand = null, frame = 0, last = 0, cast = false;

    var sheet = hero.querySelector(".sheet");
    function box() {                                         /* the sheet, and where the chart lies on it */
      var sw = sheet.offsetWidth, sh = sheet.offsetHeight, narrow = window.innerWidth <= 960;
      var pw = narrow ? Math.max(sw, 740) : sw, ph = narrow ? pw * 0.9 : sh;
      var s = Math.max(pw / 1000, ph / 900);
      return { sx: scene.offsetLeft + sheet.offsetLeft, sy: scene.offsetTop + sheet.offsetTop, sw: sw, sh: sh, narrow: narrow,
        ox: sw - pw + pw - 1000 * s, oy: sh - ph + ph - 900 * s, s: s };
    }
    function chartToHero(b, x, y) { return { x: b.sx + b.ox + x * b.s, y: b.sy + b.oy + y * b.s }; }
    function rest(b) {                                       /* nobody points: over the river, and down the pencil line as the hero scrolls away */
      var h = hero.offsetHeight;
      var at = b.narrow ? { x: b.sx + b.sw * 0.58, y: h - 150 } : { x: b.sx + b.sw * 0.5, y: h * 0.51 };
      var gone = reduce.matches ? 0 : clamp(-hero.getBoundingClientRect().top / (h * 0.8), 0, 1);
      var fix = chartToHero(b, 524, 594), go = 0.7 * gone;    /* towards the 14:40 fix on the pencil line */
      return { x: at.x + (fix.x - at.x) * go, y: at.y + (fix.y - at.y) * go };
    }
    function target(b) {
      if (!hand || reduce.matches) return rest(b);
      return { x: clamp(hand.x, b.sx + b.sw * 0.16, hero.offsetWidth - 24), y: clamp(hand.y, hero.offsetHeight * 0.06, hero.offsetHeight * 0.97) };
    }
    /* where a point of the screen lies on the tilted sheet: the CSS perspective, undone. The numbers are
       read from the CSS once, and again after a resize */
    var view = null;
    function measure() {
      var cs = getComputedStyle(scene), root = getComputedStyle(document.documentElement);
      view = { o: cs.perspectiveOrigin.split(" ").map(parseFloat), P: parseFloat(cs.perspective) || 0,
        org: getComputedStyle(sheet).transformOrigin.split(" ").map(parseFloat),
        th: (parseFloat(root.getPropertyValue("--l3-tilt")) || 0) * Math.PI / 180, k: parseFloat(root.getPropertyValue("--l3-sheet-scale")) || 1 };
    }
    function onSheet(x, y) {
      if (!view) measure();
      var o = view.o, P = view.P, org = view.org, th = view.th, k = view.k;
      var X = x - scene.offsetLeft, Y = y - scene.offsetTop, sx0 = sheet.offsetLeft, sy0 = sheet.offsetTop;
      if (!P) return { x: X - sx0, y: Y - sy0 };
      var q = Y - o[1], A = sy0 + org[1] - o[1], d = P * (q - A) / (P * Math.cos(th) + q * Math.sin(th));
      var s = P / (P - d * Math.sin(th)), gx = o[0] + (X - o[0]) / s;
      return { x: org[0] + (gx - sx0 - org[0]) / k, y: org[1] + d / k };
    }
    function draw(b) {
      lamp.style.transform = "translate3d(" + p.x.toFixed(1) + "px, " + p.y.toFixed(1) + "px, 0)";
      var lit = onSheet(p.x, p.y);
      shade.style.transform = "translate3d(" + lit.x.toFixed(1) + "px, " + lit.y.toFixed(1) + "px, 0)";
      /* the land throws its shadow away from the lamp; on a touch screen once, from where the lamp rests */
      var from = fine.matches ? p : cast ? null : rest(b);
      if (from) shadows.forEach(function (el) {
        var c = LANDS[el.getAttribute("data-land")], at = chartToHero(b, c[0], c[1]);
        var dx = (at.x - from.x) * 0.03, dy = (at.y - from.y) * 0.03, n = Math.hypot(dx, dy), k = n > 16 ? 16 / n : 1;
        el.style.translate = (dx * k).toFixed(1) + "px " + (dy * k).toFixed(1) + "px";
        cast = true;
      });
      if (slip && slip.offsetParent) {                         /* and so does the slip lying on it */
        var sx = slip.offsetLeft + slip.offsetWidth / 2 + slip.offsetParent.offsetLeft, sy = slip.offsetTop + slip.offsetHeight / 2 + slip.offsetParent.offsetTop;
        slip.style.setProperty("--slip-sx", clamp((sx - p.x) * 0.03, -16, 16).toFixed(1));
        slip.style.setProperty("--slip-sy", clamp((sy - p.y) * 0.03, -10, 16).toFixed(1));
      }
    }
    function tick(now) {
      frame = 0;
      var b = box(), t = target(b);
      if (!p || reduce.matches) { p = { x: t.x, y: t.y }; v.x = v.y = 0; draw(b); last = 0; return; }
      var dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
      last = now;
      /* a lamp on its cable: it swings after the hand and settles, a little past and back */
      var w = 6.2, z = 0.62;
      v.x += (w * w * (t.x - p.x) - 2 * z * w * v.x) * dt; v.y += (w * w * (t.y - p.y) - 2 * z * w * v.y) * dt;
      p.x += v.x * dt; p.y += v.y * dt;
      draw(b);
      if (Math.abs(t.x - p.x) + Math.abs(t.y - p.y) > 0.4 || Math.abs(v.x) + Math.abs(v.y) > 0.4) wake(); else last = 0;
    }
    function wake() { if (!frame && !document.hidden) frame = requestAnimationFrame(tick); }
    window.addEventListener("pointermove", function (event) {
      if (event.pointerType === "touch" || !fine.matches) return;
      var r = hero.getBoundingClientRect(), x = event.clientX - r.left, y = event.clientY - r.top;
      /* only over the chart: over the words the lamp goes back to its place, so nothing lights the text */
      var over = y >= 0 && y <= r.height && x >= scene.offsetLeft + scene.offsetWidth * 0.14;
      hand = over ? { x: x, y: y } : null;
      wake();
    }, { passive: true });
    document.documentElement.addEventListener("pointerleave", function () { hand = null; wake(); });
    window.addEventListener("scroll", wake, { passive: true });
    window.addEventListener("resize", function () { view = null; wake(); });
    reduce.addEventListener("change", wake);
    /* switched on: the lamp swings in on its cable from up and to the right, and settles over the river */
    var b0 = box(), r0 = rest(b0);
    p = moving() ? { x: r0.x + Math.min(b0.sw, 900) * 0.2, y: r0.y - hero.offsetHeight * 0.16 } : r0;
    draw(b0);
    if (moving()) wake(); else tick(performance.now());
  })();

  /* ---- the opening of level 3: the sheet is laid on the table, its plates come down one by one ---- */
  if (hero && moving()) (function () {
    var sheet = hero.querySelector(".sheet"), lay = spring(ms("--duration-draw") * 1.4, 0.18);   /* laid down */
    sheet.animate([{ transform: "rotateX(30deg) scale(1.12)" }],                 /* to its place in the CSS */
      { duration: lay.duration, easing: lay.easing, delay: ms("--duration-stagger") });
    var land = hero.querySelector(".plate--land"), ink = hero.querySelector(".plate--ink"), drop = spring(ms("--duration-slower") * 1.3, 0.3);
    hero.querySelectorAll(".plate--shadow").forEach(function (el) {
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms("--duration-slower"), easing: token("--ease-standard"), delay: ms("--duration-slow"), fill: "backwards" });
    });
    land.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ms("--duration-slower"), easing: token("--ease-standard"), delay: ms("--duration-base"), fill: "backwards" });
    ink.animate([{ opacity: 0, translate: "0 -14px" }, { opacity: 1, translate: "0 0" }], { duration: drop.duration, easing: drop.easing, delay: ms("--duration-slow") + ms("--duration-fast"), fill: "backwards" });
    var slip = hero.querySelector(".hero__slip"), fall = spring(ms("--duration-slower") * 1.35, 0.32);
    if (slip) slip.animate([{ translate: "8px -34px", rotate: "-6deg", scale: "1.06" }, { translate: "0 0", rotate: "-1.6deg", scale: "1" }],
      { duration: fall.duration, easing: fall.easing, delay: SLIP, fill: "backwards" });
  })();

  /* ---- the passage slips are dealt onto the table, each settling with a little give ---------------- */
  var cards = document.querySelectorAll(".pass");
  if (cards.length && moving() && "IntersectionObserver" in window) (function () {
    var deal = spring(ms("--duration-slower") * 1.25, 0.3), gap = ms("--duration-stagger") * 2;
    var seen = new IntersectionObserver(function (entries) {
      entries.filter(function (e) { return e.isIntersecting; }).forEach(function (entry, n) {
        var card = entry.target, i = Array.prototype.indexOf.call(cards, card);
        seen.unobserve(card);
        card.animate([{ opacity: 0, translate: "0 38px", rotate: (i % 2 ? -1.8 : 1.4) + "deg", scale: "0.96" }, { opacity: 1, translate: "0 0", rotate: "0deg", scale: "1" }],
          { duration: deal.duration, easing: deal.easing, delay: Math.min(n, 7) * gap, fill: "backwards" });
      });
    }, { threshold: 0.15 });
    cards.forEach(function (card) { seen.observe(card); });
  })();

  /* ---- the lamp switch: the knob is thrown across and settles with a spring --------------------- */
  var lampSwitch = document.getElementById("theme-switch");
  var knob = lampSwitch && lampSwitch.querySelector(".lamp__thumb");
  if (knob && window.MutationObserver) new MutationObserver(function () {
    if (!moving()) return;
    var on = lampSwitch.getAttribute("aria-checked") === "true", throwIt = spring(ms("--duration-slow") * 1.5, 0.45);
    knob.animate([{ translate: (on ? -16 : 16) + "px 0", scale: "1.45 0.8" }, { translate: "0 0", scale: "1" }],
      { duration: throwIt.duration, easing: throwIt.easing });
  }).observe(lampSwitch, { attributes: true, attributeFilter: ["aria-checked"] });

  /* ---- the week, told as you scroll: the tide stays pinned, a cursor walks through the days, each
     safe window is hatched in as it passes, and the day under the lamp flows into the next ----------- */
  var story = document.querySelector("[data-story]");
  if (story && "IntersectionObserver" in window) (function () {
    var plot = story.querySelector(".tide__plot");
    var cursor = story.querySelector(".tide__cursor"), dot = story.querySelector(".tide__dot"), read = story.querySelector(".tide__read");
    var shade = story.querySelector(".tide__shade"), pool = story.querySelector(".tide__pool");
    var labels = story.querySelectorAll(".tide__days > span"), times = story.querySelectorAll(".tide__times > span");
    var steps = story.querySelectorAll(".step");
    var dPlot = story.querySelector(".dayc__plot"), dCurve = story.querySelector(".dayc__curve"), dArea = story.querySelector(".dayc__area");
    var dDay = story.querySelector(".dayc__day"), dWins = story.querySelectorAll(".dayc__win"), dDot = story.querySelector(".dayc__dot");
    var NAMES = ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Mon"], NOW = 9 + 40 / 60;
    /* the tide model as the chart drew it: a height every 15 minutes from Tuesday 00:00 */
    var nums = story.querySelector(".tide__curve").getAttribute("d").match(/-?\d+(?:\.\d+)?/g).map(Number), level = [];
    for (var i = 1; i < nums.length; i += 2) level.push((600 - nums[i]) / 100);
    var WEEK = (level.length - 1) / 4;
    function heightAt(list, hours) {
      var f = clamp(hours * 4, 0, list.length - 1), n = Math.floor(f), t = f - n;
      return list[n] + ((n + 1 < list.length ? list[n + 1] : list[n]) - list[n]) * t;
    }
    function spanOf(el) {
      var x = parseFloat(el.style.getPropertyValue("--x")) || 0, w = parseFloat(el.style.getPropertyValue("--w")) || 0;
      return { el: el, a: x / 100 * WEEK, b: (x + w) / 100 * WEEK, lit: -1 };
    }
    var wins = Array.prototype.map.call(story.querySelectorAll(".tide__window"), spanOf);
    var light = Array.prototype.map.call(story.querySelectorAll(".tide__day"), spanOf);
    var DAYS = [0, 1, 2, 3, 4, 5, 6].map(function (k) { return level.slice(k * 96, k * 96 + 97); });
    var frame = 0, near = false, was = -1, day = -1, live = false;

    function smooth(t) { return t * t * (3 - 2 * t); }
    function progress() { var r = story.getBoundingClientRect(); return clamp(-r.top / Math.max(1, r.height - window.innerHeight), 0, 1); }
    /* every day has the same stretch of scroll: quick through the night, slow over the hours of daylight */
    function hourAt(p) {
      var k = Math.min(Math.floor(p * 7), 6), u = p * 7 - k;
      return clamp(k * 24 + 2 + 24 * (u + 0.6 * Math.sin(2 * Math.PI * u) / (2 * Math.PI)), NOW, WEEK - 0.25);
    }
    function clock(hours) {
      var m = Math.round(hours * 12) * 5, hh = Math.floor(m / 60) % 24, mm = m % 60;
      return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm;
    }
    function band(from, to) { return "inset(0 " + (100 - clamp(to, 0, 100)).toFixed(2) + "% 0 " + clamp(from, 0, 100).toFixed(2) + "%)"; }

    function render(t) {
      var W = plot.clientWidth, H = plot.clientHeight, x = t / WEEK * W, h = heightAt(level, t);
      cursor.style.transform = "translate3d(" + x.toFixed(1) + "px, 0, 0)";
      dot.style.transform = "translateY(" + ((600 - 100 * h) / 650 * H - 4.5).toFixed(1) + "px)";
      shade.style.transform = "translate3d(" + (x - W).toFixed(1) + "px, 0, 0)";
      pool.style.transform = "translate3d(" + x.toFixed(1) + "px, 0, 0)";
      var d = clamp(Math.floor(t / 24), 0, 6);
      read.textContent = NAMES[d] + " " + clock(t) + " · " + h.toFixed(1) + " m";
      read.classList.toggle("is-flipped", x > W - 180);       /* near the end of the week the label reads to the left */
      wins.forEach(function (w) {                            /* each window is hatched in as the cursor goes through it */
        var lit = clamp((t - w.a) / (w.b - w.a), 0, 1);
        if (lit !== w.lit) { w.lit = lit; w.el.style.setProperty("--lit", lit.toFixed(3)); }
      });
      if (d !== day) {
        day = d;
        [labels, times].forEach(function (list) { Array.prototype.forEach.call(list, function (el, n) { el.toggleAttribute("data-current", n === d); }); });
        Array.prototype.forEach.call(steps, function (el, n) { el.toggleAttribute("data-current", n === d); el.toggleAttribute("data-past", n < d); });
      }
      /* the day under the lamp: from 20:00 to 08:00 one day's curve flows into the next one's */
      var s = (t - 14) / 24, n = Math.floor(s), a = clamp(n, 0, 6), b = clamp(n + 1, 0, 6);
      var m = a === b ? 0 : smooth(clamp((s - n - 0.25) / 0.5, 0, 1)), path = "";
      for (var i = 0; i <= 96; i++) {
        var y = 600 - 100 * (DAYS[a][i] * (1 - m) + DAYS[b][i] * m);
        path += (i ? "L" : "M") + i * 10 + " " + y.toFixed(1);
      }
      dCurve.setAttribute("d", path);
      dArea.setAttribute("d", path + "L960 650L0 650Z");
      var la = light[a], lb = light[b];
      dDay.style.clipPath = band(((la.a - a * 24) * (1 - m) + (lb.a - b * 24) * m) / 0.24, ((la.b - a * 24) * (1 - m) + (lb.b - b * 24) * m) / 0.24);
      var slot = 0;
      [[a, 1 - m], [b, m]].forEach(function (pair, side) {
        if (side && a === b) return;
        wins.forEach(function (w) {
          if (Math.floor(w.a / 24) !== pair[0] || slot >= dWins.length) return;
          var el = dWins[slot++];
          el.style.clipPath = band((w.a - pair[0] * 24) / 0.24, (w.b - pair[0] * 24) / 0.24);
          el.style.opacity = pair[1].toFixed(3);
        });
      });
      for (; slot < dWins.length; slot++) dWins[slot].style.opacity = "0";
      var hod = t - d * 24, edge = clamp(Math.min(hod, 24 - hod) / 1.5, 0, 1);
      var dh = heightAt(DAYS[a], hod) * (1 - m) + heightAt(DAYS[b], hod) * m;
      dDot.style.transform = "translate3d(" + (hod / 24 * dPlot.clientWidth).toFixed(1) + "px, " + ((600 - 100 * dh) / 650 * dPlot.clientHeight).toFixed(1) + "px, var(--dot-z, 0px))";
      dDot.style.opacity = edge.toFixed(2);
    }
    function tick() {
      frame = 0;
      if (!live || !near) return;
      var p = progress();
      if (p !== was) { was = p; render(hourAt(p)); }
      frame = requestAnimationFrame(tick);
    }
    function start() {
      live = !reduce.matches;
      story.classList.toggle("is-live", live);
      if (!live) {                                             /* reduced motion: the week as it is, every window in */
        wins.forEach(function (w) { w.lit = -1; w.el.style.removeProperty("--lit"); });
        day = -1; was = -1;
        Array.prototype.forEach.call(steps, function (el) { el.removeAttribute("data-current"); el.removeAttribute("data-past"); });
        [labels, times].forEach(function (list) { Array.prototype.forEach.call(list, function (el) { el.removeAttribute("data-current"); }); });
        return;
      }
      was = -1;
      render(hourAt(progress()));
      if (!frame && near) frame = requestAnimationFrame(tick);
    }
    new IntersectionObserver(function (entries) {             /* the loop runs only while the story is on screen */
      near = entries[0].isIntersecting;
      if (near && live && !frame) frame = requestAnimationFrame(tick);
    }, { rootMargin: "20% 0px" }).observe(story);
    reduce.addEventListener("change", start);
    start();
  })();

  /* ---- real depth: the kit's depth.js (the hero's plates, the cards, the notes) ------------------- */
  /* on a touch screen the plates hold still: drifting them with the scroll would make the phone draw the
     whole chart again and again; the lamp still walks down the pencil line */
  if (hero && !fine.matches) hero.setAttribute("data-depth-scroll-shift", "0");
  import("../../vendor/scenes/depth.js").then(function (kit) {
    kit.mount(document.querySelector("main"), { tilt: 5 });
  }).catch(function () { /* without it the page is simply flat */ });
})();
