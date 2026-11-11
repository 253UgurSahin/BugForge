/* Tidewatch, level 3: Expressive. ../shared/app.js does the work (the lamp switch, the dialog, the table);
   this file shapes how it looks while it happens. Its first part is level 2's, unchanged: sections arrive
   once, figures count up, the night lamp spreads from its switch as a View Transition, the tide table and
   the plan note leave with a fade. Its second part, "level 3: Expressive", adds:
   - the sheet on the table: it leans a few degrees towards the hand, its three plates (the colours, the
     ink, the pencil) part a little with the hand and the scroll, and the slip floats above it;
   - the lamp: its pool follows the hand over the paper (the screen point is found back on the tilted sheet
     from its four corner pins), swings a little on its cable and settles; off the paper it rests on the
     pencil line and walks down it as the hero scrolls away. The sheet's shadow falls away from it;
   - the opening: the sheet is laid down, the lamp comes on, the ink lands, the slip lands, a corner springs up;
   - the week told as you scroll: the tide curve pinned, a cursor through the days (fast at night, slow over
     daylight), each safe window hatched in as it passes, and the day's own curve flowing into the next;
   - springs (the Web Animations API with a CSS linear() curve): the sheet, the slip, the passage slips, the switch;
   - the kit's depth.js (../../vendor/scenes/depth.js), loaded with import(): the passage slips and the notes.
     Without it, or without this script, the page is still whole: the sheet lies on the table, unlit by hand.
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

/* ================================================================ level 3: Expressive */
(function () {
  "use strict";
  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)");
  var style = getComputedStyle(root);
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

  /* ---- the sheet on the table, and the lamp over it --------------------------------------------- */
  /* What moves every frame is only ever a layer of its own, moved whole: the lamp, the ink and pencil
     plates, the sheet's shadow, the slip; nothing on the sheet is drawn again. The chart's lettering is HTML
     laid over its plates (level.css), because a browser lays out and repaints SVG text whenever the 3D turn
     above it changes. The sheet's lean towards the hand is one CSS transition that the compositor runs, set
     again only when the hand crosses into another part of the sheet. */
  var hero = document.querySelector(".hero");
  var sheet = hero && hero.querySelector(".sheet");
  if (sheet) (function () {
    var paper = sheet.querySelector(".sheet__paper");
    var pins = Array.prototype.slice.call(paper.querySelectorAll(".sheet__pin"));
    var lamp = paper.querySelector(".sheet__lamp"), glow = paper.querySelector(".sheet__glow");
    var ink = paper.querySelector(".plate--ink"), pencil = paper.querySelector(".plate--pencil");
    var cast = sheet.querySelector(".sheet__shadow");
    var slip = hero.querySelector(".hero__slip"), curl = hero.querySelector(".sheet__curl");
    var FIXES = [[720, 412], [524, 594], [258.6, 694.4]];   /* the pencil line's fixes, in chart units */
    /* what moves, each on a spring of its own: the lamp, the hand's pull on the plates, the page leaving */
    function S(v) { return { v: v, d: 0, t: v }; }
    var pool = { x: S(0), y: S(0) }, pull = { x: S(0), y: S(0) }, page = S(0);
    var hand = null, frame = 0, last = 0, size = null, map = null, lean = "", ready = false, laid = !moving();

    function measure() {
      var cs = getComputedStyle(root);
      var w = paper.offsetWidth, h = paper.offsetHeight, s = Math.max(w / 860, h / 900);
      size = { w: w, h: h, s: s, ox: w - 1000 * s, oy: h - 900 * s, k: parseFloat(cs.getPropertyValue("--l3-k")) || 1,
        top: hero.getBoundingClientRect().top + window.scrollY, tall: hero.offsetHeight };
    }
    function onSheet(x, y) { return { x: size.ox + x * size.s, y: size.oy + y * size.s }; }
    /* nobody pointing: the lamp rests on the pencil line, past the 14:20 fix, and walks on down it towards
       the 15:00 fix as the hero scrolls away */
    function rest(q) {
      var p = FIXES.map(function (f) { return onSheet(f[0], f[1]); });
      var a = Math.hypot(p[1].x - p[0].x, p[1].y - p[0].y), b = Math.hypot(p[2].x - p[1].x, p[2].y - p[1].y);
      var d = (0.2 + 0.72 * clamp(q, 0, 1)) * (a + b), i = d < a ? 0 : 1, f = i ? (d - a) / b : d / a;
      return { x: p[i].x + (p[i + 1].x - p[i].x) * f, y: p[i].y + (p[i + 1].y - p[i].y) * f };
    }
    /* where the sheet lies on the page, from its four corner pins: the plane's homography, so a point of
       the screen can be found back on the paper however it is turned. Read only while the sheet is still. */
    function chart() {
      var q = pins.map(function (el) { var r = el.getBoundingClientRect(); return [r.left + window.scrollX, r.top + window.scrollY]; });
      var x0 = q[0][0], y0 = q[0][1], x1 = q[1][0], y1 = q[1][1], x2 = q[2][0], y2 = q[2][1], x3 = q[3][0], y3 = q[3][1];
      var dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3, dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
      var den = dx1 * dy2 - dx2 * dy1, g = den ? (dx3 * dy2 - dx2 * dy3) / den : 0, h = den ? (dx1 * dy3 - dx3 * dy1) / den : 0;
      var m = [x1 - x0 + g * x1, x3 - x0 + h * x3, x0, y1 - y0 + g * y1, y3 - y0 + h * y3, y0, g, h, 1];
      var A = m[4] * m[8] - m[5] * m[7], B = m[5] * m[6] - m[3] * m[8], C = m[3] * m[7] - m[4] * m[6];
      var det = m[0] * A + m[1] * B + m[2] * C;
      if (!det) { map = null; return; }
      var inv = [A, m[2] * m[7] - m[1] * m[8], m[1] * m[5] - m[2] * m[4], B, m[0] * m[8] - m[2] * m[6], m[2] * m[3] - m[0] * m[5],
        C, m[1] * m[6] - m[0] * m[7], m[0] * m[4] - m[1] * m[3]];
      var xs = [x0, x1, x2, x3], ys = [y0, y1, y2, y3];
      map = {
        find: function (x, y) {
          var w = inv[6] * x + inv[7] * y + inv[8];
          return { u: (inv[0] * x + inv[1] * y + inv[2]) / w, v: (inv[3] * x + inv[4] * y + inv[5]) / w };
        },
        l: Math.min.apply(null, xs), r: Math.max.apply(null, xs), t: Math.min.apply(null, ys), b: Math.max.apply(null, ys)
      };
    }
    function progress() { return reduce.matches ? 0 : clamp((window.scrollY - size.top) / Math.max(1, size.tall * 0.85), 0, 1); }
    /* the lean: the part of the sheet under the hand sinks a few degrees, in steps of a third of the sheet */
    function leanTo(nx, ny) {
      var qx = Math.round(nx * 2) / 2, qy = Math.round(ny * 2) / 2, ax = -2.4 * qy, ay = 3.4 * qx, a = Math.hypot(ax, ay);
      var next = a ? (ax / a).toFixed(3) + " " + (ay / a).toFixed(3) + " 0 " + a.toFixed(2) + "deg" : "0deg";
      if (next === lean) return;
      lean = next;
      sheet.style.rotate = next;
      if (curl) curl.style.setProperty("--lean", a ? (ax / a).toFixed(3) + ", " + (ay / a).toFixed(3) + ", 0, " + a.toFixed(2) + "deg" : "1, 0, 0, 0deg");
    }
    function aim() {
      page.t = progress();
      var at = null;
      if (hand && map && laid && !reduce.matches) {
        var x = hand.x + window.scrollX, y = hand.y + window.scrollY;
        var nx = clamp((x - (map.l + map.r) / 2) / ((map.r - map.l) / 2), -1, 1), ny = clamp((y - (map.t + map.b) / 2) / ((map.b - map.t) / 2), -1, 1);
        pull.x.t = nx; pull.y.t = ny;
        var uv = map.find(x, y);
        /* only on the paper itself: off it, over the words or the slip, the lamp goes back to the pencil line */
        if (!hand.off && uv.u > -0.02 && uv.u < 1.02 && uv.v > -0.02 && uv.v < 1.02) { at = { x: uv.u * size.w, y: uv.v * size.h }; leanTo(nx, ny); }
        else leanTo(0, 0);
      } else {
        pull.x.t = 0; pull.y.t = 0;
        if (laid && !reduce.matches) leanTo(0, 0);
      }
      if (!at) at = rest(page.t);
      pool.x.t = clamp(at.x, size.w * 0.04, size.w * 0.96);
      pool.y.t = clamp(at.y, size.h * 0.04, size.h * 0.96);
    }
    function draw() {
      var at = "translate3d(" + pool.x.v.toFixed(1) + "px, " + pool.y.v.toFixed(1) + "px, 0)", k = 1 / size.k;
      lamp.style.transform = at;
      glow.style.transform = at;
      /* the plates part: the ink floats a little over the colours, the pencil a little more; with the hand,
         and with the page as it leaves */
      ink.style.transform = "translate3d(" + (8 * pull.x.v).toFixed(2) + "px, " + (7 * pull.y.v - 30 * page.v).toFixed(2) + "px, 0) scale(" + k + ")";
      pencil.style.transform = "translate3d(" + (17 * pull.x.v).toFixed(2) + "px, " + (14 * pull.y.v - 70 * page.v).toFixed(2) + "px, 0) scale(" + k + ")";
      /* the sheet's shadow falls away from the lamp */
      var sx = 12 + (size.w / 2 - pool.x.v) * 0.05, sy = 18 + (size.h / 2 - pool.y.v) * 0.05;
      cast.style.transform = "translate3d(" + sx.toFixed(1) + "px, " + sy.toFixed(1) + "px, -2px)";
      if (slip) {
        slip.style.translate = (20 * pull.x.v).toFixed(1) + "px " + (14 * pull.y.v - (fine.matches ? 130 : 24) * page.v).toFixed(1) + "px";
        slip.style.setProperty("--slip-sx", clamp(4 + (0.5 - pool.x.v / size.w) * 30, -12, 18).toFixed(1));
        slip.style.setProperty("--slip-sy", clamp(8 + (0.5 - pool.y.v / size.h) * 20, -4, 20).toFixed(1));
      }
    }
    function settle() { [pool.x, pool.y, pull.x, pull.y, page].forEach(function (s) { s.v = s.t; s.d = 0; }); }
    function tick(now) {
      frame = 0;
      if (!ready) return;
      aim();
      if (reduce.matches) { settle(); draw(); last = 0; return; }
      var dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60, busy = false;
      last = now;
      /* the lamp hangs on a cable: it swings after the hand and settles, a little past and back; the plates
         follow the hand more heavily; the page's own scroll is followed closely */
      [[pool.x, 7, 0.62], [pool.y, 7, 0.62], [pull.x, 5, 0.9], [pull.y, 5, 0.9], [page, 14, 1]].forEach(function (e) {
        var s = e[0], w = e[1], z = e[2];
        s.d += (w * w * (s.t - s.v) - 2 * z * w * s.d) * dt;
        s.v += s.d * dt;
        if (Math.abs(s.t - s.v) > 0.02 || Math.abs(s.d) > 0.02) busy = true;
      });
      draw();
      if (busy) wake(); else last = 0;
    }
    /* nothing is drawn while the hero is off screen or the tab is hidden */
    var near = true;
    if ("IntersectionObserver" in window) new IntersectionObserver(function (entries) {
      near = entries[0].isIntersecting;
      if (near) wake();
    }).observe(hero);
    function wake() { if (!frame && near && !document.hidden) frame = requestAnimationFrame(tick); }
    function reset() { measure(); if (laid) chart(); aim(); settle(); draw(); }

    window.addEventListener("pointermove", function (event) {
      if (event.pointerType === "touch" || !fine.matches) return;
      var target = event.target, off = Boolean(target.closest && target.closest(".topbar, .hero__slip, .hero__actions"));
      hand = hero.contains(target) ? { x: event.clientX, y: event.clientY, off: off } : null;
      wake();
    }, { passive: true });
    document.documentElement.addEventListener("pointerleave", function () { hand = null; wake(); });
    window.addEventListener("scroll", wake, { passive: true });
    window.addEventListener("resize", function () { reset(); wake(); });
    reduce.addEventListener("change", function () { if (reduce.matches) { lean = ""; sheet.style.rotate = ""; if (curl) curl.style.removeProperty("--lean"); } reset(); wake(); });
    document.addEventListener("visibilitychange", function () { if (!document.hidden) wake(); });
    /* once the lean has come to rest, the sheet is read again */
    sheet.addEventListener("transitionend", function (event) { if (event.target === sheet) { chart(); wake(); } });

    /* the CSS puts the lamp over the middle of the sheet; from here on its place is a transform */
    [lamp, glow].forEach(function (el) { el.style.left = "0"; el.style.top = "0"; });
    measure();
    if (laid) chart();
    aim(); settle();
    ready = true;
    draw();

    /* the opening: the sheet is laid down on the table, its shadow tightens under it, the lamp comes on,
       the ink plate lands on the colours, the pencil draws (level 2's CSS), the slip lands, and last the
       corner that was folded down springs up */
    if (!moving()) return;
    var lay = spring(ms("--duration-draw") * 1.5, 0.16), drop = spring(ms("--duration-slower") * 1.3, 0.3);
    var down = sheet.animate([{ translate: "0 -36px 70px", rotate: "x -20deg" }, { translate: "0 0 0", rotate: "x 0deg" }],
      { duration: lay.duration, easing: lay.easing, delay: ms("--duration-stagger"), fill: "backwards" });
    down.finished.then(function () { laid = true; chart(); wake(); }, function () { laid = true; });
    cast.animate([{ opacity: 0, scale: "1.16" }, { opacity: 1, scale: "1" }],
      { duration: lay.duration, easing: token("--ease-standard"), delay: ms("--duration-base"), fill: "backwards" });
    [lamp, glow].forEach(function (el) {
      el.animate([{ scale: "0.3", opacity: el === glow ? 0 : 1 }, { scale: "1", opacity: 1 }],
        { duration: lay.duration, easing: lay.easing, delay: ms("--duration-slow"), fill: "backwards" });
    });
    ink.animate([{ opacity: 0, translate: "0 -18px" }, { opacity: 1, translate: "0 0" }],
      { duration: drop.duration, easing: drop.easing, delay: ms("--duration-slow") + ms("--duration-fast"), fill: "backwards" });
    var fall = spring(ms("--duration-slower") * 1.35, 0.32);
    if (slip) slip.animate([{ transform: "translate(8px, -40px) rotate(-6deg) scale(1.06)" }, { transform: "rotate(-1.6deg)" }],
      { duration: fall.duration, easing: fall.easing, delay: SLIP, fill: "backwards" });
    /* the corner lies folded flat while the sheet comes down, then springs up */
    var flip = spring(ms("--duration-slower") * 1.5, 0.42);
    if (curl) curl.animate([{ opacity: 0, "--curl-a": "-179deg", offset: 0 }, { opacity: 1, offset: 0.08 }, { opacity: 1, "--curl-a": "-146deg" }],
      { duration: flip.duration, easing: flip.easing, delay: SLIP + ms("--duration-slow"), fill: "backwards" });
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
    var frame = 0, near = false, was = -1, day = -1, live = false, changed = 0;

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
        /* one day on: the old day leaves, then the new one comes (level.css). Further, or again within a
           moment (a jump, a fast scroll): straight to the new day, so two days never overprint */
        var now = performance.now(), jump = day < 0 || Math.abs(d - day) > 1 || now - changed < 360;
        day = d;
        changed = now;
        if (jump) story.classList.add("is-jumping");
        [labels, times].forEach(function (list) { Array.prototype.forEach.call(list, function (el, n) { el.toggleAttribute("data-current", n === d); }); });
        Array.prototype.forEach.call(steps, function (el, n) { el.toggleAttribute("data-current", n === d); el.toggleAttribute("data-past", n < d); });
        if (jump) { void getComputedStyle(steps[d]).opacity; story.classList.remove("is-jumping"); }
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
      dDot.style.transform = "translate3d(" + (hod / 24 * dPlot.clientWidth).toFixed(1) + "px, " + ((600 - 100 * dh) / 650 * dPlot.clientHeight).toFixed(1) + "px, 0)";
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

  /* ---- real depth from the kit's depth.js: the passage slips lean and lift, the notes stack ---------- */
  import("../../vendor/scenes/depth.js").then(function (kit) {
    kit.mount(document.querySelector("main"), { tilt: 5 });
  }).catch(function () { /* without it the page is simply flat */ });
})();
