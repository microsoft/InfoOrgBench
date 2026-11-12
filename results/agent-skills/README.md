# Agent Skills experiment results

These scores come from an experiment run after the paper, and they are not
part of it. It tested whether popular community Agent Skills for organizing
files change the Structure Score. [docs/AGENT-SKILLS.md](../../docs/AGENT-SKILLS.md)
describes the design and the results. The files contain scores, counts and
settings only, with no record text, prompts or transcripts.

| File | Contents |
| --- | --- |
| [summary.json](summary.json) | Family and average Structure Scores for each condition and model, paired differences with 95% intervals and p-values, and checks against the published runs |
| [per-task.csv](per-task.csv) | One row per condition, model and task: score, validity, records left in the inbox, tool calls, model turns, skill reads and pinned-skill messages |
| [folder-naming.json](folder-naming.json) | Share of folder names in lowercase-hyphen form, with digits and with spaces, for each round-1 condition |
| [grouping-similarity.json](grouping-similarity.json) | Adjusted Rand index between each round-1 condition's partitions and the no-skill control's, and between the control and the published run |

The scores can be recomputed with `python tools/skill_study.py analyze --out
<run folder>` from the saved runs, which are not distributed.
