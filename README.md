# InfoOrgBench

**InfoOrgBench** (Information Organization Benchmark) measures how agents
organize a fixed set of records into a hierarchy while keeping every record
unchanged. The scorer compares the final folder tree with a source-derived
reference; folder names are not scored.

**Version:** 1.0.0 (release candidate)

> [!NOTE]
> **Licence scope.** The MIT licence in [LICENSE](LICENSE) covers the
> InfoOrgBench code only. Text taken from other sources stays under its
> original licence and is not relicensed: AMI meeting annotations under
> CC BY 4.0 and Kubernetes Enhancement Proposals under Apache-2.0. Apache
> Hadoop Jira text is not included; you download it yourself. See
> [Licensing](#licensing) and [NOTICE.md](NOTICE.md).

> [!IMPORTANT]
> **Release candidate.** This repository is not yet public. Publication waits
> for Microsoft's release and dataset reviews, tracked in
> [release/manifest.json](release/manifest.json).

## Contents

| Path | Contents |
| --- | --- |
| [benchmark/inputs/public/](benchmark/inputs/public) | Task packets as given to agents: 50 Recap and 50 Design. The 50 Thread packets are built locally (see below). |
| [benchmark/inputs/reference/](benchmark/inputs/reference) | Reference hierarchies for all 150 tasks, used only by the evaluator. They hold record IDs, source IDs and hashes, not record text. |
| [benchmark/build_thread.py](benchmark/build_thread.py) and [benchmark/sources/hadoop-jira/](benchmark/sources/hadoop-jira) | Tool and issue list for building the Thread packets from Apache Hadoop Jira |
| [benchmark/predictions/](benchmark/predictions) | 1,700 saved outputs: 1,500 deterministic baselines and 200 model outputs |
| [benchmark/saved-results.json](benchmark/saved-results.json) | Expected metrics for every saved output |
| [benchmark/engine/](benchmark/engine) | Scorer |
| [benchmark/algorithm-source/](benchmark/algorithm-source) | Baseline predictors and fixed configurations |
| [benchmark/replay.py](benchmark/replay.py) | Offline replay of every saved output |
| [results/](results) | Scores and run settings of the paper's 45 systems, per task, with a script that reproduces the main results table |
| [benchmark/manifest.json](benchmark/manifest.json) | SHA-256 of every file the replay reads |
| [docs/DATASHEET.md](docs/DATASHEET.md) | Dataset documentation |
| [docs/THREAD-DATA.md](docs/THREAD-DATA.md) | How to download the Jira issues and build the Thread packets |

### Task families

| Family | Source | Reference hierarchy | Released here |
| --- | --- | --- | --- |
| Recap | AMI Meeting Corpus manual annotations | Meeting, then summary section | Packets and references |
| Design | Kubernetes Enhancement Proposals | Owning SIG, then proposal | Packets and references |
| Thread | Apache Hadoop Jira | Parent issue, then subtask | References, issue list and build tool; you download the Jira text |

### Saved outputs

| Outputs | Conditions |
| --- | --- |
| 1,200 baseline outputs | On each family: flat filing, fixed cut and silhouette clustering (50 each), plus random assignment into the silhouette-predicted shape with five seeds (250) |
| 300 diagnostic outputs | On Thread only: silhouette clustering (50) and random shape assignment (250) with identifiers masked |
| 200 model outputs | Claude Haiku 4.5 and GPT-6.1 Sol, each with a ReAct function-calling harness, on the 50 Recap and 50 Thread tasks |

Model outputs contain only the final assignment of each record ID to a folder
path, including the folder labels the model wrote. Prompts, conversation
transcripts, tool-call logs and token usage are not included.

## Replay the reported scores

Python 3.11 or newer is required. Replay uses only the standard library and
needs no network access.

```bash
cd benchmark
python -I -S -B replay.py --receipt replay-receipt.json
```

Without the Thread packets, replay checks the 900 Recap and Design outputs and
reports the 800 Thread outputs as skipped. To include Thread, first download
the 42 Jira issues and build the packets as described in
[docs/THREAD-DATA.md](docs/THREAD-DATA.md):

```bash
python build_thread.py --responses <folder with HADOOP-*.json>
python -I -S -B replay.py --require-thread --receipt replay-receipt.json
```

Replay checks the SHA-256 of every file in `benchmark/manifest.json`, rescores
the saved outputs and compares every metric with `saved-results.json` at a
tolerance of 1e-12. Network access and child processes are blocked while it
runs. Regenerating the baselines also needs the packages pinned in
`benchmark/requirements-paper-pilot.txt`.

## Licensing

| Material | Licence |
| --- | --- |
| Code (`benchmark/engine`, `benchmark/algorithm-source`, `benchmark/replay.py`, `tools`, `tests`) | MIT; see [LICENSE](LICENSE) |
| References, baseline and model outputs, metrics and metadata authored for InfoOrgBench | MIT; see [LICENSE](LICENSE) |
| Recap record text from the AMI Meeting Corpus (`benchmark/inputs/public/Recap/`) | CC BY 4.0 ([licence](https://creativecommons.org/licenses/by/4.0/)); © AMI Consortium |
| Design record text from Kubernetes Enhancement Proposals (`benchmark/inputs/public/Design/`) | Apache-2.0; © The Kubernetes Authors |
| Thread record text from the Apache Hadoop issue tracker | Not included. You download it from [Apache Jira](https://issues.apache.org/jira/projects/HADOOP) under the terms that apply there. |

Each source keeps its original licence, and the MIT licence does not apply to
it. [NOTICE.md](NOTICE.md) gives each source's origin, attribution, the
changes we made and the full licence text.

## Intended use and limitations

- Use InfoOrgBench to evaluate agents and harnesses on organizing records into
  a hierarchy while keeping every record unchanged.
- References record source membership. They are not a unique human-validated
  organization, so other reasonable trees exist.
- All 150 tasks are development tasks; there is no held-out split, and
  tasks in a family can share source documents. Rankings describe these
  tasks and do not by themselves establish differences on new sources.
- All sources are public and may appear in model training data.
- The 200 saved model outputs come from two of the paper's 45 systems:
  Claude Haiku 4.5 and GPT-6.1 Sol, each with ReAct-FC, on Recap and Thread.
  Per-task scores and run settings for all 45 systems are in
  [results/](results). Prompts, transcripts, tool-call logs and harness code
  are not included.

## Release tooling

- `python tools/check_release.py` checks that every file belongs to a
  component in [release/manifest.json](release/manifest.json) and that no
  internal paths, addresses or credentials are present.
- `python tools/build_anonymous.py --archives` builds the anonymized copy used
  for double-blind review and verifies that replay still passes.

## Citation

A citation entry will be added when the accompanying paper is public.

## Contributing

This project welcomes contributions and suggestions. Most contributions
require you to agree to a Contributor License Agreement (CLA) declaring that
you have the right to, and actually do, grant us the rights to use your
contribution. For details, visit <https://cla.opensource.microsoft.com>. See
[CONTRIBUTING.md](CONTRIBUTING.md).

When you submit a pull request, a CLA bot will automatically determine whether
you need to provide a CLA and decorate the PR appropriately (e.g., status
check, comment). Simply follow the instructions provided by the bot. You will
only need to do this once across all repos using our CLA.

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the
[Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any
additional questions or comments.

## Security

Please do not report security vulnerabilities through public GitHub issues.
See [SECURITY.md](SECURITY.md) for how to report them to the Microsoft
Security Response Center (MSRC).

## Trademarks

This project may contain trademarks or logos for projects, products, or
services. Authorized use of Microsoft trademarks or logos is subject to and
must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must
not cause confusion or imply Microsoft sponsorship. Any use of third-party
trademarks or logos are subject to those third-party's policies.