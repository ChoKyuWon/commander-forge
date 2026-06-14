---
name: commander-forge
description: Build and iteratively optimize an MTG Commander (EDH) deck from a commander, target bracket, target power, and theme constraints. Use whenever the user wants to build, generate, brew, or optimize a Commander/EDH decklist — especially when they supply a commander name plus a bracket, a target power, themes, or forbidden cards/combos/strategies. Drives a Builder→Oracle→Critic optimization loop backed by aggressive multi-source web research and emits the final deck as Archidekt-importable plain text (deck.txt), with optimization history kept in a separate log. Can optionally auto-upload the finished deck to the user's Archidekt account.
---

# Commander Forge

A deterministic, evidence-driven pipeline that turns a short brief into an optimized 100-card Commander deck. It simulates three internal roles — **Builder**, **Oracle**, **Critic** — looping until the power and bracket targets are met (or 20 iterations elapse), grounded in aggressive multi-source web research.

You are the orchestrator. You run the phases below in order, switching "hats" between roles. Keep each role honest: the Oracle never builds, the Builder never scores itself, the Critic trusts neither.

---

## The Iron Rule (contract #1 — never relaxed)

**NEVER name a card from memory, and NEVER assert what a card does from assumption.** You propose *patterns, searches, and judgments*; a real Scryfall lookup names the card and supplies its oracle text. Every card you add, score, or endorse MUST be grounded in a real Scryfall result — exact name, color identity, type line, mana value, current Oracle text, legality. **Before asserting a synergy, read the card's actual oracle text and quote the clause that justifies it** — training data is not oracle text (e.g. *Tinybones, the Pickpocket* steals from **opponents'** graveyards, so it does not want self-mill). A card named from memory — wrong color, wrong text, or nonexistent — is the single most common failure mode of an LLM deckbuilder; this rule kills it. Memory is for patterns, the API is for facts.

Read `references/deckbuilding-logic.md` before building or evaluating — it holds the Iron Rule plus the Signal / Spine-Engine-Filler / Shape / Focus / Efficiency / Curve-gate / Combo-layer logic that the Builder, Oracle, and Critic all defer to.

---

## 0. Parse the brief into parameters

Extract these parameters from the user's input. If a field is absent, use the default and state the assumption explicitly.

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `commander` | Commander (and partner/background if given) | **required** — ask if missing |
| `target_bracket` | Max allowed bracket 1–5 (see Bracket guidelines) | 3 |
| `target_power` | Min power on the **real-world CommanderSalt-calibrated 1–10 scale** (≈6 = optimized casual; ≈8+ = fast high-power, usually Bracket 4) — the Oracle is anchored to this scale, not a private one | 7.0 |
| `themes` | Desired strategies/synergies (ordered by priority) | infer from commander |
| `forbidden_cards` | Cards that must never appear | none |
| `forbidden_combos` | Combos/loops that must never be assembled | none (but respect bracket) |
| `forbidden_strategies` | Strategies to avoid (e.g. stax, mass land denial, infinite combos) | none beyond bracket norms |
| `budget` | Optional price ceiling | none |

Derive `color_identity` strictly from the commander and verify it with Scryfall if there is any uncertainty. **Every nonland card and land must be inside the color identity** — a hard, non-negotiable constraint. Echo the parsed parameters back to the user in a short table before starting, but do not block on confirmation unless the commander itself is missing or ambiguous.

**Color identity is defined by CR 903.4 — apply it exactly:** a card's color identity is the set of colors of every mana symbol that appears (a) in its mana cost AND (b) anywhere in its rules text — including symbols in activated/triggered ability costs, hybrid mana symbols (e.g. `{B/G}` counts as both black and green), and Phyrexian mana symbols (e.g. `{B/P}` counts as black) — PLUS any color indicator and any "this card is [color]" characteristic-defining text. **Mana symbols in reminder text do NOT count.** A card is legal only if its full color identity is a subset of the commander's. The classic trap: an off-color mana symbol buried in an activated or triggered ability (e.g. a `{B}` activation makes a card black-identity even with a colorless mana cost) — these must be caught. When in doubt, read the card's color identity from Scryfall (the `color_identity` field) rather than eyeballing the mana cost.

The optimization objective is to **maximize Power, Consistency, Synergy, and Fun** subject to: commander identity, `target_bracket` (as a ceiling), `target_power` (as a floor), `themes`, and all three forbidden lists.

### 0a. Bracket = restriction checklist, NOT a power cap (read before building)

`target_power` and `target_bracket` are **largely independent axes** — do not treat them as contradictory. Bracket is set by a construction-RULES checklist (mainly the Game Changers count + a few banned categories), not by a power-number band. A deck can be **POWER ~8 AND Bracket 3** if it obeys the Bracket 3 rules:

Read `references/brackets.md` before building or evaluating. It is the authoritative local guide for how this skill interprets Commander Brackets. Always verify the current official Game Changers list during research; examples in this skill are illustrative only and may become stale.

**Bracket 3 hard rules (the only constraints — everything else is allowed):**
- **0–3 Game Changers** (verify against the live official list during research — it changes over time).
- **NO Mass Land Denial.**
- **NO chaining extra turns.**
- **NO 2-card game-ending / lockout / infinite combo that can assemble before ~turn 6.**
- Efficient tutors, non-Game-Changer fast mana, and strong synergy are all **fine**.

So a brief like **"Power ~8, Bracket 3" is feasible, not contradictory.** To maximize power within Bracket 3:
1. Spend the **full 3-Game-Changer budget** on the highest-impact picks (e.g. best tutors / card-advantage engines).
2. Add **non-Game-Changer fast mana** where it improves the deck — it raises power without touching the bracket unless it enables a prohibited play pattern.
3. Add efficient tutors for consistency.
4. **Avoid only the four banned categories.** In particular, do not include a compact 2-card infinite (e.g. Restoration Angel + Felidar Guardian) that could go off before turn 6.

Only flag a genuine conflict if the brief's `target_power` truly **requires** a banned element (e.g. "Power 10 / cEDH speed" needs early 2-card combos → that forces Bracket 4+). In that case state it and let the user choose: stay in-bracket at the achievable power, or raise the bracket. **Identity and the bracket checklist are the hard constraints; the power number is the objective to maximize within them.** Report the bracket from the checklist (state Game Changers = N/3, MLD?, extra turns?, early combos?), never from the power number.

---

## 1. Research phase (do this BEFORE building)

Read `references/research.md` and follow it. Summary of the contract:

- Search **aggressively and from multiple independent sources**: EDHREC, Moxfield, Archidekt, Reddit (r/EDH, r/CompetitiveEDH, commander-specific threads), plus articles/guides.
- **Never rely on a single source.** EDHREC alone is insufficient.
- After each research pass, ask yourself the gate questions:
  - Do I have enough evidence?
  - Am I relying only on EDHREC?
  - Do Reddit discussions disagree with the aggregator data?
  - Do optimized Moxfield/Archidekt lists differ from the EDHREC average?
  - Am I missing recent tech / new set releases?
- If any answer indicates a gap → **search again**. Do not stop early.
- Stop only when **≥3 independent sources agree** on the core shell, **or** disagreements are explicitly documented with both sides.

Produce a **Research Dossier** (kept in working memory and later summarized in `optimization-log.md`) containing: the commander's known archetypes, staple cards by role (ramp/draw/interaction/tutors/wincons), theme-specific tech, recent additions, and any documented disagreements between sources.

You may run web searches in parallel and may spawn an `Explore`/`general-purpose` subagent to fan out research, but you must consolidate findings yourself.

---

## 2. Builder — construct the initial deck (iteration 0)

Put on the **Builder** hat. Read `references/builder.md`. Construct a legal 100-card deck (commander + 99) that:

- respects color identity, the forbidden lists, and `target_bracket`;
- expresses the requested `themes` as the synergy core;
- hits sane deckbuilding ratios as a starting point (tune per commander). These must sum to **99** non-commander cards. A workable default split: **35–37 lands, 8–10 ramp, 8–10 draw, 8–10 interaction, and 30–35 theme payoffs / synergy enablers / explicit win conditions** (the payoff core is normally the *largest* bucket, not an afterthought). Treat the other buckets as a band you trim toward the low end to protect the payoff core — do not let lands+ramp+draw+interaction crowd it below ~28. Verify the buckets actually add to 99 before moving on;
- names every card explicitly (no "10x filler") and assigns each a role tag.

Output the full 100-card list with role tags. This is **iteration 0**.

---

## 3. Oracle — evaluate (deterministic)

Power is scored by **two oracles**, and the deck's level is the **lower** of the two (see `references/remote-oracle.md`):
- **local-oracle** — the `references/oracle.md` rubric below. Runs every iteration; fast but biased (tends to over-rate). An estimate.
- **remote-oracle** — **CommanderSalt** (`commandersalt.com`), a data-backed number. Authoritative; read at checkpoints (§5).

`current_power = min(local_oracle, remote_oracle)` — never report power above the lower one. Convergence requires **both** ≥ `target_power`. Between checkpoints, when no fresh remote reading exists, treat `current_power` as the local estimate **clearly labeled provisional** (optionally adjusted by the carried calibration offset, §5); it is reconciled to the true `min` at the next checkpoint, which is mandatory before declaring convergence.

Switch to the **local-Oracle** hat. Read `references/oracle.md` and apply it verbatim. The local-oracle:

- is an evaluator ONLY, never a builder;
- is **deterministic** — the same list yields the same scores; **large unexplained score jumps between iterations are forbidden** (if the score moves >1.0, you must justify it card-by-card);
- is **skeptical** — when uncertain, lower confidence rather than inflate the score.

Oracle output (required every iteration):

```
Power: X.X / 10
Bracket: N
Confidence: C   (0–1)
Component scores (0–10 each):
  Ramp:
  Draw:
  Interaction:
  Tutors:
  Win Conditions:
  Commander Synergy:
  Mana Efficiency:
  Resilience:
  Penalties:
Reasons for deductions:
```

> For maximum independence you MAY run the Oracle as a fresh subagent (Agent tool, `general-purpose`). To keep it independent of Builder's *intent* without starving it of *facts*, give the subagent: the decklist, `references/oracle.md`, `references/brackets.md`, the **current Game Changers list**, and the **Research Dossier** (archetype + synergy notes) — but NOT the Builder's self-justification ledger. Without the dossier and Game Changers list it cannot legitimately score Commander Synergy / Win Conditions or count Game Changers, and would be forced to guess. Recommended on the first and final evaluations at minimum.

---

## 4. Critic — challenge everything (adversarial)

Switch to the **Critic** hat. Read `references/critic.md`. The Critic is adversarial and trusts neither Builder nor Oracle. It must:

- interrogate Builder's assumptions and Oracle's assumptions;
- ask whether experienced EDH players (per the Research Dossier) would disagree;
- check the deck against web evidence — is recent tech missing? does the build contradict consensus?;
- surface hidden weaknesses (weak mana base, no early interaction, win-cons too slow, over-reliance on commander);
- **detect pathologies**: oscillation, the same card repeatedly added/removed, overfitting to the Oracle's rubric, ignored web evidence, and **bracket drift** (creeping above `target_bracket`).

If any pathology is detected, **warn strongly** and direct the next Builder pass to break the loop (try a structurally different change, not a reverted one).

Critic output: a prioritized list of concrete, actionable defects, each tagged `[identity] / [bracket] / [theme] / [power] / [consistency] / [process]`, ending with an explicit verdict — **`CONVERGED`** (targets met, no blocking defects, no active pathology), **`CONTINUE`** (name the binding constraint the next Builder pass must attack), or **`STOP-NO-CONVERGENCE`** (budget exhausted or stuck — report the residual gap honestly). This verdict, not the Oracle's number, is the termination authority (see §5 guard #1).

---

## 5. Optimization loop

```
        ┌─────────► Builder ──► Oracle ──► Critic ──┐
        │                                           │
        └───────────────────────────────────────────┘
```

Repeat the Builder → Oracle → Critic cycle. Each iteration:

1. **Builder** applies changes addressing the Critic's highest-priority defects. **Change-budget per iteration: swap 3–8 cards** (each swap = one cut + one add, preserving the 100-card count) unless fixing a hard legality/identity violation, which may require more. This bounded step *tends to keep* the Oracle's score change small enough to honor the "no unexplained >1.0 Power jump" rule (§3) while still closing the power gap within the 3–6 iteration budget — but it is not a guarantee (8 high-impact swaps can still move power >1.0); when they do, the card-by-card justification below is the real guard, not the swap count. If a defect genuinely needs a larger rewrite (e.g. a full theme pivot), do it in one iteration but expect — and justify card-by-card — the larger Power delta. Builder MUST justify, in writing:
   - why previous changes **succeeded** (kept),
   - why previous changes **failed** (reverted),
   - why the current revision **differs** from anything tried before.
   - **Never repeat a reverted change unless new evidence (web or Oracle) justifies it.**
2. **Oracle** re-scores. Enforce the no-large-unexplained-jump rule.
3. **Critic** re-challenges and updates the pathology watch.

Maintain a running **change ledger** (card in / card out / reason / outcome) across all iterations — this becomes the Optimization History and must never be erased.

**Iteration budget:** aim to converge in 3–6 iterations. Continue beyond 6 only when the Critic identifies a concrete unresolved blocker with a plausible fix. The hard cap remains 20 iterations.

**Termination:** stop when

```
power >= target_power  AND  deck PASSES target_bracket's restriction checklist (§0a)
```

where `power = min(local_oracle, remote_oracle)`, and convergence means **POWER ≥ `target_power` AND the deck passes `target_bracket`'s restriction checklist (§0a)** — note the bracket condition is a **checklist pass/fail, not a numeric `bracket ≤ target_bracket` comparison** (bracket is a construction-rules checklist, never a power-number band). Or stop when **20 iterations** are reached. If you hit 20 without converging, stop and report the best deck found plus the unresolved gap — do not fabricate convergence.

**Three guards before you may declare convergence (all required — the raw Oracle number alone is NOT sufficient):**
1. **Minimum one full Critic pass.** Never terminate on iteration 0's Oracle score; the adversarial Critic must have reviewed the deck at least once and issued a `CONVERGED` (or no remaining `[identity]/[bracket]/[power]` defects) verdict. The Critic's verdict — not the Oracle's number — is the termination authority.
2. **Both oracles must clear the target — governing power is the LOWER of the two (`min`).** Obtain a **real remote-oracle (CommanderSalt) reading AUTOMATICALLY** — never estimated, and do NOT ask the user (the loop runs the query itself). Method (`references/remote-oracle.md`): **create the deck once** with `scripts/upload_to_archidekt.py` (writes a `<deck>.archidekt.json` manifest), then at every later checkpoint **update it in place** with `scripts/upload_to_archidekt.py --deck deck.txt --update` (manifest-backed diff: deletes removed relations, adds new — same deck id/URL), and score with `scripts/query_commandersalt.py --archidekt-id <id>`. The deck must be **public** (CommanderSalt can't read private/unlisted). Because the Archidekt URL stays stable, CommanderSalt refreshes the same entry on requery — no clutter on either side, no human paste, no login. Then `current_power = min(local, remote)`; converged only when **both** ≥ `target_power`. Revise toward whichever is lower (local 8 / remote 6 → it's really a 6, raise real power + fix local inflation; remote 8 / local 6 → keep improving the local-weak axis). Document both numbers + the CommanderSalt deck URL in the log. Only fall back to asking the user if the query script errors (API changed).
3. **Crossing the floor by a hair is suspicious.** `critic.md` flags any score that "conveniently" lands exactly on the user's target as the default failure mode. If POWER lands within ~0.2 of `target_power` and the Critic still has open power defects, treat it as not-yet-converged.

**The bracket checklist is the hard constraint; power is maximized within it.** Push power as high as possible *while still passing the checklist* — a Bracket-3 deck at POWER ~8 is a success, not a contradiction. Only stop short of the power target if reaching it would require a **banned** element (4th Game Changer, mass land denial, extra-turn chains, or a pre-turn-6 2-card infinite). If so, report the honest in-bracket power and tell the user what raising the bracket would unlock.

**Two-oracle calibration (REQUIRED at convergence — see guard #2 and `references/remote-oracle.md`):** the **remote-oracle (CommanderSalt)** governs alongside the local rubric, and `current_power = min(local, remote)`. Read the remote number for real and **automatically** — `scripts/upload_to_archidekt.py` then `scripts/query_commandersalt.py` (anonymous `POST /decks?url=` ingest + poll, no login, no human paste); never estimate it at the gate. Between real readings you may carry a calibration offset (`last_remote − last_local`) to *plan*, but the gate needs a fresh reading. **What raises the remote number is salt/staple density, not synergy alone** — CommanderSalt scores EDHREC salt-score + combos + bracket + synergy, so a low-salt value/combo pile caps ~6; add high-impact staples / Game Changers / fast mana the data rewards (use `GET https://api.commandersalt.com/meta` to spot them), within the bracket. Loop until **both** oracles ≥ `target_power`. This checks the *power number* only; it does NOT set the bracket. **Reconciliation rule: the external tool wins.** If it is >1.0 below the Oracle estimate, the Oracle was inflated — adopt the tool's number as POWER and do not declare convergence until the *tool's* number meets `target_power`. Record the actual tool number in `optimization-log.md`.

**High power IS achievable in a low bracket — build for it, don't raise the bracket.** A high external power (≈8 on CommanderSalt) requires a **compact, repeatable, protected win condition** — but that win can be *bracket-legal*. A Bracket-3 deck reaches ~8 by building around a **2-card infinite/near-infinite combo that assembles mid-game (~turn 6+, not earlier), within the 3-Game-Changer cap, with no MLD or extra-turn chains** — plus tutors to find it and fast mana to deploy it. The Cloud, Ex-SOLDIER reference deck does exactly this (Aggravated Assault + equipment = infinite combat, CommanderSalt ~8, still Bracket 3). What caps a deck at ~6 is being a **value/attrition pile with no compact kill**, NOT the bracket. So when `target_power` is high, the Builder's job is to add a bracket-legal compact win (see `references/builder.md` → "Building for high power within a bracket"), not to durdle on value or to escalate the bracket. Only escalate the bracket if the target genuinely needs an *early* (pre-turn-6) combo or a 4th+ Game Changer — i.e. CommanderSalt ≈9–10 / cEDH speed. If so, surface the choice per §0a; never fabricate the power number.

Practical guidance: you do not need to re-run full web research every iteration, but DO re-research whenever the Critic flags missing tech or a theme pivot. Keep iterations efficient; spend tokens on changes that move a binding constraint.

---

## 6. Write outputs — `deck.txt` (importable) + `optimization-log.md` (history)

Two separate artifacts. Keep them strictly separate: the deck file is the deck, nothing else.

**Run the §7 validation pass BEFORE writing these files.** §7 is a gate, not a postscript — a deck that fails validation must be fixed (and, if the fix changed cards, re-scored per §3) *before* anything is written, so the artifacts never reflect an unvalidated deck.

### 6a. `deck.txt` — the deck, as Archidekt-importable PLAIN TEXT

Write the final 100-card list to `deck.txt` in the current working directory. This file is consumed by Archidekt's importer, so it MUST be **pure plain text with NO markdown, NO prose, NO explanation, NO headers, NO blank-line section labels** — **only card lines**. Use `templates/deck.txt` as the reference.

**Line format (one card per line):**

```
<qty>x <Card Name> (<setcode>) [<Category>]
```

- `<qty>x` — quantity followed by a literal `x` (e.g. `1x`, `10x`).
- `<Card Name>` — exact Scryfall spelling (correct apostrophes, commas, accents).
- `(<setcode>)` — **OPTIONAL** lowercase set code (e.g. `(clb)`, `(soc)`). Include it ONLY when you are confident of the exact printing; otherwise **omit it** and let Archidekt auto-select. **Never fabricate a set code** — a wrong code can break the line on import.
- `[<Category>]` — **OPTIONAL** single Archidekt category that preserves the role grouping (e.g. `[Ramp]`, `[Removal]`, `[Blink]`, `[Land]`, `[Draw]`, `[Wincon]`). Tag the commander with `[Commander]`.

Rules:
- The file contains card lines and nothing else. The first line should be the commander, tagged `[Commander]`.
- Quantities must sum to exactly 100. Basics are collapsed (e.g. `10x Plains`).
- Do not write category header lines — categories live inline in `[...]`. A stray non-card line will be treated as a card and fail to import.

Example (illustrative, not a full deck):
```
1x Ketramose, the New Dawn [Commander]
1x Sol Ring [Ramp]
1x Swords to Plowshares [Removal]
1x Ephemerate [Blink]
10x Plains [Land]
```

### 6b. `optimization-log.md` — the analysis & history (separate file)

Write all human-facing analysis here, NOT in `deck.txt`. Use `templates/optimization-log.md`. It MUST contain:

- **Summary**, **Commander** (with color identity), **Estimated power** + **Confidence**, **Estimated bracket**, **Themes**, **Main win conditions**
- **Optimization history** — the full change ledger, iteration by iteration (**append, never erase**)
- **Strengths**, **Weaknesses**, **Risks**, **Confidence**

If `optimization-log.md` already exists, **first check its `## Commander` header matches the commander being built this run.** Only **append** the new iterations to the history if it is the **same commander**. If the existing log is for a *different* commander (a stale file from a previous, unrelated run), do NOT append onto it — start a fresh log (and warn the user that the old log is being replaced/renamed) so `deck.txt` and `optimization-log.md` never describe two different decks. Always regenerate `deck.txt` to the latest converged state.

After writing both files (validation per §7 having already passed *before* the write), perform the Archidekt auto-upload (§8) if it is enabled, then end your turn with a short chat summary: final power, bracket, confidence, whether targets were met, top residual risks, and — if uploaded — the Archidekt deck URL (or the upload failure + manual-import note).

---

## 7. Mandatory final validation pass

Run this mechanical validation pass **before writing the §6 outputs** (see §6). Do not skip it even if the Oracle and Critic converged.

Required checks:
- **Count:** exactly 100 total cards including the commander; commander + 99.
- **Singleton:** no two cards share an English name, EXCEPT (a) basic lands (any number); (b) cards whose own text explicitly says "A deck can have **any number** of cards named ___" — *unlimited* copies (e.g. Relentless Rats, Rat Colony, Persistent Petitioners, Shadowborn Apostle, Dragon's Approach, Slime Against Humanity, Hare Apparent — the printed roster grows over time, so confirm the exact line on Scryfall rather than trusting this list); and (c) cards that print "A deck can have **up to N** cards named ___" — a *bounded* exception, NOT unlimited (e.g. Seven Dwarves ≤ 7, Nazgûl ≤ 9). There is no general "the format allows it" exception — if a card prints neither line, exactly one copy is allowed. The Iron Rule applies to this check too: verify the card's actual Oracle text, never the copy limit from memory (a card "remembered" as unlimited may be capped or may not exist).
- **Commander legality:** every card is legal in Commander according to current legality data, AND the commander itself is eligible to be a commander — it must be a **legendary creature** or a card that explicitly says **"can be your commander"** (some planeswalkers/other types), or a legal **Partner / Partner with / Friends Forever / Background** pairing. A non-legendary, non-eligible card in the command zone is an automatic fail.
- **Exact names:** verify uncertain spelling, punctuation, accents, and current Oracle names with Scryfall.
- **Color identity:** every card, including lands, is inside the commander's color identity per CR 903.4 (mana symbols in cost AND rules text — including ability costs, hybrid, and Phyrexian symbols, and color indicators; reminder text excluded). Cross-check Scryfall's `color_identity` field for any card with off-color mana symbols in its text.
- **Forbidden lists:** no forbidden cards, forbidden combos, or forbidden strategies appear.
- **Companion:** if the deck uses a companion, it satisfies that companion's deckbuilding restriction and is listed in the sideboard convention, not as one of the 100. If no companion, skip.
- **Bracket checklist:** current official Game Changers count, mass land denial check, extra-turn-chain check, and early 2-card combo/lockout check are explicitly passed. For the 2-card-infinite check, cross-reference the deck's notable pairs against **Commander Spellbook** (`commanderspellbook.com`) rather than relying on memory (see `references/deckbuilding-logic.md §8`).
- **Curve gate (HARD):** land count meets the computed floor (~Karsten: ≈33–34 minimum, +1 per ~1.0 of average mana value above ~2.5–3.0, adjusted down only for genuine extra mana sources; MDFC land-backs count ~½). Below the floor the deck is a FAIL and cannot be finalized without an explicit, acknowledged override citing low avg MV + high cheap-card-advantage. Also check the soft **Flood line** (`recommended + 2`): above it, nudge to trim basics (not a blocker). See `references/deckbuilding-logic.md §7`.
- **Mana base:** colored source counts are plausible for the deck's pips and curve; utility lands and MDFCs are not overcounted as reliable colored sources.
- **Import format:** every `deck.txt` line follows `<qty>x <Card Name>` optionally followed by ` (<setcode>)` and/or ` [<Category>]` (both fields optional — a bare `1x Sol Ring` is valid), with no markdown, comments, placeholders, section headers, or blank-line labels.

If any check fails, fix the deck. If the fix changed which cards are in the deck, re-run Oracle (§3) and a Critic pass (§4) for the affected changes before proceeding to write §6 — a corrected deck still has to pass scoring. If the issue cannot be fixed within the target bracket or constraints, report the unresolved gap honestly in `optimization-log.md` and the final chat summary.

---

## 8. Auto-upload to Archidekt (optional)

After the deck has converged, passed validation (§7), and `deck.txt` is written (§6), upload it to the user's Archidekt account. Read `references/upload.md` for the full contract; the summary:

**When to upload.** Upload when the user asked for it (e.g. "upload to Archidekt", "push it to my account") or has it enabled by default. If the user has not indicated either way, ask once whether they want it uploaded — do not upload silently on a first run. `deck.txt` is always written regardless, so upload is purely additive.

**Relationship to the remote-oracle scoring deck (important — avoid a double upload).** The automatic CommanderSalt scoring in §5 guard #2 *already* creates one public Archidekt deck on the user's account (create-once, then `--update` in place) and records its id/URL in the `<deck>.archidekt.json` manifest. **That scoring deck IS the deck §8 surfaces — §8 does NOT create a second one.** If a manifest exists, the §8 "upload" is just a final `--update` to the converged list plus surfacing the existing URL. Because scoring necessarily writes to the user's Archidekt account, the consent question above is really *"may I use your Archidekt account at all this run?"*: if the user declines or `ARCHIDEKT_EMAIL/PASSWORD` are unset, the remote-oracle falls back to asking for a pasted CommanderSalt number (`references/remote-oracle.md §5`) and §8 falls back to manual import — neither path creates an Archidekt deck.

**Credentials.** The uploader reads `ARCHIDEKT_EMAIL` and `ARCHIDEKT_PASSWORD` from the environment. If they are absent, do **not** prompt for or store the password yourself — tell the user to set those two environment variables (shell profile or Claude Code `settings.json` `env` block) and fall back to manual import for this run.

**How.** Run the script from the directory containing `deck.txt`:

```
# No manifest yet (scoring never ran, or upload-only run) — create the deck:
python3 scripts/upload_to_archidekt.py --deck deck.txt --name "<commander/deck name>" --format edh [--bracket <1-5>]

# A manifest already exists (the §5 scoring deck) — push the converged list to that SAME deck:
python3 scripts/upload_to_archidekt.py --deck deck.txt --update
```

- Use the converged deck's name (default: the `[Commander]` card) and the target bracket.
- **If `<deck>.archidekt.json` already exists** (the scoring loop created it), run with `--update` so the existing deck is reused in place — do NOT create a duplicate. Only the no-manifest form creates a fresh deck.
- The script logs in, creates-or-updates the deck, resolves every card via Archidekt's server-side parser (the same Archidekt text format `deck.txt` uses), and saves them. On success its **last stdout line is the deck URL** — surface that to the user.
- Optionally run with `--dry-run` first to confirm `deck.txt` parses, especially if you changed the format.

**On failure (REQUIRED fallback).** Any non-zero exit code means the upload did not fully succeed. Do **not** treat this as a failed build. Report the error briefly, and tell the user to import `deck.txt` manually at archidekt.com (New Deck → import). Map the exit code per `references/upload.md` (3 = set the env vars; 4 = check credentials; 6 = card resolve/save failed — a deck may have been created but empty/partial: **give them the URL only if the script actually printed one** (a resolve failure exits 6 before any deck is created, so there is no URL), plus the manual-import instruction). Never claim the deck was uploaded unless the script exited 0.

**Honesty.** Report the upload outcome faithfully in the final chat summary: uploaded (with URL), or not uploaded (with the reason and the manual-import note). Never fabricate a deck URL.

---

## Guardrails

- **Identity & legality are hard constraints.** A card outside color identity or on a forbidden list is an automatic reject regardless of power.
- **Bracket is a ceiling, not a target to exceed.** If the Oracle reports `bracket > target_bracket`, that is a failure even if power is high — the Builder must remove the specific checklist violation before the loop can terminate.
- **Determinism over flair.** The Oracle's rubric is fixed; do not invent new scoring mid-run.
- **Evidence over vibes.** Every nontrivial inclusion should trace to the Research Dossier or an explicit synergy argument.
- This skill is **generic**: it must work for any commander. Nothing here is Ketramose-specific.
- **Upload is additive and never masks a failure.** `deck.txt` is always the source of truth and is written before any upload (§8). A failed Archidekt upload falls back to manual import; never report a deck as uploaded unless the uploader exited 0, and never fabricate a deck URL.
