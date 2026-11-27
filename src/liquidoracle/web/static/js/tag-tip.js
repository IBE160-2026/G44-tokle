/* Info tag tooltips (EXPERIENCE.md *Wallet not fully read*, WCAG 1.4.13; Story 4.5). Only enhances: the
   tooltip shows on hover and keyboard focus by CSS alone, and its sentence is in the page for screen
   readers through aria-describedby.

   This adds the one part CSS cannot do: Esc hides a showing tooltip without moving the pointer or the
   focus. The tag stays quiet until the pointer or the focus comes back to it, so the next hover or
   Tab shows it again. */
(function () {
  "use strict";

  var DISMISSED = "is-dismissed";

  function wrapperOf(node) {
    return node && node.closest ? node.closest(".tag-tip") : null;
  }

  function showing() {
    return Array.prototype.slice.call(document.querySelectorAll(".tag-tip")).filter(function (tip) {
      return tip.matches(":hover") || tip.contains(document.activeElement);
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    showing().forEach(function (tip) { tip.classList.add(DISMISSED); });
  });

  // A tag shows again when focus or the pointer comes back to it: no timer, so nothing races the focus move.
  document.addEventListener("focusin", function (event) {
    var tip = wrapperOf(event.target);
    if (tip) {
      tip.classList.remove(DISMISSED);
    }
  });

  document.addEventListener("pointerover", function (event) {
    var tip = wrapperOf(event.target);
    if (tip && !tip.contains(event.relatedTarget)) {
      tip.classList.remove(DISMISSED);
    }
  });
})();
