# Folder trees of the 45 systems

This folder holds the final folder trees that the 45 systems in Table 3 of the
InfoOrgBench paper produced, wherever we still have them. Each system file
gives the system key, the model and harness names, the run used in the paper
and, for each task, the folder path of every record ID. The files contain no
record text, prompts, transcripts, token usage, provider IDs or private run
IDs.

We have the trees of 5,368 of the 6,750 outputs. Scoring them again with the
released scorer reproduces every per-task score in
[per-task.csv](../per-task.csv) to within 1e-9. The other 1,382 outputs are
listed under [Missing outputs](#missing-outputs) and are left out of each
system's `tasks` mapping. No tree was reconstructed from a published score.

## Coverage

Each cell gives how many of the 50 tasks have a tree here that reproduces the
published scores. The last column counts folders whose name was replaced (see
[Folder names](#folder-names)); a folder counts once even when several records
sit in it.

| System | Recap | Thread | Design | Renamed folders |
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

## Folder names

The folder names are the ones the models wrote, with a few exceptions. For
Thread, we compared every folder name with the Jira text of the rebuilt tasks,
ignoring case and spacing, and replaced the name with a neutral `G` name when
it copied 6 or more consecutive words of that text. In all families, we also
replaced names that contained an email address, a URL, a user path, something
that looks like a secret, or another pattern that `tools/check_release.py`
flags.

Only 2 folders needed a new name, which appears in 6 record paths: one folder
in `gpt-6-luna__dsh` and one in `gpt-6-luna__react-fc`, both because they
copied Jira text. Each new name is used consistently within its task, so the
tree and its scores do not change.

## Scoring the trees again

You need Python 3.11 or newer. The script uses only the standard library and
`benchmark/engine`. From the repository root:

```bash
python results/rescore.py --reference-only-thread --require-thread
```

From `results/`, the same check is `python rescore.py`. The scorer needs only
record IDs and folder paths, so `--reference-only-thread` scores the Thread
outputs with blank record bodies; it does not download or write any Jira
text. If you have built the Thread tasks (see
[docs/THREAD-DATA.md](../../docs/THREAD-DATA.md)), you can use them instead:

```bash
python results/rescore.py --thread-packets PATH --require-thread
```

Without either Thread option, the script behaves like `benchmark/replay.py`
and skips Thread until its tasks have been built. With `--require-complete`,
the missing outputs listed below count as a failure.

The script prints `PASS` when every available tree reproduces its scores in
`per-task.csv`. GPT-6 Luna with Codex is a special case: its per-task scores
were not kept, only its family scores in the authors' result catalog (see
[What is not included](../README.md#what-is-not-included)). Its trees
reproduce the Structure Score and folder economy of every family, but not the
published pooled Triplet F1: Recap 43.1 rather than 44.9, Thread 48.6 rather
than 59.8, and Design 89.3 rather than 91.2. The script lists these 3 values
as `CATALOG-ONLY` differences rather than as failures.

## Missing outputs

Task ranges include both ends. The reasons in the table mean:

- **Only the scores were kept.** The authors' result catalog keeps the scores
  of these runs, but their folder trees are neither in the 4 archives prepared
  for the release nor in any local copy of the experiment repositories that we
  could still read.
- **Left out because of Jira text.** The captured workspace of the output was
  removed from our archive when it was screened for Jira text, and the score
  files we kept do not list folder paths.
- **The rerun was not kept.** The archive holds an earlier run of this task,
  but the paper uses the rerun `terra-rfc-mini-fill-r3`, whose files were not
  kept.
- **Different Design records.** This run used an earlier set of Design records
  in which the record IDs point to different excerpts than in the released
  tasks, so its trees cannot be scored on the released tasks.

| System | Family | Missing tasks | Reason |
| --- | --- | --- | --- |
| `claude-haiku-4-5__codex` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__codex` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__codex` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__dsh` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__dsh` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__dsh` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-4-5__pi` | Thread | mini-031 | Left out because of Jira text |
| `claude-haiku-4-5__react-fc` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__codex` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__codex` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__codex` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__dsh` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__dsh` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__dsh` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__react-fc` | Design | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__react-fc` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `claude-haiku-5-5__react-fc` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `claude-sonnet-5-5__deep-agents` | Thread | mini-023, mini-031 | Left out because of Jira text |
| `gpt-5-6-luna__deep-agents` | Thread | mini-025 | Left out because of Jira text |
| `gpt-5-6-terra__react-fc` | Recap | mini-030 | The rerun was not kept |
| `gpt-6-1-sol__dsh` | Design | mini-001 to mini-005, mini-007 to mini-009, mini-011 to mini-018, mini-020 to mini-036, mini-038 to mini-046, mini-048 to mini-050 | Only the scores were kept |
| `gpt-6-1-sol__dsh` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `gpt-6-1-sol__dsh` | Thread | mini-002, mini-005 to mini-006, mini-008 to mini-013, mini-016 to mini-018, mini-020, mini-022 to mini-023, mini-026 to mini-027, mini-030, mini-032 to mini-037, mini-040 to mini-043, mini-045, mini-048 | Only the scores were kept |
| `gpt-6-luna__deep-agents` | Thread | mini-048 | Left out because of Jira text |
| `gpt-6-luna__pi` | Design | mini-035 | Left out because of Jira text |
| `grok-4-7__codex` | Design | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__codex` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__codex` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__dsh` | Design | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__dsh` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__dsh` | Thread | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__react-fc` | Design | mini-001 to mini-050 | Only the scores were kept |
| `grok-4-7__react-fc` | Recap | mini-001 to mini-050 | Only the scores were kept |
| `mai-code-1-1-flash__codex` | Design | mini-001 to mini-050 | Different Design records |
