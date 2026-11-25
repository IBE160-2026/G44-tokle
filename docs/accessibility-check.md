# Accessibility check (Story 3.5)

This is the record of the accessibility check that closes stage 1 (epics.md, Story 3.5). The target is WCAG 2.1 AA (EXPERIENCE.md › Accessibility Floor). Edvard first planned to walk the checklist himself with NVDA and the keyboard. On 24 November 2026 he chose browser tests instead. They walk the same 12-item checklist with the keyboard only and read what the browser hands a screen reader: each element's role, name, description and state, the reading order (Playwright's accessibility snapshot), and the text of the live regions.

- **Where:** `tests/browser/test_checklist.py`, one test per item, plus the Real Wallets links and every page with JavaScript off. The page checks in Python are in `tests/test_web.py`.
- **Browser:** the Chrome or Edge already installed (Playwright for Python). On CI a browser that cannot start fails the run; it is never skipped.
- **Run them:** `uv run pytest tests/browser/test_checklist.py` (needs Chrome or Edge), or everything with `uv run pytest`.
- **Pages:** the Synthetic Wallets in Offline Mode. The live pages (fetching, no history, Polymarket down, the error page) come from a live app with its real job queue in front of a stand-in Polymarket on 127.0.0.1.

Each test was also broken on purpose once, with one planted change to the page or a script, and it failed each time. The planted breaks are listed with each item. Run on 25 November 2026, Windows 11, Chrome.

## The automated page checks (AC1)

| Check | Test | Found |
| --- | --- | --- |
| One h1 per page, the first heading, and no skipped heading level (h1 → h2 → h3) | `tests/test_web.py` › `test_ux_dr11_every_page_has_one_h1_first_and_no_skipped_level`, on 14 pages: Lookup, Lookup with an error, Verdict, Not enough data, Fetching, Not available offline, Sample Dataset not loaded, No history, Polymarket did not answer (with and without stored data), the 500 page (from the app's handler and from a failed job), 404 and 405 | Pass on every page. The Lookup page goes h1 → h2 *Sample Wallets* → h3 *Real Wallets* / *Synthetic Wallets*; the Verdict page goes h1 → h2 *Simulated results* → h2 *What this test can't see*. Planted break: *Synthetic Wallets* as an h4 fails the three pages that show the list. |
| Every field has a label; every error is tied to its field | `tests/test_web.py` › `test_ux_dr13_every_field_is_labelled_and_every_error_tied_to_its_field`, same 14 pages | Pass. The only field is the address field (label *Wallet address*); its error is in its `aria-describedby` and the field is marked `aria-invalid`. Planted break: without `aria-invalid` it fails. |
| `lang="en"`, the skip link is the first focusable element, the Verdict read as "Verdict: …", no inline scripts | `tests/test_web.py` › `test_every_page_has_the_frame`, `test_fr8_sharp_trader_verdict_card`, `test_ux_dr20_all_dotted_variants` (from Stories 1.7 and 3.4) | Pass (cited, not tested again). |
| Forced-colours rules | `tests/test_web.py` › `test_ux_dr27_ux_dr28_explore_styles`; `tests/browser/test_pages.py` › the three `forced_colours` tests (Story 3.5 part A) | Pass (cited). |
| No page needs JavaScript | `tests/browser/test_checklist.py` › the four `..._without_javascript` tests (below) | Pass. |

## The checklist

| # | Item | Test | What it found |
| --- | --- | --- | --- |
| 1 | The first Tab stop is "Skip to content"; Enter jumps to the main content | `test_checklist_1_skip_link_is_the_first_tab_stop` | **Verdict page: pass.** The first Tab lands on the link *Skip to content*, with its focus ring; Enter moves the focus to `main`. **Lookup page: as checklist item 1 now says (finding 1, Edvard's call).** The focus starts in the address field (autofocus), so the first Tab goes on to *Check wallet*. The skip link is still the first stop in the page's tab order: Shift+Tab from the field reaches it, and Enter on it moves the focus to `main`. Planted break: the link pointing at a missing id fails. |
| 2 | Lookup: the field is read as "Wallet address"; an empty submit is read as "Error: Enter a wallet address." and the focus stays in the field | `test_checklist_2_empty_submit_is_read_as_an_error_on_the_field` | Pass. The field is *textbox "Wallet address"*, described by the hint. Enter on the empty field submits the form; on the page that comes back the focus is in the field, the field is *[invalid]*, and its description is "Error: Enter a wallet address. A Wallet address starts with 0x and has 42 characters." The ✕ icon is not read. Planted break: the error left out of `aria-describedby` fails. |
| 3 | Verdict page: jumping by heading reaches the main heading, read as "Verdict: …"; the dots are silent | `test_checklist_3_verdict_heading_is_read_as_verdict` | Pass. There is one level-1 heading, named "Verdict: Skilled (high confidence)", with nothing else in it: the dots give a screen reader nothing. Planted break: the hidden "Verdict: " removed fails. |
| 4 | The odds phrase, the stats and the chart's text alternative are read as plain text | `test_checklist_4_odds_stats_and_chart_text_are_plain_text_in_order` | Pass. After the heading come the odds phrase as a paragraph, then *Stats* and the stats line as one paragraph, then the chart title and the text alternative as a paragraph, in that order. The drawing is not read: no axis title and no end-bar labels, and the marker's "This Wallet: $…" only in the marker button's name. The stats line reads "100 resolved bets , Real PnL $2,000": the hidden comma stands in for the visible dot (which is hidden), and the stray space before it is only how the accessibility tree joins the text pieces. It is harmless, and the markup was not changed. Planted break: the text alternative hidden fails. |
| 5 | The chart slider "Replays by result": the keys move it and each step is read | `test_checklist_5_slider_is_read_with_its_value` | Pass. Tab reaches *slider "Replays by result"*, with its focus ring and its hint as the description. ArrowLeft changes the value read (`aria-valuetext`, the bar's range and count); End goes to the last bar. Every key is proven in `test_chart_script.py` › `test_ux_dr26_slider_keys` (part A). Planted break: chart.js not updating `aria-valuetext` fails. |
| 6 | The Wallet marker: its sentence is read; Enter says "Highlight on", Esc says "Highlight off" | `test_checklist_6_marker_is_read_and_announces_highlight_on_and_off` | Pass. Tab reaches the button "This Wallet: $X. Highlight the replays that did this well or better", described by the tail sentence. Enter puts "Highlight on: …" in the polite live region and the button reads as pressed; Esc puts "Highlight off". Planted break: the live region set to `aria-live="off"` fails. |
| 7 | Copy button: "Address copied" is announced | `test_checklist_7_copy_is_announced` | Pass. Tab reaches *Copy wallet address*; Enter copies the address, the status region says "Address copied" and the focus stays on the button. Timing and failures: `test_pages.py` › `test_ux_dr21_copy_works`, `test_ux_dr21_copy_refused`. Planted break: other status words fail. |
| 8 | The Exit PnL warning is read with "Warning:" first (stop-loss Synthetic Wallet) | `test_checklist_8_exit_warning_is_read_with_warning_first` | Pass. The note in the Verdict card is read "Warning:", then "Positions this Wallet sold before resolution lost money in total.", then the second sentence. The icon is not read. Planted break: the hidden "Warning: " removed fails. |
| 9 | "What this test can't see" is reachable by heading and read in order | `test_checklist_9_honesty_notes_are_reachable_by_heading_and_read_in_order` | Pass. It is a level-2 heading that names its region, and the region is read in the order it is shown: largest bet, held to resolution, Exit PnL, the limits, "This is not financial advice.", left out, fees, the over-10% warning, computed-on. Planted break: the left-out block hidden fails. |
| 10 | The theme toggle is read as "Dark theme, toggle button" with its pressed state | `test_checklist_10_theme_toggle_is_a_pressed_button` (Lookup and Verdict) | Pass. It is *button "Dark theme" [pressed]*. Enter turns it to not pressed (light theme) and Space back to pressed, with the focus staying on it. Planted break: `aria-pressed` stuck at true fails. |
| 11 | Keyboard only: every action works, the focus ring is always visible, nothing traps the focus | `test_checklist_11_tab_walks_every_control_with_a_ring_and_no_trap` (Lookup, sharp trader, stop-loss trader) | Pass. Lookup: 12 controls. Verdict pages: 8 (skip link, logo, *Check a wallet*, theme, copy, *About this chart*, slider, marker). Every press of Tab must go to the next control in page order, with a visible 2 px ring. The only stop off the controls allowed is one run at the wrap point: Tab leaves the page exactly once, right after the last control, then comes back to the first. Shift+Tab starts from the control the Tab walk ended on and walks the same stops backwards. At the wrap point Chrome goes from the first control straight to the last, without leaving the page. Any other stop fails the test and names the element that has the focus. Each control's own action is checked by items 1, 2, 5, 6, 7 and 10. Planted breaks: no focus ring fails all three pages; `tabindex="1"` on the theme toggle (a broken tab order) fails all three. |
| 12 | At 200% zoom and in a 320 px window there is no sideways scrolling | `test_checklist_12_no_sideways_scroll_at_200_percent_zoom` (Lookup, two Verdicts), `test_checklist_12_fetching_page_has_no_sideways_scroll` (640 px at scale 2, and 320 px) | Pass. 200% zoom of a 1280 px window is 640 CSS px at device scale 2. 320 px for the Lookup and Verdict pages: `test_pages.py` › `test_ux_dr10_no_sideways_scroll` (Story 3.4). Planted break: a 700 px minimum width fails all five. |

### Real Wallets links

`test_real_wallets_links_have_unique_names_in_their_list`, over the 10 committed real Wallets (read in place). Pass. The test checks:

- the list named *Real Wallets* has one link for each of the 10 committed `0x*.json` files;
- each link's name is exactly its visible text, the short address, such as "0x7298…fcfc" (the chevron is decorative and hidden);
- the 10 names are all different.

A screen-reader user hears the same name a sighted user sees (WCAG 2.5.3). Naming the links by address only was the AI's call in the spec, and Edvard approved it with the spec (2026-11-25). Planted break: names cut to "0x0915…" style prefixes fail.

### Every page with JavaScript off

| Test | Found |
| --- | --- |
| `test_ad18_every_offline_page_is_complete_without_javascript`: Lookup, Lookup with an error, three Verdicts (Skilled, the stop-loss trader, Not enough data), Not available offline, 404 | Pass. Each page has its one h1, its content, and nothing shown that needs a script: the only shown button is the form's submit button, and the theme toggle, copy button and chart controls stay hidden. |
| `test_ad18_not_loaded_page_is_complete_without_javascript` | Pass: the Lookup page's box and the Wallet page both say to run `uv run liquidoracle load-sample`. |
| `test_ad18_lookup_form_submits_by_keyboard_without_javascript` | Pass: typing an address and pressing Enter opens its Verdict page. |
| `test_ad18_live_pages_are_complete_without_javascript` | Pass. The fetching page is complete, and its "Reload this page" link, followed by keyboard, shows the Verdict, *No Polymarket history found*, *Polymarket did not answer* or *Something went wrong*. |

Planted breaks: a visible theme toggle fails 12 of these tests; a POST form fails the form test; a renamed reload link fails the four live pages. The chart without its script is covered in `test_chart_script.py` › `test_ad18_chart_complete_without_the_script` (part A).

## Findings

1. **The Lookup page's first Tab is not the skip link (item 1). It stays: Edvard's call, 2026-11-25.** The address field has `autofocus` (UX-DR16: "focus in the field"), so the page opens with the focus already inside `main`, which is what the skip link is for. The first Tab therefore goes to *Check wallet*. The skip link is still the first element in the tab order, and Shift+Tab reaches it. Removing the autofocus would change a planned behaviour, and item 2 relies on it (after an empty submit the focus is back in the field). Edvard chose to keep it (AI recommendation, over removing it), and checklist item 1 in epics.md now says that on the Lookup page the skip link is reached by Shift+Tab.
2. **"Below all" was not read (from Story 3.1, fixed here).** When the Real PnL is below every replay, the marker's "below all 10,000 Simulations" sat only in the drawing, which is hidden from screen readers, and the text alternative then said only "more than half the time". Edvard chose to add "That is below all 10,000 replays." to the text alternative (2026-11-25; EXPERIENCE.md, epics.md UX-DR24 and Story 3.1 changed first). Checked by `tests/test_phrases.py` › `test_ux_dr24_chart_text_says_below_all_only_when_asked`, `tests/test_chart.py` (below all, above all, inside the curve, a tie) and `tests/test_web.py` › `test_ux_dr24_planted_below_all_is_in_the_text_alternative`.

No other check failed. No source file needed a fix for these tests.

## What these tests cannot prove

- **The words NVDA itself speaks.** No screen reader runs in the tests. They read the accessibility tree Chrome builds, which is what NVDA, JAWS and Narrator read from. How a screen reader words it ("toggle button", "pressed", "clickable") and in what order it speaks the name, role and state is up to the screen reader.
- **Browse mode.** Jumping by heading (H), by landmark or by list is screen-reader browse mode, which no test can press. The tests check that the headings, landmarks and lists are there, with the right levels and names.
- **When a live region is spoken.** The tests check the text that lands in the status and live regions, not whether or when a screen reader interrupts to say it.
- **Text-only zoom.** Playwright zooms the whole page (device scale), not text alone, so the browser's text-only zoom setting is not checked.
- **Other browsers.** Only Chrome or Edge (Chromium) runs. Firefox and Safari build their own accessibility tree.
- **Text spacing (WCAG 1.4.12)** is not checked. No test applies the larger letter, word, line and paragraph spacing to see that nothing is cut off.
- **Non-text contrast (WCAG 1.4.11)** of the chart bars, the marker and the focus ring is by design (DESIGN.md records it) and is not measured.
- **Orientation (WCAG 1.3.4)** is not checked. The pages set no orientation lock, but no test turns a device.
- **Colour contrast** is not measured here. The colour tokens come from DESIGN.md, which records their contrast, and `tests/test_web.py` › `test_ux_dr1_colour_tokens_match_design_md` checks the stylesheet uses them.
