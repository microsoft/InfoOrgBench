# InfoOrgBench (anonymized for review)

This is an anonymized copy of the InfoOrgBench artifact for double-blind
review. Author and organization identifiers are withheld.

InfoOrgBench measures how agents organize fixed records into a hierarchy
while preserving every record unchanged.

## Contents

| Path | Contents |
| --- | --- |
| `benchmark/inputs/public/{Recap,Design}/` | 100 task packets (50 per family) as given to agents |
| `benchmark/inputs/reference/{Recap,Thread,Design}/` | Reference hierarchies for all 150 tasks (evaluator only; IDs and hashes, no text) |
| `benchmark/build_thread.py`, `benchmark/sources/hadoop-jira/` | Tool and issue list to build the 50 Thread packets from Apache Hadoop Jira |
| `benchmark/predictions/` | 1,700 saved outputs: 1,500 deterministic baselines and 200 model outputs |
| `benchmark/saved-results.json` | Expected metrics for every saved output |
| `benchmark/engine/` | Scorer |
| `benchmark/algorithm-source/` | Baseline predictors and fixed configurations |
| `benchmark/replay.py` | Offline replay of every saved output |
| `benchmark/run_task.py` | Prepare a task for any agent, then check and score its final folder tree |
| `docs/THREAD-DATA.md` | How to download the Jira issues and build the Thread packets |
| `results/` | Per-task scores and run settings of the paper's 45 systems, and `check_table3.py`, which reproduces the main results table |
| `results/assignments/`, `results/rescore.py` | Final assignment trees of the 45 systems (5,368 of 6,750 outputs) and a script that rescores them against the per-task scores |
| `harness/` | The ReAct-FC harness and adapters for Codex CLI, Pi, DeepSeek Harness and Deep Agents, with model access through GitHub Copilot or a provider API key |

Model outputs contain only record-to-folder assignments and the folder labels
the models wrote; Thread labels that copied Jira text were replaced with
neutral names. Transcripts and tool logs are not included. The prompts are in
`harness/`.

## Check the main results

```bash
python results/check_table3.py
python results/rescore.py --reference-only-thread --require-thread
```

`results/assignments/README.md` lists the outputs that were not retained.

## Replay

Python 3.11 or newer; no packages and no network access are needed.

```bash
cd benchmark
python -I -S -B replay.py --receipt replay-receipt.json
```

This verifies the SHA-256 of every file listed in `manifest.json` and rescores
the 900 Recap and Design outputs at a tolerance of 1e-12. Apache Hadoop Jira
text is not redistributed, so the 800 Thread outputs are reported as skipped
until you build the Thread packets (see `docs/THREAD-DATA.md`):

```bash
python build_thread.py --responses <folder with HADOOP-*.json>
python -I -S -B replay.py --require-thread --receipt replay-receipt.json
```

Network access and child processes are blocked during replay. Regenerating the
baselines additionally needs the packages pinned in
`benchmark/requirements-paper-pilot.txt`.

## Licences

The MIT licence in `LICENSE` covers the code, including `harness/` and the
scripts in `results/`, and the data written for the benchmark (references,
outputs, scores and metadata). Third-party text keeps its original licence and
is not relicensed: AMI meeting annotations (Recap) under CC BY 4.0 and
Kubernetes Enhancement Proposals (Design) under Apache-2.0. Apache Hadoop Jira
text is not included. See `NOTICE.md` for origins, attribution, changes and
licence texts.
