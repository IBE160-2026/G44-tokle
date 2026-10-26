# LiquidOracle (G44, IBE160 Programmering med KI, HiMolde, autumn 2026)

A local web app that tells whether a Polymarket wallet's results show skill or luck. Solo project by Edvard Tokle. Plans live in `_bmad-output/planning-artifacts/` (brief, PRD); follow them, and update them when the plan changes.

## How this project is graded (keep this in mind on every task)

The exam is this repository as it stands on **2026-12-15**, when the repos lock. Aim to be done about two weeks earlier. Part 1, the app and repo, counts 70%; part 2, the reflection report, counts 30% (template on Canvas: `reflection-report-template.md`).

Part 1 criteria, from the teacher's grading guide:
- **Process and AI steering (30%)**: a traceable path from plan to code.
  - BMAD documents that are used and updated, not generated once.
  - Code traceable to requirements and stories, with deviations from the plan explained.
  - Small, frequent commits with descriptive messages. One big upload near the deadline scores close to zero.
  - Branches, pull requests or issues to organise the work.
  - Saved prompts and AI sessions, including examples of the student refining, rejecting or correcting AI suggestions.
  - Documented decisions with reasons.
- **Functionality and scope (20%)**: the core flows from the brief work end to end, the app is stable on bad input, and anything left out or changed is explained.
- **Quality assurance and testing (15%)**: automated tests of meaningful logic, runnable from the README, plus traces of code review and of bugs found in AI-written code and how they were fixed.
- **Design and UX (10%)**: a consistent visual style, clear navigation, usability and accessibility. The BMAD UX step is mandatory.
- **Code quality and architecture (10%)**: readable, structured code, no spaghetti.
- **README and runnability (10%)**: someone who doesn't know the project can install and run it from the README alone, with prerequisites, exact commands, and how keys and secrets are set.
- **Repository tidiness (5%)**: simple structure, no stray files, no secrets.

## Working rules

- **Log every session**: save the prompts and the AI's key proposals and decisions in `docs/ai-logs/<date>-<topic>.md` (or the full exported transcript). Record where the student changed or rejected a suggestion.
- **Commit small and often**, one logical change per commit, with a message saying what and why. Push at the end of each session.
- **Decisions about the plan** go in the BMAD memlog of the document they change, through `_bmad/scripts/memlog.py`.
- **Everything in the code must trace back to the brief or PRD.** Code with no basis in the plan is a serious fault. If the plan has to change, change the plan first.
- **Secrets** live in `.env`, which is never committed; keep `.env.example` up to date.
- **The app is read-only toward Polymarket.** It analyses public data and never places orders, holds keys or touches a wallet's funds.
- **A database is required** (teacher, 17 Sept 2026): every difficulty level in the course has one, and an app without one counts as too simple. A free tier or a local SQLite file is enough. Hosting and publishing are not required and don't affect the grade. The PRD draft (2026-10-12) doesn't name a database yet: add it when the PRD is reviewed.
- **Stack**: Python for the analysis and backend. The frontend is chosen in the architecture step; the course recommends JavaScript.

## Sesjonslogg

Når en oppgave eller økt avsluttes, før sluttoppsummeringen, bruk `sesjonslogg`-skillen: dokumenter Oppgave + Plan + Resultat + åpne punkter i `.logs/<bruker>/`, og før åpne punkter i `.logs/<bruker>/issues.md`. Skillen committer loggfila lokalt; push gjør du selv. Gruppens egne regler for commit og språk gjelder foran dette.
