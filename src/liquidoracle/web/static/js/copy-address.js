/* Copy address (UX-DR21, AD-18; Story 3.4). Only enhances: without it, the copy button stays hidden
   and the address can be selected by hand.

   The script marks the page (class has-copy on <html>), which shows every copy button, and listens
   for clicks on the whole page, so a Verdict that progress.js swaps in later works too. On success
   the button shows "Copied" for 2 seconds and the status line announces "Address copied"; if the
   browser refuses, the error under the card is shown and announced and the address is selected.
   Every word comes from the page (AD-25): the button's data- attributes and the error line. */
(function () {
  "use strict";

  var SHOW_MS = 2000;
  var ANNOUNCE_MS = 50; // a status line emptied first announces the same words again
  var timer = null;
  var announceTimer = null;
  var root = document.documentElement;

  function isMac() {
    // Chrome's userAgentData says "macOS", navigator.platform (Safari, Firefox) "MacIntel". Only a Mac:
    // an iPhone has no keyboard, and iPadOS already reports MacIntel.
    var platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    return /mac/i.test(platform);
  }

  function announce(status, text) {
    window.clearTimeout(announceTimer); // only the latest attempt is announced
    status.textContent = "";
    announceTimer = window.setTimeout(function () { status.textContent = text; }, ANNOUNCE_MS);
  }

  function reset(button) {
    window.clearTimeout(timer);
    button.querySelector(".copy-label").textContent = "";
    button.classList.remove("is-copied");
  }

  function failed(card, status) {
    var error = card.querySelector(".copy-error");
    var errorText = card.querySelector(".copy-error-text");
    var button = card.querySelector(".copy-button");
    reset(button); // a refusal right after a copy never leaves "Copied" beside the error
    if (isMac()) errorText.textContent = button.getAttribute("data-mac-text");
    error.hidden = false;
    announce(status, errorText.textContent);
    var range = document.createRange();
    range.selectNodeContents(card.querySelector(".address"));
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function copied(button, status) {
    var label = button.querySelector(".copy-label");
    label.textContent = button.getAttribute("data-copied");
    button.classList.add("is-copied");
    announce(status, button.getAttribute("data-done"));
    window.clearTimeout(timer);
    timer = window.setTimeout(function () { reset(button); }, SHOW_MS);
  }

  function copy(button) {
    var card = button.closest(".address-card");
    if (!card) return;
    var status = card.querySelector(".copy-status");
    card.querySelector(".copy-error").hidden = true;
    var address = card.querySelector(".address").textContent.trim();
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      failed(card, status);
      return;
    }
    navigator.clipboard.writeText(address).then(
      function () { copied(button, status); },
      function () { failed(card, status); }
    );
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest(".copy-button");
    if (button) copy(button);
  });
  root.classList.add("has-copy");
})();
