# Main results ledger

This folder holds the scores behind the main results table of the
InfoOrgBench paper (Table 3): 45 systems, each a pairing of one of nine
models with one of five agent harnesses, on the 50 Recap, 50 Thread and 50
Design tasks. It contains scores and run settings only, with no record text,
model outputs, prompts or transcripts.

| File | Contents |
| --- | --- |
| [systems.json](systems.json) | One entry per system: model and harness names, the selected run for each family, task and prompt versions, recorded run settings, family scores and the average. A separate `excluded` list gives the five Gemini 4 Argon pairings and the reason they are not in Table 3. |
| [per-task.csv](per-task.csv) | 6,750 rows, one per system and task: Structure Score, level-balanced and pooled Triplet F1, folder economy, clade F1, exact recovery, unsupported refinement triples and, where recorded, the per-level triple counts (reference-resolved, agreed, conflicting, unresolved and unsupported). |
| [table3-published.json](table3-published.json) | The values printed in the paper's Table 3, frozen for comparison. |
| [check_table3.py](check_table3.py) | Recomputes every family cell and average from `per-task.csv`, compares them with `systems.json` and renders them as in the paper. |

## Check the table

Python 3.11 or newer, standard library only:

```bash
cd results
python check_table3.py
```

The script recomputes each cell at a tolerance of 1e-9 and checks all
562 printed numbers of Table 3 (540 result cells plus model-name and layout
numbers). It prints `PASS` when every check succeeds.

## Metrics

For each family, Triplet F1 (Trip.) is the mean over the 50 tasks of the
per-task pooled triplet F1, the Structure Score is the mean of the 50
per-task Structure Scores, and folder economy E is the mean over valid
outputs. The table prints each value times 100 with one decimal, and the
penalty column as 100(1 − E). The average is the mean of the three family
cells. The scorer is in [benchmark/engine](../benchmark/engine); the
equations are in the paper.

## Coverage

| Field | Systems with all 50 tasks in every family |
| --- | ---: |
| Structure Score, Triplet F1, folder economy | 43 of 45 |
| Clade F1 and exact recovery | 33 of 45 |
| Per-level triple counts | 20 of 45 |

The two GPT-6 Luna systems with ReAct-FC and Codex have family scores
only, because their per-task score reports were not retained; the checker
reports them as catalog-level checks. For Claude Haiku 4.5 with DSH, the
Thread and Design folder-economy cells average over all outputs, as recorded
in the catalog, rather than over valid outputs. Blank CSV fields were not
recorded for that run. Thread tasks whose reference has no second level
leave the level-1 counts blank.

## What is not included

The final assignment trees for these systems are not included, except the
200 outputs in [benchmark/predictions](../benchmark/predictions), which
replay with [benchmark/replay.py](../benchmark/replay.py). Prompts,
transcripts, tool-call logs, token usage and harness code are not included.
Run names in `systems.json` identify the authors' runs; scores were taken
from the result catalog at commit `2495ac1` of the authors' experiment
repository.
