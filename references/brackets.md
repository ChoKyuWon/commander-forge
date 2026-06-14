# Commander Brackets Protocol

Use this file whenever the skill builds, evaluates, or validates a deck against a `target_bracket`.

## Core rule

Commander Bracket is a construction checklist, not a power-number band. Do not infer bracket from the Oracle's POWER score. A deck can be high-power and still pass a lower bracket if it obeys that bracket's construction rules.

## Live data requirement

The Game Changers list is live rules data. Verify the current official list during the research phase and again in the final validation pass. Treat any card examples in local skill files as illustrative, not authoritative.

## The five brackets (official WotC Commander Brackets)

Names: **1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH.** A deck's bracket is the **lowest** bracket whose checklist it fully satisfies. To "pass `target_bracket`," the deck must obey that bracket's checklist; a deck that violates a lower bracket's rule belongs in a higher one regardless of its POWER number.

### Bracket 1 — Exhibition checklist
A deck passes Bracket 1 if **all** of these are true:
- **0 Game Changers.**
- **No** two-card infinite/game-ending/lockout combos at all.
- **No** mass land denial.
- **No** chaining of extra turns (a lone extra-turn card is fine; chaining is not).
- **Minimal tutoring** — tutors used sparingly, not to assemble a win.
- The deck is built around an unusual theme / for the experience, not to win efficiently. Games are expected to be slow.

### Bracket 2 — Core checklist
Roughly average modern-precon power. A deck passes Bracket 2 if **all** of these are true:
- **0 Game Changers.**
- **No** two-card infinite/game-ending/lockout combos at all.
- **No** mass land denial.
- **No** chaining of extra turns.
- **Tutoring used sparingly.**
The difference from Bracket 1 is optimization/intent, not the restriction list (Core decks play to win with solid staples; Exhibition decks lean into a gimmick). If a deck wants *any* Game Changers or an intentional 2-card combo, it is **not** Bracket 2 — it is at least Bracket 3 (or 4 for the combo).

### Bracket 3 — Upgraded checklist
A deck passes Bracket 3 if **all** of these are true:
- It contains **0–3 current official Game Changers.**
- It contains **no mass land denial** package.
- It does **not chain extra turns** (a single extra-turn card is acceptable; you should not expect to chain them).
- It contains **no compact 2-card game-ending, lockout, or infinite combo that can reliably assemble before about turn 6.**

Efficient tutors, strong synergy, and non-Game-Changer fast mana do not automatically raise the bracket unless they are current Game Changers or enable a prohibited play pattern under the checklist.

### Bracket 4 — Optimized
**No construction restrictions** beyond the format's banned list: any number of Game Changers, intentional 2-card combos, mass land denial, extra-turn chains, and aggressive tutoring are all allowed. A deck lands in Bracket 4 the moment it violates any Bracket 3 rule (e.g. a 4th Game Changer, an early 2-card infinite, an MLD package) without being a tournament-tuned cEDH list. High power, but not necessarily built for a competitive metagame.

### Bracket 5 — cEDH
**No restrictions.** Fully optimized to win in a competitive tournament metagame: the fastest legal combos, the full suite of Game Changers, and metagame-driven card choices. The distinction from Bracket 4 is intent and refinement (built to win a cEDH event), not an additional rule.

## Reporting format

Whenever reporting bracket, include:

```text
Bracket: N
Checklist:
  Game Changers: X/Y allowed
  Mass land denial: yes/no
  Extra-turn chains: yes/no
  Early compact game-ending combo/lockout: yes/no
  Notes:
```

If the deck fails the target bracket, state the specific checklist item that failed. Do not say the bracket failed because the POWER score is too high.
