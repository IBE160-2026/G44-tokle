# AI session log, 2026-11-05: Polymarket tags instead of keyword rules

- **Tool**: Claude Code (model Claude Opus 5.5) in the VS Code extension.
- **Student**: Edvard Tokle (G44).
- **What this covers**: a check Edvard asked for before his hand labels, and the plan change he decided on after it. No app code was written.
- **Result**: Mock LLM Mode labels Domains from Polymarket's event tags instead of keyword rules. Changes to the brief (revision 9), PRD, spine, `EXPERIENCE.md`, `epics.md` and `sprint-status.yaml`, with memlog entries.

## 1. The prompts

> "check something for me before i do the hand labels, polymarket sends tags along with each event like politics tariffs trade war economy n stuff, do the markets we already saved for the sample set still have those tags on them or did we drop them when we saved. n if theyre there could we just use them for the domain instead of the keyword rules, whats the catch. dont change anything yet just tell me what you find"

> "yeah do that, tags instead of keyword rules for the offline mode n keep the model as the main labeller. dont write the tag map yet, ill do my definitions n the 50 blind labels first n then we build the map from my definitions."

> "yes to all three, additions are good, probes in spike, n new branch is fine. one thing, the script that fetches tags for the sample set must not touch my 50 markets until after ive committed my definitions n labels, leave those events out same as before n say in the commit that you did"

The idea came from Edvard. Keyword rules had been the plan since the brief, and neither the data spike nor the architecture step looked at tags.

## 2. What the check found

**Were the tags saved? No, and they were never dropped.** The saved raw Gamma responses have no tags, because no call asked for them: `/markets` only returns them with `include_tag=true`. The sample cache also keeps just five fields. The event IDs were saved, so the tags can still be fetched.

**The probe** (`spike/tag_probe.py`): 27 read-only Gamma requests. It drew a seeded 1,000 of the Sample Wallets' 15,616 events and left out the 48 events behind the 50 hand-label Markets, so Edvard's labels stay blind.

| Measure | Result |
|---|---|
| Events returned | 999 of 1,000 |
| Events with at least one tag | all 999 |
| Different tags | 686, including housekeeping ones like "Recurring" |
| 20-Market call with `include_tag=true` | tags on all 20 |
| Same call without it, on 5 Markets | tags on none |

The AI also wrote a rough test map from tags to Domains, only to size the problem. It gave 84% exactly one Domain, 13.5% none and 2.3% more than one. Counted by Markets, "none" rises to 23%. Among economy-type events, 13 of 35 also carry Politics.

When the probes moved to `spike/`, the AI reran the analysis on the saved draw and got the same numbers, and reran the two small steps to check they still work (7 more requests).

**What this does not show.** Getting one Domain is not the same as getting the right one: nothing here measures accuracy against hand labels, and no keyword rules were ever built to compare with. It covers the 10 Sample Wallets only, and the draw had nothing older than 2024.

## 3. The catches the AI reported

1. It is still a rule list, and anything the map misses lands in Other without warning. The AI's own test map missed one event this way.
2. Overlap is small overall but clusters in macro, and the tags do not settle it. Edvard's definitions have to.
3. Accuracy is unproven.
4. Tags sit on the event, so all its Markets get the same Domain, and Polymarket can edit them.
5. The plan names keyword rules in several documents, and the sample set needs its tags fetched.

It also warned that tags count as the "category field" his blind rule bans, so he should not look at them for his 50 Markets before labelling.

## 4. Edvard's decision

The AI recommended tags for Mock LLM Mode only, keeping the language model as the main labeller, because the brief promises it. Edvard said yes and added the order himself: **the tag map is not written yet**. He writes his Domain definitions and the 50 blind labels first, and the map is built from those definitions afterwards.

He said "offline mode". Offline Mode and Mock LLM Mode are separate in the plan, but both use `TemplateModel`, so the change covers both.

## 5. Added by the AI, confirmed by Edvard

These came up while writing the change into the plan. Edvard confirmed all of them, and the documents mark them as the AI's proposals:

- Each Market gets exactly one Domain, and a Market whose tags are all off the map gets Other.
- `TemplateModel` reads tags from the stored Market record and makes no request of its own.
- Gamma Market reads send `include_tag=true` from Epic 2, so stored records are not missing tags when Story 7.1 comes.
- The raw capture has no tags, so a one-off script fetches them once and saves them next to the capture zip, with their own SHA-256 file. The build-sample script then adds them.

The source name `tag-rules` and the info tag "Labels: Polymarket tags" are also the AI's wording.

**Edvard's rule on top:** the tag fetch must not touch his 50 Markets until his definitions and labels are committed, and those events are left out as in the probe. It is now in FR-19, AD-16 and Story 7.1.

## 6. AI mistakes caught in this session

- **Credit**: the AI first wrote its additions from section 5 into the PRD, spine and epics as "Edvard, 2026-11-05". It caught this itself on rereading and fixed it before anything was committed.
- **A gap in its own addition**: asking for tags on Market reads from Story 2.2 would have fetched tags for Edvard's 50 Markets if that read ran on the Sample Wallets first. The AI saw this while writing down his rule, so the rule now covers Story 2.2 too.
- **A number**: it wrote 28 requests in the PRD memlog, but the count is 27. The memlog is append-only, so the fix is a new entry.

## 7. Next

Edvard writes his Domain definitions and labels the 50 Markets blind. The tag map comes after that, in Story 7.1.

The AI's rough test map stays out of the repo until then, so it cannot steer his definitions. This was the AI's call and it departs slightly from "probes in spike": until the map is committed, `analyse` cannot be rerun from the repo alone.

## 8. Later the same day: Edvard's definitions and hand labels

> "ok i did the fifty by hand without looking at any tags. first my domain definitions [...] n here are my labels. 18 n 50 i wasnt sure about so i put other [...] put these into the hand label file n write my definitions down where they belong, commit it on the same branch as the tag work"

The definitions and the labels are Edvard's own; the AI only put them into the files. Before committing, it asked three questions, because the labels are never edited afterwards:

| Question | AI's recommendation | Edvard |
|---|---|---|
| His list said "unsure" for Market 50, but he wrote that he put "other" | other | other |
| Write "and" where he typed "n", since the model's prompt quotes the definitions word for word | yes, spelling only | yes |
| The plan asked each line to say where its overlap cases go; his lines cover two | commit as written, so the definitions still come before the labels | commit as written |

The plan named no file for the definitions, so the AI chose `sample_data/hand_labels/domain-definitions.md`. The commit message says no labeller ran on the 50 and no tags were fetched for their events before it.

Totals: politics 20, sports 13, other 12, crypto 4, macro 1. With only one macro Market, the 80% check says little about macro.
