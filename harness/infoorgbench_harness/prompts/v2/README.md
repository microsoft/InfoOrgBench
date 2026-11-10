# Task prompts

These files hold the task instruction that every harness sends to the model.
The text is the same for every model and harness, so differences between
systems come from the model and the harness, not from the wording.

## Files used in the paper

| Family | Shared instruction | Organizing criterion |
| --- | --- | --- |
| Recap | `protocol.v2.md` | `family-summary.v1.md` (meeting, then summary section) |
| Thread | `protocol.v2.md` | `family-issue.v1.md` (parent issue, then subtask) |
| Design | `protocol.v2.2.md` | `family-design-sections.v1.md` (owning group, then proposal) |

The shared instruction fixes the workspace, the rules for keeping records
unchanged, the evidence the agent may use and how to finish. The criterion
file describes the hierarchy for one family. `protocol.v2.2.md` differs from
`protocol.v2.md` only in dropping the sentence that asks the agent to read long
records completely.

`prompt.py` fills in the slots for one task: the workspace path, the checker
command and the number of records. For ReAct-FC, `h0_system.txt` adds the tool
instruction.

## Other files

`protocol.v2.1.md`, `family-design.v1.md`, `family-meeting.v1.md` and
`family-meeting-unanchored.v1.md` come from development runs before the paper's
experiments. They are kept so that the recorded prompt hashes of those runs
stay checkable; the paper's results do not use them.

## Hashes

Each run records the SHA-256 of the instruction and criterion files it used.
Do not edit these files: any change alters the hashes and makes a run
incomparable with the paper. Write a new versioned file instead.
