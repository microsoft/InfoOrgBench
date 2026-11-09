# Table 3 assignment trees

This directory contains final record-to-folder assignments for the systems in Table 3 of the InfoOrgBench paper. Each system file records the public system key, model and harness names, selected public run name, and assignment paths. It contains no record text, prompt, transcript, usage record, provider identifier, or private episode identifier.

The recovery found 5,368 of the 6,750 selected outputs. The released scorer reproduced every available per-task metric for the recovered outputs at a tolerance of 1e-9. The missing-output table lists the 1,382 unavailable outputs, which remain absent from each system's `tasks` mapping. Recovery did not infer any assignment from a published metric.

## Coverage

Each cell reports recovered and verified outputs out of 50 tasks. The table counts each replaced label node once, even when several records use it.

| System | Recap | Thread | Design | Replaced label nodes |
| --- | ---: | ---: | ---: | ---: |
| `claude-haiku-4-5__react-fc` | 50/50 | 50/50 | 0/50 | 0 |
| `claude-haiku-4-5__pi` | 50/50 | 49/50 | 50/50 | 0 |
| `claude-haiku-4-5__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-haiku-4-5__dsh` | 0/50 | 0/50 | 0/50 | 0 |
| `claude-haiku-4-5__codex` | 0/50 | 0/50 | 0/50 | 0 |
| `claude-haiku-5-5__react-fc` | 0/50 | 0/50 | 0/50 | 0 |
| `claude-haiku-5-5__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-haiku-5-5__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-haiku-5-5__dsh` | 0/50 | 0/50 | 0/50 | 0 |
| `claude-haiku-5-5__codex` | 0/50 | 0/50 | 0/50 | 0 |
| `claude-sonnet-5-5__react-fc` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-sonnet-5-5__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-sonnet-5-5__deep-agents` | 50/50 | 48/50 | 50/50 | 0 |
| `claude-sonnet-5-5__dsh` | 50/50 | 50/50 | 50/50 | 0 |
| `claude-sonnet-5-5__codex` | 50/50 | 50/50 | 50/50 | 0 |
| `mai-code-1-1-flash__react-fc` | 50/50 | 50/50 | 50/50 | 0 |
| `mai-code-1-1-flash__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `mai-code-1-1-flash__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `mai-code-1-1-flash__dsh` | 50/50 | 50/50 | 50/50 | 0 |
| `mai-code-1-1-flash__codex` | 50/50 | 50/50 | 0/50 | 0 |
| `grok-4-7__react-fc` | 0/50 | 50/50 | 0/50 | 0 |
| `grok-4-7__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `grok-4-7__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `grok-4-7__dsh` | 0/50 | 0/50 | 0/50 | 0 |
| `grok-4-7__codex` | 0/50 | 0/50 | 0/50 | 0 |
| `gpt-5-6-luna__react-fc` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-luna__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-luna__deep-agents` | 50/50 | 49/50 | 50/50 | 0 |
| `gpt-5-6-luna__dsh` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-luna__codex` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-terra__react-fc` | 49/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-terra__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-terra__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-terra__dsh` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-5-6-terra__codex` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-6-luna__react-fc` | 50/50 | 50/50 | 50/50 | 1 |
| `gpt-6-luna__pi` | 50/50 | 50/50 | 49/50 | 0 |
| `gpt-6-luna__deep-agents` | 50/50 | 49/50 | 50/50 | 0 |
| `gpt-6-luna__dsh` | 50/50 | 50/50 | 50/50 | 1 |
| `gpt-6-luna__codex` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-6-1-sol__react-fc` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-6-1-sol__pi` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-6-1-sol__deep-agents` | 50/50 | 50/50 | 50/50 | 0 |
| `gpt-6-1-sol__dsh` | 0/50 | 20/50 | 5/50 | 0 |
| `gpt-6-1-sol__codex` | 50/50 | 50/50 | 50/50 | 0 |

## Label screening

The release retains model-written folder labels except where a label failed the release screen. For Thread, the screen compared labels with the locally rebuilt Apache Hadoop Jira packets after case folding and whitespace normalization. It replaced a label with a neutral `G` label when that label contained a verbatim span of six or more consecutive words. For all families, the screen also replaced labels containing an email address, URL, user path, secret-like value, or another pattern used by `tools/check_release.py`.

Two folder nodes were replaced across six assignment-path occurrences. One node occurs in `gpt-6-luna__dsh`, and one occurs in `gpt-6-luna__react-fc`; both matched the Thread verbatim-span rule. No other system required a replacement. Replacements are consistent within each task, so they preserve the tree and its scores.

## Rescoring

Python 3.11 or newer is sufficient. The script uses only the standard library and `benchmark/engine`.

From the repository root, rescore all available outputs, including Thread through the reference-only structural path:

```bash
python results/rescore.py --reference-only-thread --require-thread
```

The same command can be run from `results/` as `python rescore.py`. The reference-only mode supplies blank record bodies because the released scorer uses record IDs and paths for these metrics. It does not write or distribute Jira text. A locally rebuilt packet directory can instead be supplied with:

```bash
python results/rescore.py --thread-packets PATH --require-thread
```

Without either Thread option, the script follows `benchmark/replay.py` and reports Thread as skipped when its packets have not been built. `--require-complete` additionally treats the missing outputs listed below as a failure. The default result is `PASS` when every available per-task metric reproduces the ledger. The script reports catalog-only aggregates separately. GPT-6 Luna with Codex has no retained per-task metric rows. Its rescored Structure Score and economy means reproduce the catalog, but its pooled Triplet F1 means do not: Recap is 0.43147635888391617 rather than 0.4492053975314347, Thread is 0.4857653223564322 rather than 0.5979874698458146, and Design is 0.8927056271220666 rather than 0.9118822058881926. The script reports these three values as `CATALOG-ONLY` differences rather than per-task failures.

## Missing outputs

The task ranges below are inclusive and give the exact missing set.

| System | Family | Missing tasks | Reason |
| --- | --- | --- | --- |
| `claude-haiku-4-5__codex` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__codex` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__codex` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__dsh` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__dsh` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__dsh` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-4-5__pi` | Thread | mini-031 | Selected capture was excluded from the custody asset after source-text screening; retained result and score receipts contain no assignments. |
| `claude-haiku-4-5__react-fc` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__codex` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__codex` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__codex` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__dsh` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__dsh` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__dsh` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__react-fc` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__react-fc` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-haiku-5-5__react-fc` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `claude-sonnet-5-5__deep-agents` | Thread | mini-023, mini-031 | Selected capture was excluded from the custody asset after source-text screening; retained result and score receipts contain no assignments. |
| `gpt-5-6-luna__deep-agents` | Thread | mini-025 | Selected capture was excluded from the custody asset after source-text screening; retained result and score receipts contain no assignments. |
| `gpt-5-6-terra__react-fc` | Recap | mini-030 | The archive binds the earlier episode; the ledger selects terra-rfc-mini-fill-r3, whose capture is absent from the archives and local clones. |
| `gpt-6-1-sol__dsh` | Design | mini-001 to mini-005, mini-007 to mini-009, mini-011 to mini-018, mini-020 to mini-036, mini-038 to mini-046, mini-048 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `gpt-6-1-sol__dsh` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `gpt-6-1-sol__dsh` | Thread | mini-002, mini-005 to mini-006, mini-008 to mini-013, mini-016 to mini-018, mini-020, mini-022 to mini-023, mini-026 to mini-027, mini-030, mini-032 to mini-037, mini-040 to mini-043, mini-045, mini-048 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `gpt-6-luna__deep-agents` | Thread | mini-048 | Selected capture was excluded from the custody asset after source-text screening; retained result and score receipts contain no assignments. |
| `gpt-6-luna__pi` | Design | mini-035 | Selected capture was excluded from the custody asset after source-text screening; retained result and score receipts contain no assignments. |
| `grok-4-7__codex` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__codex` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__codex` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__dsh` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__dsh` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__dsh` | Thread | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__react-fc` | Design | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `grok-4-7__react-fc` | Recap | mini-001 to mini-050 | The selected component run is absent from the four release archives and the readable local experiment clones; the catalog retains metrics but not the assignment tree. |
| `mai-code-1-1-flash__codex` | Design | mini-001 to mini-050 | The selected run used a noncomparable Design record set whose bindings differ from the released reference, so the captured tree cannot be rescored on the released task. |
