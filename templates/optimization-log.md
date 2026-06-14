<!--
optimization-log.md TEMPLATE — analysis & history ONLY. The decklist itself lives in deck.txt.
Optimization History is APPEND-ONLY: never erase prior iterations.
-->

# {{Deck Name}} — Optimization Log

> Importable decklist: see `deck.txt` (Archidekt plain-text format).

## Summary
{{2–4 sentences: gameplan and whether targets were met.}}

## Commander
- **Commander:** {{name}} ({{partner/background if any}})
- **Color identity:** {{WUBRG}}

## Targets vs. Result
| Metric | Target | Achieved |
|--------|--------|----------|
| Power — local-oracle | {{>= X.X}} | {{X.X / 10}} |
| Power — remote-oracle (CommanderSalt) | {{>= X.X}} | {{X.X / 10}} (real reading, not estimate) |
| **Power — governing = min(local, remote)** | {{>= X.X}} | {{X.X / 10}} |
| Bracket (checklist pass/fail) | {{target N}} | {{N — passes target's checklist? yes/no}} |
| Confidence | — | {{0–1}} |

> Converged only when BOTH oracles ≥ target. Record the real CommanderSalt number (deck URL / `commandersalt.com/details/deck/<id>`), never an estimate.

## Themes
- {{theme 1 (primary)}}
- {{…}}

## Constraints honored
- Forbidden cards / combos / strategies: {{list or "none"}}

## Main win conditions
1. {{primary kill}}
2. {{secondary}}
3. {{backup / inevitability}}

## Optimization history (APPEND-ONLY — do not erase)

### Research Dossier (summary)
- Sources consulted: {{EDHREC / Moxfield / Archidekt / Reddit / articles}}
- Consensus shell: {{…}}
- Documented disagreements: {{…}}
- Recent tech included: {{…}}
- Current Game Changers source checked: {{source/date}}
- Scryfall verification notes: {{name/color identity/legality checks}}

| Card | Role | Sources supporting | Sources disputing | Include/cut call | Reason |
|------|------|--------------------|-------------------|------------------|--------|
| {{card}} | {{role}} | {{sources}} | {{sources or none}} | {{include/cut}} | {{reason}} |

### Iteration 0 — Initial build
- **Builder:** {{rationale}}
- **Oracle:** Power {{X.X}}, Bracket {{N}}, Confidence {{C}} — components {{…}}
- **Critic:** {{top defects, verdict}}

### Iteration 1
- **Change ledger:** {{+ card / − card / reason}}
- **Builder justification:** kept / reverted / new&different
- **Oracle:** Power {{X.X}} (Δ {{…}}), Bracket {{N}}, Confidence {{C}}
- **Critic:** {{defects, verdict}}

<!-- continue appending; never delete earlier iterations -->

## Strengths
- {{…}}

## Weaknesses
- {{…}}

## Risks
- {{bracket-drift risk, meta vulnerabilities, fragile engines, unresolved disagreements}}

## Final validation
- Count: {{100/100}}
- Singleton/legal exceptions: {{pass/fail}}
- Commander legality + eligibility: {{pass/fail}}
- Companion (if any): {{n/a or pass/fail}}
- Color identity (CR 903.4): {{pass/fail}}
- Forbidden lists: {{pass/fail}}
- Bracket checklist: {{Game Changers X/Y; MLD no; extra-turn chains no; early compact combo no}}
- Mana base source check: {{summary}}
- Archidekt import format: {{pass/fail}}

## Confidence
- **{{0–1}}** — {{what drives confidence up/down}}
