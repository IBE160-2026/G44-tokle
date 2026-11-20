// theme.js: the light/dark toggle (UX-DR2, AD-18; Edvard, 2026-11-20).
// The dark theme is the default and needs no JavaScript. This file applies a stored "light" pick
// before the page is drawn (it is loaded in <head>), shows the toggle, and switches on a click.
// The pick is kept in the browser; if storage is blocked, the toggle still switches this page.
(function () {
  "use strict";
  var KEY = "lo-theme";
  var root = document.documentElement;

  function stored() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function remember(theme) {
    try { window.localStorage.setItem(KEY, theme); } catch (e) { /* storage blocked: this page only */ }
  }
  function isLight() { return root.getAttribute("data-theme") === "light"; }
  function apply(theme) {
    if (theme === "light") { root.setAttribute("data-theme", "light"); } else { root.removeAttribute("data-theme"); }
  }

  apply(stored() === "light" ? "light" : "dark");

  function start() {
    var button = document.getElementById("theme-toggle");
    if (!button) { return; }
    function sync() { button.setAttribute("aria-pressed", isLight() ? "false" : "true"); }
    button.addEventListener("click", function () {
      var next = isLight() ? "dark" : "light";
      apply(next);
      remember(next);
      sync();
    });
    sync();
    button.hidden = false;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
