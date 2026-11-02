# InfoOrgBench datasheet

This datasheet follows the questions in *Datasheets for Datasets* (Gebru et
al., 2021).

## Motivation

- **Purpose.** Measure whether agents can organize a fixed set of records
  into a hierarchy while preserving every record and its content.
- **Creators and funding.** The InfoOrgBench authors at Microsoft.

## Composition

| Family | Tasks | Records per task | Source | Reference |
| --- | --- | --- | --- | --- |
| Recap | 50 | See each packet | AMI meeting summary sentences | Meeting, then summary section |
| Design | 50 | See each packet | Kubernetes Enhancement Proposal excerpts | Owning SIG, then proposal |
| Thread | 50 | See each packet (built locally) | Apache Hadoop Jira issues, subtasks and comments | Parent issue, then subtask |

- **Instance.** A task packet lists records with opaque IDs and text. The
  reference assigns each record a path; agents never see it.
- **Thread text is not distributed.** Thread packets are rebuilt by the user
  from 42 public Apache Hadoop Jira issues with `benchmark/build_thread.py`
  ([docs/THREAD-DATA.md](THREAD-DATA.md)). The repository holds only their
  references, source IDs and hashes.
- **Saved outputs.** 1,500 deterministic baseline outputs, including 300
  identifier-masked diagnostics on Thread, and 200 model outputs (Claude Haiku
  4.5 and GPT-6.1 Sol on Recap and Thread). Each output is a list of record
  IDs and folder paths. Folder labels in model outputs were written by the
  models.
- **What the references mean.** References record source membership. They
  are not a unique human-validated organization; other reasonable trees exist.
- **Splits.** All 150 tasks are development tasks; there is no held-out split.
- **Personal data.** Distributed text comes unchanged from public, openly
  licensed sources and contains only what they published: AMI summaries mostly
  refer to meeting roles but name one person in two tasks, and two Kubernetes
  excerpts contain author GitHub handles. Hadoop issue text, which contains
  contributor names, handles and project e-mail addresses, is not distributed.
  Model outputs contain record IDs and model-written folder labels only; no
  label names a person.
- **Excluded.** Prompts, transcripts and logs of model runs.

## Collection and preprocessing

- Recap comes from `ami_public_manual_1.6.2.zip`; Design from
  `kubernetes/enhancements` at commit `e3ed21fdb51d359a2e73c714257f73cf453e8ba7`;
  Thread from the public Apache Hadoop Jira REST API.
- Whole source units were selected deterministically, records were given
  opaque IDs and shuffled, and text was left unchanged. The SHA-256 of every
  record body is stored in `benchmark/saved-results.json`.

## Uses

- **Intended.** Evaluating agents and harnesses on hierarchical organization
  with content preservation.
- **Not recommended.** Claims about human-preferred organization, or ranking
  models from these 150 development tasks alone. These are guidance, not
  restrictions on reuse.
- **Exposure.** All sources are public and may appear in model training data.

## Distribution and licence

- Code: MIT. Data authored for InfoOrgBench (references, outputs, metrics,
  metadata): set by Microsoft's dataset review before release; proposed MIT.
  Recap text: CC BY 4.0 (AMI Consortium). Design text: Apache-2.0 (The
  Kubernetes Authors). Thread text: not distributed. Third-party text is not
  relicensed by InfoOrgBench. See the [README](../README.md#licensing) and
  [NOTICE.md](../NOTICE.md).

## Maintenance

- Issues and corrections are tracked in GitHub Issues. Any change to a task,
  reference or saved output changes its hash and must keep replay passing.
