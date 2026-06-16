# Commander Forge

A Claude Code skill that builds and iteratively optimizes a Magic: The Gathering **Commander (EDH)** deck from a short brief — a commander, a target bracket, a target power, and any theme or forbidden-list constraints — and emits an Archidekt-importable decklist.

It runs a deterministic, evidence-driven **Builder → Oracle → Critic** loop, grounded in aggressive multi-source web research, and converges on a legal 100-card deck that meets the power and bracket targets (or honestly reports the gap).

## What it does

- **Parses a brief** into parameters: `commander`, `target_bracket` (1–5), `target_power` (1–10), `themes`, `forbidden_cards`, `forbidden_combos`, `forbidden_strategies`, `budget`.
- **Researches** the commander across EDHREC, Moxfield, Archidekt, Reddit, and articles — never trusting a single source.
- **Builds** a legal 100-card deck inside the commander's color identity, expressing the requested themes.
- **Scores** power with two oracles (see [Power scoring](#power-scoring)). Governing power is the *lower* of the two.
- **Critiques** adversarially — surfacing weaknesses, detecting oscillation and bracket drift, and issuing the termination verdict.
- **Loops** until both oracles clear `target_power` and the deck passes the `target_bracket` restriction checklist (3–6 iterations typical; 20 hard cap).
- **Emits** `deck.txt` (Archidekt-importable plain text) plus `optimization-log.md` (analysis and full change history).
- **Optionally uploads** the finished deck to the user's Archidekt account.

## Core principle — the Iron Rule

**Never name a card from memory, and never assert what a card does from assumption.** Every card added, scored, or endorsed must be grounded in a real Scryfall lookup — exact name, color identity, type line, mana value, current Oracle text, and legality. Memory is for *patterns*; the API is for *facts*. This single rule kills the most common failure mode of an LLM deckbuilder.

## How to use it

This is a Claude Code skill — invoke it by asking Claude to build a Commander deck. For example:

> Build me a Ketramose, the New Dawn deck. Bracket 3, power ~8, themed around blink and lifegain. No infinite combos.

Claude (as the orchestrator) parses the brief, runs the loop, and writes the outputs to the current working directory.

## Outputs

| File | Contents |
|------|----------|
| `deck.txt` | The final 100-card deck as **pure Archidekt-importable plain text** — one card per line, no prose. Format: `<qty>x <Card Name> (<setcode>) [<Category>]` (set code and category optional). |
| `optimization-log.md` | All human-facing analysis: summary, commander + color identity, estimated power/bracket/confidence, themes, win conditions, the full iteration-by-iteration change ledger, strengths, weaknesses, and risks. |
| `<deck>.archidekt.json` | Manifest written by the uploader, mapping the deck to its Archidekt id/URL so the scoring deck is reused in place (no clutter). |

## Repository layout

```
SKILL.md                      The orchestration contract Claude follows (start here).
README.md                     This file.
references/
  deckbuilding-logic.md       Iron Rule + Signal / Spine-Engine-Filler / Curve-gate / combo logic.
  brackets.md                 How this skill interprets the Commander Brackets (1–5).
  research.md                 The multi-source research contract and gate questions.
  builder.md                  Builder-role guidance (ratios, high-power-in-bracket).
  oracle.md                   Deterministic local-oracle scoring rubric.
  remote-oracle.md            CommanderSalt scoring method and two-oracle calibration.
  critic.md                   Adversarial Critic checklist and verdicts.
  upload.md                   Archidekt uploader contract, API provenance, exit codes.
scripts/
  upload_to_archidekt.py      Create/update an Archidekt deck from deck.txt (stdlib only).
  query_commandersalt.py      Query CommanderSalt for a deck's power level (stdlib only).
templates/
  deck.txt                    Reference format for the importable decklist.
  optimization-log.md         Reference structure for the analysis log.
```

## Power scoring

Power is scored by **two oracles**, and the deck's power is the **lower** of the two: `power = min(local, remote)`. The deck meets `target_power` only when both clear it.

- **Local oracle** — a fixed rubric the skill applies every iteration. Fast, no network, but biased (it tends to over-rate). Treated as an estimate.
- **Remote oracle** — [CommanderSalt](https://commandersalt.com), a data-backed number derived from each card's salt score, combos, bracket, and synergy. Authoritative. Read at checkpoints and always before declaring convergence. It rewards the *density* of high-impact staples, not synergy alone — so a low-salt value pile caps around 6 regardless of how well it plays.

The scoring runs fully automatically: the skill hosts the deck on Archidekt and queries CommanderSalt itself. You are never asked to paste a number — that only happens if CommanderSalt's API breaks.

## Environment variables

CommanderSalt scoring requires the deck to be hosted on Archidekt, so the skill needs your Archidekt credentials:

| Variable | Purpose |
|----------|---------|
| `ARCHIDEKT_EMAIL` | Archidekt account email. |
| `ARCHIDEKT_PASSWORD` | Archidekt account password. |

Set them in your shell profile or in Claude Code's `settings.json` `env` block. The deck is created **unlisted** (private-enough, still scorable).

If they are unset, the skill skips both the remote oracle and the auto-upload: it falls back to asking for a pasted CommanderSalt number and tells you to import `deck.txt` manually. `deck.txt` is always written either way.

## Notes

- **Bracket is a restriction checklist, not a power cap.** A Bracket-3 deck can legitimately reach power ~8 — high power is achieved by a compact, bracket-legal win condition, not by escalating the bracket.
- **Identity and legality are hard constraints.** A card outside the commander's color identity or on a forbidden list is rejected regardless of power.
- The skill is **generic** — it works for any commander, with nothing hard-coded to a specific one.
- Uploading is **additive**: `deck.txt` is always the source of truth, and a failed upload never masks a successful build.
