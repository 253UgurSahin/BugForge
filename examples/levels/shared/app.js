/* Tidewatch: the little script. The lamp (theme), the plan dialog, the tide table.
   Level 1 motion only: a fade when something appears, and none when the reader asks for less. */
(function () {
  "use strict";
  var root = document.documentElement;
  var calm = window.matchMedia("(prefers-reduced-motion: reduce)");

  function fadeIn(el) {
    if (calm.matches || !el.animate) return;
    el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
  }

  /* ---- the lamp: day chart or night chart ------------------------------------------------- */
  var lamp = document.getElementById("theme-switch");
  var night = window.matchMedia("(prefers-color-scheme: dark)");
  function isNight() {
    var set = root.getAttribute("data-theme");
    return set ? set === "dark" : night.matches;
  }
  function showLamp() { lamp.setAttribute("aria-checked", String(isNight())); }
  lamp.addEventListener("click", function () {
    var next = isNight() ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("tidewatch-theme", next); } catch (e) { /* private mode: the choice lasts for this visit */ }
    showLamp();
  });
  night.addEventListener("change", showLamp);
  showLamp();

  /* ---- the plan dialog --------------------------------------------------------------------- */
  var plan = document.getElementById("plan");
  var form = document.getElementById("plan-form");
  var from = document.getElementById("plan-from");
  var to = document.getElementById("plan-to");
  var sameError = document.getElementById("plan-to-error");
  var status = document.getElementById("plan-status");

  function checkLeg() {
    var same = from.value === to.value;
    to.setCustomValidity(same ? "Pick a harbour other than the one you leave from." : "");
    sameError.hidden = !same;
    to.setAttribute("aria-invalid", String(same));
  }
  from.addEventListener("change", checkLeg);
  to.addEventListener("change", checkLeg);

  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-open-plan]");
    if (opener) {
      if (opener.dataset.to) { from.value = "Vlissingen"; to.value = opener.dataset.to; }
      checkLeg();
      if (typeof plan.showModal === "function") plan.showModal(); else plan.setAttribute("open", "");
      return;
    }
    if (event.target.closest("[data-close-plan]")) { plan.close("cancel"); return; }
    if (event.target.closest("[data-close-status]")) { status.hidden = true; }
  });
  plan.addEventListener("click", function (event) {      /* a click on the dimmed chart closes the slip */
    if (event.target === plan) plan.close("cancel");
  });
  plan.addEventListener("close", function () {
    if (plan.returnValue !== "plan") return;
    var data = new FormData(form);
    var row = document.querySelector('#tide-table tr[data-date="' + data.get("date") + '"]');
    var day = row ? row.dataset.day : data.get("date");
    var windows = row ? row.dataset.windows : "";
    var text = data.get("from") + " to " + data.get("to") + ", " + day + ", at " + data.get("speed") + " kn. ";
    text += windows ? "Safe window " + windows.replace(", ", " and ") + "." : "No safe window that day" + (row ? ": wind " + row.dataset.wind + "." : ".");
    status.textContent = text;
    var close = document.createElement("button");
    close.type = "button"; close.textContent = "Close"; close.setAttribute("data-close-status", "");
    status.appendChild(close);
    status.hidden = false;
    fadeIn(status);
  });

  /* ---- the tide table behind its button ----------------------------------------------------- */
  var toggle = document.getElementById("table-toggle");
  var toggleText = document.getElementById("table-toggle-text");
  var table = document.getElementById("tide-table");
  table.hidden = true;                                   /* without this script the table simply shows */
  toggle.addEventListener("click", function () {
    var open = table.hidden;
    table.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggleText.textContent = open ? "Hide the table" : "Show as table";
    if (open) fadeIn(table);
  });
})();
