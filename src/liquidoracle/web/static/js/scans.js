/* The Scans page (AD-18, UX-DR30 to UX-DR32; Story 4.4). Only enhances: without it, the form shows the
   warning after the first submit, the estimate is the one for the number the page was drawn with, and
   reloading the page shows how far a Scan got.

   - The rough time estimate follows the Number of Wallets, from GET /scans/estimate?wallets=N, so its
     words stay in Python (AD-25).
   - The "very few bets" warning shows as soon as a recent Cut-off Date is chosen, and marks the form
     confirmed so one submit starts the Scan.
   - "Start Scan" marked aria-disabled does nothing when pressed (it stays focusable, UX-DR9).
   - While a Scan runs it polls GET /jobs/<id>/progress ({status, phase, done, total, message}) once a
     second: the bar, the step text and the tab title follow it, and a polite live region announces
     only a new step, each new 10% and the end. When the job ends, the running box, the Scan list and
     the button are taken from a fresh copy of the page; the form keeps what the user typed. */
(function () {
  "use strict";

  var POLL_MS = 1000;
  var MAX_FAILURES = 30; // about half a minute of failed polls: stop, reloading still works
  var ESTIMATE_DELAY_MS = 250;
  var DAY_MS = 86400000;

  function start() {
    var page = document.getElementById("scans-page");
    if (!page) return;
    var form = document.getElementById("new-scan");
    if (form) {
      enhanceForm(page, form);
    }
    if (window.fetch && window.DOMParser && page.getAttribute("data-progress")) {
      follow(page, page.getAttribute("data-progress"));
    }
  }

  // --- the form -------------------------------------------------------------------------------

  function enhanceForm(page, form) {
    form.addEventListener("submit", function (event) {
      var button = document.getElementById("start-scan");
      if (button && button.getAttribute("aria-disabled") === "true") event.preventDefault();
    });
    var cutoff = document.getElementById("cutoff");
    if (cutoff && !cutoff.readOnly) {
      cutoff.addEventListener("input", function () { updateWarning(form, cutoff); });
      cutoff.addEventListener("change", function () { updateWarning(form, cutoff); });
    }
    var wallets = document.getElementById("wallets");
    if (wallets && !wallets.readOnly && window.fetch) {
      var timer = null;
      wallets.addEventListener("input", function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () { updateEstimate(page, wallets.value); }, ESTIMATE_DELAY_MS);
      });
    }
  }

  function dayOf(text) {
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text || "");
    return match ? Date.UTC(+match[1], +match[2] - 1, +match[3]) : null;
  }

  function updateWarning(form, cutoff) {
    var warning = document.getElementById("cutoff-warning");
    var confirmed = document.getElementById("confirmed");
    if (!warning || !confirmed) return;
    var day = dayOf(cutoff.value);
    var today = dayOf(form.getAttribute("data-today"));
    var warnDays = Number(form.getAttribute("data-warn-days"));
    var recent = day !== null && today !== null && day < today && today - day < warnDays * DAY_MS;
    warning.hidden = !recent;
    confirmed.value = recent ? "1" : "";
    describe(cutoff, "cutoff-warning", recent);
  }

  function describe(field, id, on) {
    var ids = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(function (x) {
      return x && x !== id;
    });
    if (on) ids.push(id);
    if (ids.length) field.setAttribute("aria-describedby", ids.join(" "));
    else field.removeAttribute("aria-describedby");
  }

  function updateEstimate(page, value) {
    var url = page.getAttribute("data-estimate") + "?wallets=" + encodeURIComponent(value);
    fetch(url, { cache: "no-store", headers: { Accept: "application/json" } })
      .then(function (reply) {
        if (!reply.ok) throw new Error("estimate answered " + reply.status);
        return reply.json();
      })
      .then(function (answer) {
        var line = document.getElementById("wallets-estimate");
        var field = document.getElementById("wallets");
        if (!line || !field || field.value !== value) return; // a newer number is on its way
        line.textContent = answer.text || "";
        line.hidden = !answer.text;
      })
      .catch(function () { /* the last estimate stays */ });
  }

  // --- a running Scan -------------------------------------------------------------------------

  function follow(page, progressUrl) {
    var last = { key: null, bucket: null };
    var failures = 0;

    function poll() {
      window.setTimeout(function () {
        fetch(progressUrl, { cache: "no-store", headers: { Accept: "application/json" } })
          .then(function (reply) {
            if (reply.status === 404) return { status: "gone" };
            if (!reply.ok) throw new Error("progress answered " + reply.status);
            return reply.json();
          })
          .then(function (progress) {
            failures = 0;
            if (progress.status === "queued" || progress.status === "running") {
              show(page, progress, last);
              poll();
            } else {
              finish(page);
            }
          })
          .catch(function () {
            failures += 1;
            if (failures < MAX_FAILURES) poll();
            else document.title = page.getAttribute("data-page-title"); // gave up: no stale count in the tab
          });
      }, POLL_MS);
    }
    poll();
  }

  function show(page, progress, last) {
    var bar = document.getElementById("scan-progress");
    var step = document.getElementById("running-step");
    var total = Number(progress.total) || 0;
    var done = Number(progress.done) || 0;
    if (bar) {
      if (total > 0) {
        bar.max = total;
        bar.value = Math.min(done, total);
      } else {
        bar.removeAttribute("value"); // no count yet: an indeterminate bar
      }
      bar.setAttribute("aria-valuetext", progress.message);
    }
    if (step) step.textContent = progress.message;
    document.title = total > 0
      ? done + "/" + total + " · " + page.getAttribute("data-running-title")
      : page.getAttribute("data-page-title");

    // A step is its phase, its total and its words without the counts ("Reading Markets: "), so two
    // steps with the same total still count as two.
    var key = progress.phase + "|" + total + "|" + String(progress.message).replace(/[\d,]+/g, "");
    var bucket = total > 0 ? Math.floor((done * 10) / total) : 0;
    if (last.key !== null && (key !== last.key || bucket > last.bucket)) announce(progress.message);
    last.key = key;
    last.bucket = bucket; // also when the count went back (a resumed run), so the next 10% is heard
  }

  function announce(text) {
    var region = document.getElementById("scan-announce");
    if (!region) return;
    region.textContent = "";
    window.setTimeout(function () { region.textContent = text; }, 50); // a change, even for the same words
  }

  function finish(page) {
    fetch(page.getAttribute("data-page"), { cache: "no-store" })
      .then(function (reply) { return reply.text(); })
      .then(function (text) {
        var next = new DOMParser().parseFromString(text, "text/html");
        var focused = document.activeElement;
        var focusedId = focused && focused !== document.body ? focused.id : "";
        var hadFocus = ["scan-status", "scan-list"].some(function (id) {
          var box = document.getElementById(id);
          return box && box.contains(focused);
        });
        var swapped = ["scan-status", "scan-list"].every(function (id) {
          var mine = document.getElementById(id);
          var theirs = next.getElementById(id);
          if (!mine || !theirs) return false;
          mine.innerHTML = theirs.innerHTML;
          return true;
        });
        if (!swapped) {
          window.location.assign(page.getAttribute("data-page"));
          return;
        }
        var button = document.getElementById("start-scan");
        var fresh = next.getElementById("start-scan");
        if (button && fresh) {
          ["aria-disabled", "aria-describedby"].forEach(function (name) {
            if (fresh.hasAttribute(name)) button.setAttribute(name, fresh.getAttribute(name));
            else button.removeAttribute(name);
          });
        }
        if (hadFocus) {
          // The focused element was replaced: the same one again if it is still there, else the list's heading.
          var again = (focusedId && document.getElementById(focusedId)) || document.getElementById("scan-list-title");
          if (again) {
            if (again.id === "scan-list-title") again.setAttribute("tabindex", "-1");
            again.focus();
          }
        }
        document.title = next.title;
        var finished = page.getAttribute("data-scan");
        var nextPage = next.getElementById("scans-page");
        if (nextPage && nextPage.getAttribute("data-progress")) {
          page.setAttribute("data-progress", nextPage.getAttribute("data-progress"));
          page.setAttribute("data-scan", nextPage.getAttribute("data-scan"));
          follow(page, nextPage.getAttribute("data-progress")); // another Scan already queued
        } else {
          page.removeAttribute("data-progress");
          page.removeAttribute("data-scan");
        }
        var status = document.querySelector('#scan-list tr[data-scan="' + finished + '"] .scan-status');
        announce(status ? status.textContent : next.title);
      })
      .catch(function () {
        window.location.assign(page.getAttribute("data-page"));
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
