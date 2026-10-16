# Accessibility Review — LiquidOracle (WCAG 2.1 AA)

Reviewed on 2026-10-16: `DESIGN.md`, `EXPERIENCE.md`, `.memlog.md`, `mockups/verdict.html` and `mockups/logo-and-tab.html`, with PRD §8 for context.

How it was checked:
- Every colour pair was recomputed with a script, in both themes. That includes the `color-mix()` colours the mockup creates: tail bars, the active bar and the primary button on hover.
- The mockup was driven in installed Chrome with Playwright at 1280, 640 and 320 px. Each width was run with and without the WCAG 1.4.12 text-spacing override, and with reduced motion, forced colours and JavaScript off.
- The tab order and the accessibility tree were read from Chrome.

Tags: **[spec]** means DESIGN.md or EXPERIENCE.md. **[prototype]** means the mockup HTML.

## Overall verdict

**Good. No blockers.** The PRD §8 rules are met:
- The Verdict is always text, and its heading reads "Verdict: No evidence of skill".
- The chart's text alternative is visible and states the Real PnL and the odds phrase.

All listed text and UI colour pairs pass AA in both themes. The script check in DESIGN.md is correct. Everything interactive can be reached and used by keyboard, in reading order, with a visible focus ring. Reduced motion is respected fully. At 320 px and under text spacing the page does not scroll sideways.

The problems are in the finer parts of the interactive chart: screen-reader announcements and hover labels. There is also one silent failure (copying), plus some gaps in the spec for pages that are not mocked yet (forms, page changes, scrolling tables). Fix the 7 medium items before the build. The low items can be handled during the build.

Counts: critical 0, high 0, medium 7, low 12.

## Findings

### Medium

- **[medium] [prototype] The wallet marker's announcements are doubled, stale or missing.** (verdict.html, script "The wallet marker", 4.1.3 Status Messages)
  - On focus, the live region gets "2,500 of 10,000 replays did this well or better." at the same moment the screen reader reads the button's name and "toggle button, not pressed", so the two can talk over each other.
  - Pressing Enter writes the same sentence again, so it is likely read twice.
  - Esc sets `aria-pressed="false"` but leaves the old sentence in the live region, so nothing says the highlight was cleared. Confirmed in Chrome: after Esc the live text is unchanged.
  - Arrow keys on the slider also unpin the marker without telling anyone.
  - Because blur never clears the live region, focusing the marker again may be silent.
  - *Fix:* Point the button's `aria-describedby` at the sentence. The tail label can carry it if it is not `aria-hidden`. Then drop the live update on focus. Use the live region only for pin and unpin, with different text each time: "Highlight on: 2,500 of 10,000 …" and "Highlight off". Announce "Highlight off" on Esc and on an unpin caused by the slider too.

- **[medium] [prototype] Hover labels vanish when you move the pointer onto them.** (verdict.html `.tail-label`, `.chart-tip`, 1.4.13 Content on Hover or Focus, "hoverable")
  - The tail label sits 14 px right of the 28 px marker button and has `pointer-events: none`. Moving the pointer towards it fires `pointerleave` on the button, and the label disappears.
  - The bar label works the same way. Moving onto it changes it to another bar's label, or hides it once the pointer leaves the slider area at the top.
  - Esc does dismiss both labels, and they stay put while the pointer is still. So only "hoverable" fails.
  - Screen-magnifier users are hit hardest, because they have to move to read.
  - *Fix:* Treat the marker button and the tail label as one hover area: give the label pointer events and hide it only when the pointer leaves both. Alternatively, hide after a 300 ms delay that is cancelled when the pointer re-enters. For bar labels, keep the label while the pointer is over the label itself. Add the rule to EXPERIENCE.md › Chart explore so the build keeps it.

- **[medium] [prototype + spec] A failed copy is silent, and "Copied" is not part of the button's name.** (verdict.html copy script; EXPERIENCE.md › Copy address; 4.1.3, 3.3.1, 2.5.3 Label in Name)
  - If `navigator.clipboard` is missing or the copy is refused, nothing happens. This was confirmed with a refused write. The user then pastes whatever was on the clipboard before.
  - The spec only says the address stays selectable, but nobody is told to select it.
  - While "Copied" is visible, the name is still "Copy wallet address". A speech-input user who says "click Copied" gets nothing. That part is minor.
  - *Fix:* When copying fails, show and announce "Copy failed. Select the address and press Ctrl+C", and select the address text. Put the status in a live region *outside* the button: some screen readers ignore live regions inside a named button. Write the failure state into EXPERIENCE.md › Copy address.

- **[medium] [spec] Page changes, the Fetching state and how a new Verdict is announced are not specified.** (EXPERIENCE.md › State Patterns "Fetching", Accessibility Floor "Live updates", 2.4.3 Focus Order, 4.1.3)
  - The spec says "the arrival of a Verdict is announced", but not how. If the frontend turns out to be a single-page app, a screen-reader user will hear nothing when the Verdict page loads.
  - "Button disabled" while fetching takes focus off the button the user just pressed. In Chrome, focus falls back to the page.
  - The `logo-and-tab.html` demo has the same issue: its button is disabled while the demo Scan runs.
  - The *No Polymarket history* state has no main heading defined.
  - *Fix:* Add three rules to the Accessibility Floor.
    1. On every page change, including a client-side route change, update the tab title and move focus to the `h1`, or to a "Skip to content" target that holds it.
    2. While fetching, keep the button focusable with `aria-disabled="true"`, or move focus to the status line, and put "Fetching trades from Polymarket…" in a polite live region.
    3. Each error or empty state has its own `h1`, for example "No Polymarket history found".

- **[medium] [spec] The form and error rules are not concrete enough to build or test.** (EXPERIENCE.md › Accessibility Floor "Forms", Component Patterns "Address field", "New Scan form", "Scan list"; 3.3.1, 3.3.2, 1.3.1, 2.4.6)
  - "Linked to it" does not say how.
  - The visible label of the address field is never named.
  - The New Scan form has no error states: no date, a date in the future or outside the data, a Wallet count that is not a number or is out of range.
  - The "✕" in error messages may be read as "multiplication sign".
  - Several "Resume" buttons in the Scan list would all have the same name.
  - *Fix:* Write the mechanism down:
    - the visible label "Wallet address" on a `<label for>`
    - the error sentence with `aria-describedby` and `aria-invalid="true"`, starting with hidden text "Error:" and with the ✕ `aria-hidden`
    - allowed ranges and error texts for both New Scan fields
    - button names like "Resume Scan (Cut-off Date 1 Jun 2026)"

- **[medium] [spec + prototype] Tables that scroll sideways can't always be scrolled by keyboard.** (DESIGN.md › Layout "Wide tables scroll inside their card"; verdict.html `.table-card`; 2.1.1 Keyboard, 1.4.10 Reflow)
  - The mockup's scroll container has `tabindex -1`, no role and no name.
  - The Watchlist can get away with it, because its row links take focus and the browser scrolls to them.
  - The S3 domain table, the Hold-up group figures and any table without links can't be scrolled by keyboard. At 200% zoom (640 CSS px) the right-hand columns, such as Real PnL, are cut off.
  - *Fix:* Specify that every table container that can scroll gets `tabindex="0"`, `role="region"` and `aria-label` (the table's caption), plus the normal focus ring. Do the same in the mockup.

- **[medium] [prototype; advisory, beyond 2.1 AA] In Windows High Contrast (forced colours) the chart's bars disappear.** (verdict.html `.bar`, `.dot.is-filled`; 1.4.11 in spirit)
  - Bars and filled dots are drawn as backgrounds, and forced colours removes backgrounds.
  - Verified: the chart showed only gridlines and the marker, and the filled and empty dots looked the same.
  - The text alternative and the Verdict text still carry the meaning, so this is not a strict 2.1 AA failure. It does hit real Windows users, and the examiner runs Windows.
  - *Fix:* Add `@media (forced-colors: active) { .bar { forced-color-adjust: none; background: CanvasText; } .bar.is-tail, .bar.is-active { background: Highlight; } .dot.is-filled { forced-color-adjust: none; background: CanvasText; } }`, or draw bars with borders or SVG. Add one line to DESIGN.md.

### Low

- **[low] [prototype + spec] Warnings and errors are marked only by look.** (verdict.html `.warning`; DESIGN.md › Warning box, Error message; 1.3.1 Info and Relationships)
  - The ⚠ icon is `aria-hidden` and `role="note"` says nothing about caution, so a screen reader reads the sentence with no hint that it is a warning.
  - *Fix:* Start the text with hidden "Warning:" (and "Error:" for error messages). Write this into DESIGN.md's Warning box and Error message entries.

- **[low] [prototype] The stats line runs together for screen readers.** (verdict.html `.stats .line`; 1.3.1)
  - The `aria-hidden` "•" leaves no space, and Chrome's tree reads "212 resolved betsReal PnL $40,180".
  - *Fix:* Put spaces outside the hidden separator, or use a hidden ", ".

- **[low] [prototype + spec] The tail highlight is a change of hue only.** (verdict.html `.bar.is-tail`; DESIGN.md › chart-tail; 1.4.1, 1.4.11)
  - Tail bars vs normal bars measure 1.04:1 in light and 1.22:1 in dark. The marker line vs the tail bars is 2.16:1 in light and 1.90:1 in dark.
  - Without colour vision, nothing changes on hover. It passes WCAG only because the tail label states the number.
  - DESIGN.md's "checked with a script" list doesn't cover the state colours: tail, active bar, tooltip and row hover. All of these pass against the card. Results: tail 3.14 / 3.72, active bar 9.33 / 9.58, tooltip text 17.6 / 14.5.
  - *Fix:* Make tail bars clearly darker than normal bars (e.g. accent 85% instead of 65%) so there is also a change in lightness. Add the state colours to the contrast script and to DESIGN.md.

- **[low] [prototype] The bar label covers the marker dot.** (verdict.html `setActive`; 2.4.7, readability)
  - When the slider gets focus it starts on the marker's bar. The dark label then sits over the marker's dot and the top of its line (seen in Chrome at 1280 px).
  - *Fix:* Start the label at the marker bar's right edge for that bar, or move it to the side.

- **[low] [prototype] The theme toggle changes its own name.** (verdict.html `#theme-toggle`; 4.1.2)
  - Swapping the `aria-label` on click is allowed, but many screen readers don't read the new name, so the user hears no result.
  - *Fix:* Optional. Keep the current name and add a short polite live message ("Dark theme on"). Or use a fixed name, "Dark theme", with `aria-pressed`.

- **[low] [prototype] `aria-labelledby` on `<code>` is ignored.** (verdict.html `#wallet-address`; 4.1.2)
  - The `code` role can't be named, and Chrome drops the label. No harm is done, because the visible label comes right before it.
  - *Fix:* Remove the attribute.

- **[low] [prototype] The disclosure arrow is read aloud, and the help text assumes a mouse and colour vision.** (verdict.html `.about summary::after`, About text; 1.3.3 Sensory Characteristics)
  - The "▾" / "▴" made in CSS is read as "down-pointing small triangle".
  - "The blue line is …" and "Point at a bar or at the line" lean on colour and a mouse.
  - *Fix:* Use `content: " ▾" / ""`. Change the text to "The blue line labelled 'This wallet' …" and add "or use the arrow keys".

- **[low] [prototype] Text below the spec's minimum.** (verdict.html `.offline-pill` at ≤ 640 px is 12 px; DESIGN.md › Typography "No text below 13 px")
  - This is not a WCAG failure, but it breaks the project's own rule.
  - *Fix:* Keep 13 px and let the pill wrap, or shorten it.

- **[low] [prototype] The theme toggle shrinks under text spacing at 320 px.** (verdict.html `.theme-toggle`; 1.4.12 Text Spacing)
  - With the 1.4.12 text spacing on, the `nowrap` Offline pill grows and the toggle (flex-shrink 1) gets narrower than 40 px.
  - *Fix:* Give `.theme-toggle` `flex: none`, and let the pill wrap.

- **[low] [prototype] The chart is empty without JavaScript.** (verdict.html `.plot.pre-build` in the markup)
  - The bars and marker start at scale 0 or opacity 0 in the HTML. If the script fails, the chart stays empty. The text alternative is still there.
  - *Fix:* Add `pre-build` from the script, not in the HTML.

- **[low] [spec] The full address in the table link's name clashes with Label in Name.** (DESIGN.md › Data table "full address … in the link's accessible name"; 2.5.3)
  - The visible text is "0x1a2b…9f0e". A name that holds only the full 42-character address doesn't contain that text.
  - The full address is also tiring to listen to in every row.
  - *Fix:* The mockup's approach is better: "Open Verdict for wallet 0x1a2b…9f0e". Put the full address in `aria-describedby` or the `title` if needed, and update DESIGN.md to match.

- **[low] [spec] Semantics of the Scan pages that aren't mocked yet.** (EXPERIENCE.md › Scan sub-navigation, Scan progress; DESIGN.md › Tabs, Progress bar; 1.3.1, 4.1.2)
  - The Watchlist, Hold-up Test and Copy Test "tabs" are separate pages with their own URLs. A builder could wrongly use ARIA `tablist`.
  - The progress bar has no defined role or value.
  - *Fix:* State that the tabs are a `<nav aria-label="Scan">` with links and `aria-current="page"`. State that the bar is a `<progress>` or `role="progressbar"` with `aria-valuetext="84 of 200 Wallets checked"`, next to the polite 10% live region already in the spec.

## Checked and fine

- **Contrast, both themes:**
  - All text pairs pass 4.5:1. Muted text on surface, raised, neutral, tint and warning backgrounds is 5.4–8.1. Accent on every background, including Copied on tint, is 5.4–7.7. On-accent on the button, at rest and on hover, is 6.8–8.4. Warning text is 10.1 / 10.3. Error is 6.1–7.9. The Offline pill is 16.4 / 15.7. The tooltip is 17.6 / 14.5. Ink on the tail label is 15.3 / 11.1.
  - All UI and graphics pairs pass 3:1. Bars are 3.02 / 3.05. The marker is 6.8 / 7.1. Border-strong is 3.1–4.1. The warning stripe is 3.7–8.2. The focus ring is at least 6.0 against every background it sits on.
  - Pairs under 3:1 are decorative only: empty dots, card and toggle borders, and the dark-theme pill's fill (its outline is 3.75).
- **Colour is never the only signal:** the Verdict is always text, warnings have an icon and text, a negative PnL has a minus sign, and the active nav item has an underline, bold text and `aria-current`.
- **Keyboard order follows reading order:** skip link → brand → nav → theme toggle → copy button → About summary → chart slider → marker button → (prototype strip) button → row links. No traps. Esc works.
- **Visible focus everywhere,** never hidden by sticky content. The focus ring on the clickable table row draws correctly in Chrome. Focus rings stay clear of the marker label.
- **Slider:** `role="slider"` with min, max, now and a `valuetext` per bar ("$40,000 to $45,000: 260 replays"). Arrows, Page Up/Down and Home/End all work. The hint is linked by `aria-describedby`.
- **Marker button:** a real `<button>` with `aria-pressed` and a clear name. The visible label is in the name.
- **Structure:** one `h1` (the Verdict), then `h2` cards; banner, nav (labelled "Main") and main landmarks; `lang="en"`; tab titles follow the spec on both pages; the table has a caption, `th scope="col"` and a stated sort order.
- **Chart text alternative:** always visible. Bars and axes are `aria-hidden`, so the alternative is the only thing read.
- **Reflow:** no sideways page scroll at 320, 640 or 1280 px, with or without the text-spacing override. Hover labels stay inside the plot, and nothing is clipped.
- **Motion:** with *reduce motion* on, the chart is complete at once, with no lift and no transitions. The build-up runs once and lasts under a second, so 2.2.2 (pause, stop, hide) does not apply. 2.3.3 (AAA) is met in practice. The spec makes the fetching dots static under reduce motion.
- **Targets:** theme toggle 40 px, copy 36 px, marker 28 px wide (2.5.5 is AAA and 2.5.8 is 2.2, so neither applies).
- **Scan progress plan:** polite announcements at most every 10%. Screen readers are kept away from the title and favicon, and the logo-and-tab demo works that way.
- **logo-and-tab.html:** decorative images have `alt=""`, the table has a hidden caption and header cells, and the focus ring is visible.
