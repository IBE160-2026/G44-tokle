/* Luck chart exploring (UX-DR26, UX-DR27, UX-DR28, AD-18; Story 3.2). Only enhances: without it
   the chart card is complete, as in Story 3.1. Adapted from the prototype in mockups/verdict.html.

   It writes no words and counts nothing. Each bar carries its range and replay count (data-range,
   data-count), the chart says which bar holds the Wallet's Real PnL and the first bar the marker
   lights (data-marker-bar, data-tail-from; that comes from the exact stored count, never from the
   bars), and the tail sentence and the "Highlight on" / "Highlight off" words are in the page.
   The script shows, hides and moves those parts:

   - pointing at a bar (or tapping it) shows its tooltip; it stays while the pointer is on it and
     for 300 ms after, and Esc hides it (WCAG 1.4.13); within three bars of the marker it moves aside,
     and it always takes a place on the card that is clear of the marker's dot and label;
   - the bars are one slider, "Replays by result": Left/Down and Right/Up step one bar, Page Down/Up
     ten, Home/End go to the ends;
   - the marker button lights the tail and shows the tail label while pointed at or focused; a click
     or Enter pins it, a second click, Esc or a slider step unpins it;
   - the first time the chart comes into view, the bars grow and the marker drops in (under a
     second), unless the system asks for reduced motion.

   `window.LiquidOracleChart.enhance(root)` is also called by progress.js after it swaps in a
   Verdict page. Enhancing the same chart twice does nothing. */
(function () {
  "use strict";

  var HIDE_AFTER_MS = 300; // tooltip and tail stay this long after the pointer leaves (WCAG 1.4.13)
  var NEAR_MARKER = 3; // bars this close to the marker's bar get their tooltip at the side
  var PAGE_STEP = 10;
  var BUILD_MS = 1000; // the whole build-up ends within this; the CSS needs 560 + 260 ms
  var reduced = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  function enhance(root) {
    var charts = (root || document).querySelectorAll(".chart-card .chart");
    for (var i = 0; i < charts.length; i++) {
      if (charts[i].getAttribute("data-enhanced") === "true") continue;
      charts[i].setAttribute("data-enhanced", "true");
      setUp(charts[i].closest(".chart-card"), charts[i]);
    }
  }

  function setUp(card, chart) {
    var plot = chart.querySelector(".chart-plot");
    var svg = chart.querySelector(".chart-svg");
    var bars = chart.querySelectorAll(".chart-bar");
    var slider = chart.querySelector(".chart-explore");
    var button = chart.querySelector(".chart-marker-button");
    var tailLabel = chart.querySelector(".chart-tail-label");
    var tip = chart.querySelector(".chart-tip");
    var dot = chart.querySelector(".chart-dot");
    var markerLabel = chart.querySelector(".chart-marker-label");
    var live = card.querySelector(".chart-live");
    if (!plot || !svg || !bars.length || !slider || !button || !tailLabel || !tip || !live) return;

    var count = bars.length;
    var viewWidth = svg.viewBox.baseVal.width;
    var markerBar = whole(chart.getAttribute("data-marker-bar"), 0);
    var tailFrom = whole(chart.getAttribute("data-tail-from"), count);
    var active = -1; // the bar with the tooltip, or -1
    var current = markerBar; // the slider's value; kept when the tooltip hides (Esc, the tail)
    var pinned = false;
    var tailHover = false;
    var hideTip = null;
    var hideTail = null;

    var parts = card.querySelectorAll("[data-explore]");
    for (var p = 0; p < parts.length; p++) parts[p].hidden = false;
    var stills = card.querySelectorAll("[data-no-explore]");
    for (var s = 0; s < stills.length; s++) stills[s].hidden = true;

    buildUp(plot);

    // --- Tooltip and slider -------------------------------------------------------------------

    function setActive(i) {
      window.clearTimeout(hideTip);
      if (active >= 0) bars[active].classList.remove("is-active");
      active = i;
      if (i < 0) {
        tip.classList.remove("is-shown");
        return;
      }
      var bar = bars[i];
      current = i;
      bar.classList.add("is-active");
      tip.textContent = "";
      tip.appendChild(document.createTextNode(bar.getAttribute("data-range")));
      tip.appendChild(document.createElement("br"));
      var strong = document.createElement("strong");
      strong.textContent = bar.getAttribute("data-count");
      tip.appendChild(strong);
      placeTip(i);
      tip.classList.add("is-shown");
      slider.setAttribute("aria-valuenow", String(i + 1));
      slider.setAttribute("aria-valuetext", bar.getAttribute("data-range") + ": " + bar.getAttribute("data-count"));
    }

    // The tooltip tries its places in order: above the bar (not within three bars of the marker),
    // beside it away from the marker, then beside it on the other side. It takes the first place that
    // stays on the card and clear of the marker's dot and label (Story 3.2 review: an end bar next to
    // the marker pushed a side tooltip off the card).
    function placeTip(i) {
      var bar = bars[i];
      var x = parseFloat(bar.getAttribute("x"));
      var centre = (100 * (x + parseFloat(bar.getAttribute("width")) / 2)) / viewWidth;
      var height = parseFloat(bar.getAttribute("height"));
      var away = i <= markerBar ? "left" : "right";
      var places = [away, away === "left" ? "right" : "left"];
      if (Math.abs(i - markerBar) > NEAR_MARKER) places.unshift("above");
      tip.style.left = centre + "%";
      for (var k = 0; k < places.length; k++) {
        putTip(places[k], centre, height);
        if (onCard(tip) && !touches(tip, dot) && !touches(tip, markerLabel)) return;
      }
      putTip(places[0], centre, height); // nothing fits (a very narrow card): the first choice
    }

    function putTip(place, centre, height) {
      if (place === "above") {
        tip.style.bottom = "calc(" + height + "% + 10px)";
        tip.style.transform = centre < 18 ? "translateX(-12%)" : centre > 82 ? "translateX(-88%)" : "translateX(-50%)";
      } else {
        tip.style.bottom = Math.max(height / 2, 4) + "%";
        tip.style.transform = place === "left" ? "translateX(calc(-100% - 14px))" : "translateX(14px)";
      }
    }

    function onCard(element) {
      var r = element.getBoundingClientRect();
      var c = card.getBoundingClientRect();
      return r.left >= c.left && r.right <= c.right;
    }

    function hideTipSoon() {
      window.clearTimeout(hideTip);
      hideTip = window.setTimeout(function () { setActive(-1); }, HIDE_AFTER_MS);
    }

    function barAt(clientX) {
      var box = plot.getBoundingClientRect();
      var slot = ((clientX - box.left) / box.width) * viewWidth;
      var best = 0;
      var bestDistance = Infinity;
      for (var i = 0; i < count; i++) {
        var centre = parseFloat(bars[i].getAttribute("x")) + parseFloat(bars[i].getAttribute("width")) / 2;
        var distance = Math.abs(centre - slot);
        if (distance < bestDistance) {
          best = i;
          bestDistance = distance;
        }
      }
      return best;
    }

    slider.addEventListener("pointermove", function (event) {
      if (pinned) return;
      var i = barAt(event.clientX);
      if (i !== active) setActive(i);
      else window.clearTimeout(hideTip);
    });
    // A tap or click on a bar shows that bar (touch screens send no pointermove before a tap); like a
    // slider step, it ends a pinned highlight.
    slider.addEventListener("pointerdown", function (event) {
      if (pinned) {
        unpin();
        showTail(false);
      }
      setActive(barAt(event.clientX));
    });
    slider.addEventListener("pointerleave", function (event) {
      if (event.pointerType === "touch") return; // a finger "leaves" on every tap: keep it until the next tap or Esc
      if (document.activeElement !== slider) hideTipSoon();
    });
    tip.addEventListener("pointerenter", function () { window.clearTimeout(hideTip); });
    tip.addEventListener("pointerleave", function () {
      if (document.activeElement !== slider) hideTipSoon();
    });

    slider.addEventListener("focus", function () {
      if (!pinned) setActive(active >= 0 ? active : current);
    });
    slider.addEventListener("blur", function () { setActive(-1); });
    slider.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return; // leave Alt+Left (back) and the like to the browser
      var i = active < 0 ? current : active;
      var steps = {
        ArrowLeft: i - 1, ArrowDown: i - 1, ArrowRight: i + 1, ArrowUp: i + 1,
        PageDown: i - PAGE_STEP, PageUp: i + PAGE_STEP, Home: 0, End: count - 1
      };
      if (!Object.prototype.hasOwnProperty.call(steps, event.key)) return;
      event.preventDefault();
      if (pinned) {
        unpin();
        showTail(false);
      }
      setActive(Math.max(0, Math.min(count - 1, steps[event.key])));
    });

    // --- Marker button and tail ---------------------------------------------------------------

    function showTail(on) {
      plot.classList.toggle("show-tail", on);
      for (var i = 0; i < count; i++) bars[i].classList.toggle("is-tail", on && i >= tailFrom);
      if (on) setActive(-1);
    }

    function unpin() {
      if (!pinned) return;
      pinned = false;
      button.setAttribute("aria-pressed", "false");
      live.textContent = live.getAttribute("data-highlight-off");
    }

    function tailEnter() {
      window.clearTimeout(hideTail);
      tailHover = true;
      showTail(true);
    }

    function tailLeave() {
      tailHover = false;
      window.clearTimeout(hideTail);
      hideTail = window.setTimeout(function () {
        if (!pinned && !tailHover && document.activeElement !== button) showTail(false);
      }, HIDE_AFTER_MS);
    }

    button.addEventListener("pointerenter", tailEnter);
    button.addEventListener("pointerleave", tailLeave);
    tailLabel.addEventListener("pointerenter", tailEnter);
    tailLabel.addEventListener("pointerleave", tailLeave);
    button.addEventListener("focus", function () { showTail(true); });
    button.addEventListener("blur", function () {
      if (!pinned && !tailHover) showTail(false);
    });
    button.addEventListener("click", function () {
      if (pinned) {
        unpin();
        showTail(tailHover || document.activeElement === button);
        return;
      }
      pinned = true;
      button.setAttribute("aria-pressed", "true");
      showTail(true);
      live.textContent = live.getAttribute("data-highlight-on");
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || !document.body.contains(chart)) return;
      if (pinned || plot.classList.contains("show-tail")) {
        unpin();
        showTail(false);
      }
      if (active >= 0) setActive(-1);
    });
  }

  // --- Build-up (UX-DR28): once per view, never with reduced motion ----------------------------

  function buildUp(plot) {
    if ((reduced && reduced.matches) || !("IntersectionObserver" in window)) return;
    plot.classList.add("pre-build");
    var observer = new IntersectionObserver(function (entries) {
      if (!entries[0].isIntersecting) return;
      observer.disconnect();
      window.requestAnimationFrame(function () {
        plot.classList.remove("pre-build");
        plot.classList.add("is-building");
        window.setTimeout(function () { plot.classList.remove("is-building"); }, BUILD_MS);
      });
    }, { threshold: 0.35 });
    observer.observe(plot);
  }

  function touches(a, b) {
    if (!a || !b) return false;
    var r = a.getBoundingClientRect();
    var q = b.getBoundingClientRect();
    return r.left < q.right && q.left < r.right && r.top < q.bottom && q.top < r.bottom;
  }

  function whole(text, fallback) {
    var n = parseInt(text, 10);
    return isNaN(n) ? fallback : n;
  }

  window.LiquidOracleChart = { enhance: enhance };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { enhance(document); });
  } else {
    enhance(document);
  }
})();
