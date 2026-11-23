/* Lookup progress (AD-18, UX-DR22; Story 2.5). Only enhances: without it, the "Reload this page"
   link shows the result.

   On the fetching page it polls GET /jobs/<id>/progress ({status, phase, done, total, message})
   once a second. When the job is no longer queued or running, it fetches the page again (the
   server renders the result: Verdict, no history, Polymarket did not answer), puts its content in
   place of this block, and moves focus to the new page's main heading. A luck chart in the new
   content is handed to chart.js, which the fetching page also loads. */
(function () {
  "use strict";

  var POLL_MS = 1000;
  var MAX_FAILURES = 30; // about half a minute of failed polls: stop, the reload link still works

  function start() {
    var block = document.getElementById("job-block");
    if (!block || !window.fetch || !window.DOMParser) return;
    poll(block.getAttribute("data-progress"), block.getAttribute("data-page"), 0);
  }

  function poll(progressUrl, pageUrl, failures) {
    window.setTimeout(function () {
      fetch(progressUrl, { cache: "no-store", headers: { Accept: "application/json" } })
        .then(function (reply) {
          if (reply.status === 404) return { status: "gone" };
          if (!reply.ok) throw new Error("progress answered " + reply.status);
          return reply.json();
        })
        .then(function (progress) {
          if (progress.status === "queued" || progress.status === "running") {
            poll(progressUrl, pageUrl, 0);
          } else {
            showResult(pageUrl);
          }
        })
        .catch(function () {
          if (failures + 1 < MAX_FAILURES) poll(progressUrl, pageUrl, failures + 1);
        });
    }, POLL_MS);
  }

  function showResult(pageUrl) {
    fetch(pageUrl, { cache: "no-store" })
      .then(function (reply) {
        return reply.text().then(function (text) { return { url: reply.url, text: text }; });
      })
      .then(function (answer) {
        var next = new DOMParser().parseFromString(answer.text, "text/html");
        var nextMain = next.getElementById("content");
        var main = document.getElementById("content");
        if (!nextMain || !main) {
          window.location.assign(pageUrl);
          return;
        }
        main.innerHTML = nextMain.innerHTML;
        document.title = next.title;
        if (answer.url && window.history && window.history.replaceState) {
          window.history.replaceState(null, "", answer.url); // a reload now shows this same result
        }
        // Scripts in swapped-in HTML do not run, so the luck chart is enhanced here (chart.js, Story 3.2).
        if (window.LiquidOracleChart) window.LiquidOracleChart.enhance(main);
        var heading = main.querySelector("h1");
        if (heading) {
          heading.setAttribute("tabindex", "-1");
          heading.focus();
        }
        start(); // a new fetching block (a lookup queued again) is followed the same way
      })
      .catch(function () {
        window.location.assign(pageUrl);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
