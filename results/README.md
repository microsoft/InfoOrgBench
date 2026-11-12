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
cells. The scorer is in [benchmark/engine](../benchmark/engine), and
[docs/EVALUATION.md](../docs/EVALUATION.md) explains every metric step by
step.

## Coverage

| Field | Systems with all 50 tasks in every family |
| --- | ---: |
| Structure Score, Triplet F1, folder economy | 43 of 45 |
| Clade F1 and exact recovery | 33 of 45 |
| Per-level triple counts | 20 of 45 |

The two GPT-6 Luna systems with ReAct-FC and Codex have family scores
only, because their per-task score reports were not retained; the checker
compares them with the family scores in the authors' result catalog (see
[What is not included](#what-is-not-included)). For Claude Haiku 4.5 with DSH, the
Thread and Design folder-economy cells average over all outputs, as recorded
in the catalog, rather than over valid outputs. Blank CSV fields were not
recorded for that run. Thread tasks whose reference has no second level
leave the level-1 counts blank.

## Assignment trees

[assignments/](assignments) holds the final trees of 5,368 of the 6,750
outputs, and [rescore.py](rescore.py) rescores them with
[benchmark/engine](../benchmark/engine) and compares each score with
`per-task.csv`:

```bash
python results/rescore.py --reference-only-thread --require-thread
```

Every available output reproduces its per-task scores. The trees also give
per-task scores for the two GPT-6 Luna systems that have only family scores in
this ledger. For GPT-6 Luna with Codex they reproduce the Structure Score and
folder economy of every family, but not the published pooled Triplet F1
(Recap 43.1 rather than 44.9, Thread 48.6 rather than 59.8, Design 89.3
rather than 91.2); the catalog value for that row appears to use a different
Triplet F1 variant. [assignments/README.md](assignments/README.md) gives the
coverage and the reasons for missing outputs.

## What is not included

Transcripts, tool-call logs, token usage and source text are not included.
The prompts and harness code are in [harness](../harness). Run names in
`systems.json` identify the authors' runs; scores were taken from the result
catalog at commit `2495ac1` of the authors' experiment repository.
