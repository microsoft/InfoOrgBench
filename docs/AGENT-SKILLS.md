# Skills eval: do Agent Skills help agents organize?

This experiment was run after the paper and is not part of it. It asks whether
popular community [Agent Skills](https://agentskills.io) for organizing files
raise an agent's Structure Score on the 150 InfoOrgBench tasks. The
[README](../README.md#do-agent-skills-help) gives the short version. This page
gives the design, every estimate with its interval, the error analysis, the
limitations and how to [test your own skill](#try-your-own-skill). Per-task scores are in [results/agent-skills/](../results/agent-skills).

## Answer

No skill produced a detectable change in the average Structure Score. Over 5
organizing skills, 3 Claude models and 2 ways of loading a skill, every
difference from a same-day run without a skill lay between −0.83 and
+1.00 points out of 100. Every 95% interval included 0, and every
Holm-adjusted p-value was at least 0.23. The intervals reach from
−1.97 to +2.21, so changes of up to about 2 points in either
direction cannot be excluded. The agents followed the skills' naming rules, but
grouped the records about as they did without a skill. Each pinned skill still
made a task cost 4% to 9% more at API prices with Claude Haiku 5.5
and Claude Sonnet 5.5.

## Skills

Popularity is the all-time install count on [skills.sh](https://skills.sh),
retrieved on 10 November 2026 with 61 search terms. A skill was eligible when
its main purpose is organizing an existing collection of files or information
items by their content, and its guidance does not depend on a particular
application, API key, MCP server or user path. Round 1 tested the 3
most-installed eligible skills, and round 2 the next 2. Several more-installed
skills matched the search but failed the screen. The most-installed match,
`obsidian-vault`, manages one hard-coded note vault, and
`recipe-organize-drive-folder` is written entirely as Google Drive commands.
[harness/configs/community-skills.json](../harness/configs/community-skills.json)
lists every screened skill with the reason for its exclusion, and pins each
tested skill by commit and SHA-256. The skill text is not redistributed here;
`fetch-skills` downloads and verifies it.

| Skill | Source | Installs | `SKILL.md` | Round |
| --- | --- | ---: | ---: | :---: |
| file-organizer | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 7,276 | 11,312 bytes | 1 |
| File Organizer | [claude-office-skills/skills](https://github.com/claude-office-skills/skills) | 5,612 | 6,828 bytes | 1 |
| invoice-organizer | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 5,379 | 12,010 bytes | 1 |
| Invoice Organizer | [claude-office-skills/skills](https://github.com/claude-office-skills/skills) | 4,749 | 8,863 bytes | 2 |
| Email Classifier | [claude-office-skills/skills](https://github.com/claude-office-skills/skills) | 4,713 | 6,640 bytes | 2 |
| mcp-builder (unrelated control) | [anthropics/skills](https://github.com/anthropics/skills) | 139,595 | 11,129 bytes | 1 |

## Design

- **Agent.** Deep Agents 0.7.23 with the 5 record tools of the paper's runs,
  through the GitHub Copilot backend. Claude Haiku 5.5 and Claude Sonnet 5.5
  used medium reasoning effort and 128,000 output tokens. Claude Haiku 4.5
  used its provider's default reasoning setting and 64,000 output tokens.
- **Pinned skill (main conditions).** The `SKILL.md` body is added to the
  conversation before the first model call, as when a user invokes the skill
  by name, so the agent sees it on every task. The skills middleware also adds
  a short generic section to the system prompt with each skill's name and
  description.
- **Offered skill.** Only the name and description are listed. The agent may
  open the skill with `read_file`, which can read only the skill's files.
- **Controls.** Each skill run is compared with a run of the same agent
  without a skill, made on the same day in the same interleaved order. Round 2
  had its own no-skill run. `mcp-builder`, a skill about building MCP servers
  of nearly the same length as the ComposioHQ file organizer, was pinned in
  the same way. It separates a skill's advice from the extra prompt text and
  the generic skills section.
- **Runs.** Round 1 had 6 conditions × 2 models × 150 tasks (1,800 episodes).
  Round 2 had 3 conditions × 2 models × 150 tasks (900). Because neither
  round-2 skill helped, the 2 most-installed skills were then run with Claude
  Haiku 4.5 (3 conditions × 150 tasks, 450). Every episode ran once, in its own
  process. Transient upstream failures, such as HTTP 502, were retried under
  a rule fixed before the runs, and every analyzed episode completed.
- **Analysis.** For each task, the skill's score minus the no-skill score.
  Averages give the 3 families equal weight. Intervals are 95% percentile
  bootstrap intervals over tasks, resampled within families (10,000
  resamples). p-values are from a two-sided sign-flip permutation test (20,000
  permutations). The skills, conditions and comparisons were written down
  before the runs, and Holm correction covers each planned group: the 6
  round-1 comparisons, the 4 round-2 comparisons and the 2 Haiku 4.5
  comparisons. The unrelated control was added after round 1 had started,
  when 43 episodes had finished and no comparison had been computed.
  The offered skill and the unrelated skill are secondary comparisons without
  correction.

## Results

### Scores

Structure Score (0 to 100). The average is the mean of the 3 family scores.

| Condition | Model | Recap | Thread | Design | Average |
| --- | --- | ---: | ---: | ---: | ---: |
| No skill | Haiku 5.5 | 39.0 | 63.7 | 91.9 | 64.9 |
| file-organizer (ComposioHQ) | Haiku 5.5 | 36.2 | 64.0 | 92.8 | 64.3 |
| invoice-organizer (ComposioHQ) | Haiku 5.5 | 38.8 | 64.2 | 90.8 | 64.6 |
| File Organizer (claude-office-skills) | Haiku 5.5 | 38.7 | 66.3 | 92.0 | 65.7 |
| file-organizer (ComposioHQ), offered only | Haiku 5.5 | 39.8 | 64.9 | 91.7 | 65.5 |
| mcp-builder (unrelated) | Haiku 5.5 | 40.4 | 65.4 | 91.7 | 65.9 |
| No skill, round 2 | Haiku 5.5 | 40.0 | 64.1 | 91.4 | 65.2 |
| Invoice Organizer (claude-office-skills) | Haiku 5.5 | 38.2 | 64.0 | 91.3 | 64.5 |
| Email Classifier (claude-office-skills) | Haiku 5.5 | 38.8 | 65.5 | 91.9 | 65.4 |
| No skill | Sonnet 5.5 | 48.3 | 73.9 | 93.4 | 71.9 |
| file-organizer (ComposioHQ) | Sonnet 5.5 | 46.8 | 74.0 | 93.7 | 71.5 |
| invoice-organizer (ComposioHQ) | Sonnet 5.5 | 45.9 | 74.6 | 92.6 | 71.0 |
| File Organizer (claude-office-skills) | Sonnet 5.5 | 47.9 | 73.3 | 93.5 | 71.6 |
| file-organizer (ComposioHQ), offered only | Sonnet 5.5 | 49.4 | 73.9 | 93.6 | 72.3 |
| mcp-builder (unrelated) | Sonnet 5.5 | 48.3 | 75.9 | 93.5 | 72.6 |
| No skill, round 2 | Sonnet 5.5 | 49.2 | 73.1 | 93.3 | 71.8 |
| Invoice Organizer (claude-office-skills) | Sonnet 5.5 | 47.4 | 75.5 | 93.7 | 72.2 |
| Email Classifier (claude-office-skills) | Sonnet 5.5 | 48.2 | 72.0 | 93.5 | 71.2 |
| No skill | Haiku 4.5 | 38.1 | 46.5 | 78.6 | 54.4 |
| file-organizer (ComposioHQ) | Haiku 4.5 | 38.7 | 46.6 | 80.4 | 55.3 |
| File Organizer (claude-office-skills) | Haiku 4.5 | 39.8 | 46.8 | 79.5 | 55.4 |

### Differences from the no-skill run

| Skill | Model | Difference | 95% interval | p | Holm p |
| --- | --- | ---: | :---: | ---: | ---: |
| file-organizer (ComposioHQ) | Haiku 5.5 | −0.52 | [−1.66, +0.62] | 0.39 | 1.00 |
| file-organizer (ComposioHQ) | Sonnet 5.5 | −0.33 | [−1.50, +0.82] | 0.57 | 1.00 |
| File Organizer (claude-office-skills) | Haiku 5.5 | +0.81 | [−0.48, +2.08] | 0.23 | 1.00 |
| File Organizer (claude-office-skills) | Sonnet 5.5 | −0.30 | [−1.48, +0.89] | 0.63 | 1.00 |
| invoice-organizer (ComposioHQ) | Haiku 5.5 | −0.25 | [−1.31, +0.88] | 0.67 | 1.00 |
| invoice-organizer (ComposioHQ) | Sonnet 5.5 | −0.83 | [−1.97, +0.29] | 0.16 | 0.96 |
| Invoice Organizer (claude-office-skills) | Haiku 5.5 | −0.65 | [−1.80, +0.45] | 0.27 | 1.00 |
| Invoice Organizer (claude-office-skills) | Sonnet 5.5 | +0.33 | [−0.91, +1.60] | 0.62 | 1.00 |
| Email Classifier (claude-office-skills) | Haiku 5.5 | +0.26 | [−0.92, +1.38] | 0.67 | 1.00 |
| Email Classifier (claude-office-skills) | Sonnet 5.5 | −0.63 | [−1.87, +0.61] | 0.34 | 1.00 |
| file-organizer (ComposioHQ) | Haiku 4.5 | +0.88 | [−0.35, +2.10] | 0.17 | 0.23 |
| File Organizer (claude-office-skills) | Haiku 4.5 | +1.00 | [−0.23, +2.21] | 0.11 | 0.23 |

Round-2 skills are compared with the round-2 no-skill run; all others with the
round-1 no-skill run of the same model.

| Skill | Model | Difference | 95% interval | p |
| --- | --- | ---: | :---: | ---: |
| file-organizer (ComposioHQ), offered only | Haiku 5.5 | +0.60 | [−0.47, +1.75] | 0.30 |
| file-organizer (ComposioHQ), offered only | Sonnet 5.5 | +0.46 | [−0.69, +1.59] | 0.44 |
| mcp-builder (unrelated) | Haiku 5.5 | +0.99 | [−0.08, +2.10] | 0.08 |
| mcp-builder (unrelated) | Sonnet 5.5 | +0.71 | [−0.48, +1.88] | 0.25 |

The averages hide large changes on single tasks in both directions. The
standard deviation of a per-task difference was 7.0 to 8.2 points. With the
ComposioHQ file organizer, for example, Sonnet 5.5 scored higher on 61 tasks
and lower on 58.

### When the skill is only offered

Usually a skill is only installed, and the agent decides whether to open it.

| file-organizer (ComposioHQ), offered only | Haiku 5.5 | Sonnet 5.5 |
| --- | ---: | ---: |
| Tasks where the agent opened the skill | 60 of 150 | 14 of 150 |
| No-skill score on those tasks | 59.3 | 62.0 |
| No-skill score on the other tasks | 68.6 | 72.9 |
| Change on the tasks where it was opened (p) | +1.51 (0.11) | −1.12 (0.55) |
| Change on the other tasks (p) | −0.01 (0.99) | +0.62 (0.33) |

The agent left the skill unopened in most tasks, and opened it mostly on harder
ones. The split depends on the agent's own choice, so it describes when the
skill was used rather than its effect. p-values are from a sign-flip test over
the tasks in each row.

### Skill content against an unrelated skill

Each round-1 organizing skill scored slightly below the unrelated skill of
similar length. Three of the 6 contrasts had unadjusted p below 0.05, and none
after Holm correction across the 6 (smallest 0.07). The unrelated skill was
itself +0.99 and +0.71 points above the no-skill
run, which is not significant. This is weak evidence that organizing
instructions do slightly worse than unrelated text, not evidence that they
harm the agent compared with no skill.

| Skill | Model | Difference | 95% interval | p |
| --- | --- | ---: | :---: | ---: |
| file-organizer (ComposioHQ) | Haiku 5.5 | −1.51 | [−2.68, −0.41] | 0.01 |
| file-organizer (ComposioHQ) | Sonnet 5.5 | −1.04 | [−2.17, +0.11] | 0.07 |
| File Organizer (claude-office-skills) | Haiku 5.5 | −0.18 | [−1.50, +1.10] | 0.79 |
| File Organizer (claude-office-skills) | Sonnet 5.5 | −1.00 | [−2.31, +0.27] | 0.13 |
| invoice-organizer (ComposioHQ) | Haiku 5.5 | −1.24 | [−2.39, −0.14] | 0.03 |
| invoice-organizer (ComposioHQ) | Sonnet 5.5 | −1.54 | [−2.82, −0.28] | 0.02 |

### Cost

A skill is a few thousand tokens of text, but the agent re-reads it on every
model call. Tokens read are the input tokens the provider reported for a task,
including cache writes and cache reads. Costs use Anthropic's
[API prices](https://platform.claude.com/docs/en/about-claude/pricing) on
12 November 2026: $0.10 per million input tokens for Claude Haiku 5.5 (its
tier for prompts up to 100,000 tokens), $2 for Claude Sonnet 5.5 and $1 for
Claude Haiku 4.5. Cache writes cost 1.25×, output 5× and cache reads 0.1× the
input price, or 0.05× for Sonnet 5.5. The runs went through the GitHub Copilot
backend, so these are API-equivalent costs rather than what the study paid.
Haiku 5.5's other price tier has the same ratios, so the changes do not depend
on the tier.

| Condition | Model | Tokens read per task | Change | API cost per task | Change | 95% interval |
| --- | --- | ---: | ---: | ---: | ---: | :---: |
| No skill | Haiku 5.5 | 120.8k | — | $0.0112 | — | — |
| file-organizer (ComposioHQ) | Haiku 5.5 | 146.5k | +21.2% | $0.0122 | +8.5% | [+6.8%, +10.4%] |
| invoice-organizer (ComposioHQ) | Haiku 5.5 | 149.1k | +23.4% | $0.0119 | +6.4% | [+4.6%, +8.3%] |
| File Organizer (claude-office-skills) | Haiku 5.5 | 139.3k | +15.3% | $0.0121 | +7.7% | [+5.6%, +9.8%] |
| file-organizer (ComposioHQ), offered only | Haiku 5.5 | 139.4k | +15.4% | $0.0118 | +5.1% | [+3.4%, +6.9%] |
| mcp-builder (unrelated) | Haiku 5.5 | 146.4k | +21.1% | $0.0120 | +6.9% | [+5.1%, +8.8%] |
| No skill, round 2 | Haiku 5.5 | 120.0k | — | $0.0109 | — | — |
| Invoice Organizer (claude-office-skills) | Haiku 5.5 | 142.7k | +18.9% | $0.0118 | +8.3% | [+6.3%, +10.4%] |
| Email Classifier (claude-office-skills) | Haiku 5.5 | 138.6k | +15.6% | $0.0118 | +8.3% | [+6.2%, +10.4%] |
| No skill | Sonnet 5.5 | 102.5k | — | $0.1535 | — | — |
| file-organizer (ComposioHQ) | Sonnet 5.5 | 136.1k | +32.7% | $0.1639 | +6.7% | [+4.9%, +8.6%] |
| invoice-organizer (ComposioHQ) | Sonnet 5.5 | 138.9k | +35.5% | $0.1659 | +8.0% | [+6.4%, +9.7%] |
| File Organizer (claude-office-skills) | Sonnet 5.5 | 126.8k | +23.7% | $0.1601 | +4.3% | [+2.5%, +6.2%] |
| file-organizer (ComposioHQ), offered only | Sonnet 5.5 | 113.6k | +10.8% | $0.1503 | −2.1% | [−4.2%, −0.2%] |
| mcp-builder (unrelated) | Sonnet 5.5 | 145.7k | +42.2% | $0.1626 | +5.9% | [+3.8%, +7.9%] |
| No skill, round 2 | Sonnet 5.5 | 100.0k | — | $0.1518 | — | — |
| Invoice Organizer (claude-office-skills) | Sonnet 5.5 | 137.7k | +37.7% | $0.1623 | +6.9% | [+5.0%, +8.9%] |
| Email Classifier (claude-office-skills) | Sonnet 5.5 | 128.9k | +28.9% | $0.1611 | +6.1% | [+4.3%, +7.9%] |
| No skill | Haiku 4.5 | 217.9k | — | $0.0943 | — | — |
| file-organizer (ComposioHQ) | Haiku 4.5 | 256.2k | +17.6% | $0.0933 | −1.0% | [−5.8%, +3.8%] |
| File Organizer (claude-office-skills) | Haiku 4.5 | 222.7k | +2.2% | $0.0949 | +0.6% | [−4.3%, +5.8%] |

With a pinned organizing skill, Haiku 5.5 and Sonnet 5.5 read 15% to
38% more tokens per task. Most of them came from the prompt cache, so the
API cost rose by 4.3% to 8.5%, about as much as with the unrelated
skill. For a run of all 150 tasks that is $0.99 to $1.85
more with Sonnet 5.5 and $0.11 to $0.14 more with Haiku 5.5. Output tokens
changed by −0.7% to +7.8%, model turns by −5.5% to +4.3% and time per
task by −1.5% to +5.9%, with up to 12 episodes running at once. Claude Haiku 4.5
makes about twice as many model calls per task; its cost changed by
−1.0% and +0.6%, within run-to-run variation. When the skill was only
offered, the cost changed by +5.1% for Haiku 5.5 and −2.1% for Sonnet 5.5, which
opened the skill in only 14 tasks.

### What the skills changed

- **Exposure.** Every pinned episode contained the skill text, 150 of 150 in
  each condition. When the skill was only offered, Haiku 5.5 opened it in
  60 tasks and Sonnet 5.5 in 14.
- **Procedure.** In round 1, the pinned organizing skills left the episodes almost
  unchanged: 57.4 to 59.3 tool calls on average (58.2 and 58.8 without a
  skill), 5.6 to 6.7 model turns (6.0 and 6.6) and output tokens within 6%.
- **Tree shape.** Every round-1 output had 2 levels, as the task
  instruction asks, with 14.7 to 16.1 folders and 3.5 to 4.4 top-level groups
  on average.
- **Folder names.** The ComposioHQ file organizer raised Sonnet 5.5's share of
  lowercase-hyphen folder names from 0.46 to 0.84. The
  claude-office-skills File Organizer and the ComposioHQ invoice organizer
  lowered Haiku 5.5's share from 0.94 to 0.80 and 0.78. Folder names do not
  affect the score.
- **Groupings.** Outputs with a skill grouped the records differently from
  the no-skill run on most tasks, by about as much as an unrelated skill or a
  second run without any skill. The table gives the mean adjusted Rand index
  (ARI) between the 2 outputs' partitions of the records, where 1 means the
  same grouping. This comparison is exploratory, without intervals.

| Outputs compared | Haiku 5.5 leaf | Haiku 5.5 parent | Sonnet 5.5 leaf | Sonnet 5.5 parent |
| --- | ---: | ---: | ---: | ---: |
| No skill: same-day run vs the paper's run | 0.70 | 0.60 | 0.78 | 0.68 |
| Unrelated skill vs no skill | 0.75 | 0.64 | 0.80 | 0.70 |
| Organizing skills vs no skill (range of 3) | 0.74–0.75 | 0.63–0.64 | 0.81–0.82 | 0.71–0.72 |

Each row averages 150 tasks, except that the paper's trees cover 148 Sonnet
5.5 tasks.

### Where, if anywhere, do skills help?

An exploratory error analysis split the tasks by family, by difficulty (from
the paper's run of the same model, not from the no-skill run), and by the
number of parent groups, leaf groups and records, giving 28 task strata. A
stratum counted as helped only if a skill beat the no-skill run there after
Holm correction across all 168 cells (3 round-1 skills × 2 models × 28
strata), also helped the other model and also beat the unrelated skill.

- **No stratum qualified.** Without the last 2 conditions, no cell is
  significant after Holm correction either (smallest adjusted p 0.63). Each
  apparent gain on a subset reversed for the other model or appeared as well
  with the unrelated skill or a second run without any skill.
- **Sensitivity.** With a per-task standard deviation near 7.5 points, 80%
  power after correction needs a gain of about 11.8 points in a stratum of 8
  tasks, 6.0 points for 31 tasks and 4.7 points for a family of 50. Gains of 1
  to 5 points on subsets would usually go undetected.
- **No task-specific effect.** If a skill helped particular tasks, its
  per-task differences for the 2 models would correlate. Over 150 tasks the
  correlations were −0.09, −0.02 and −0.06 for the 3 pinned skills, against
  −0.09 for the unrelated skill.
- **Error modes unchanged.** Without a skill, 90% (Haiku 5.5) and 77% (Sonnet
  5.5) of top-level Recap folders mix sentences from different meetings. The
  skills changed these shares by at most 2 points, as did the unrelated skill.
- **A possible small cost on Recap.** All 6 round-1 pinned skill and model
  pairs scored below the no-skill run on Recap, by 0.2 to 2.8 points, and all
  4 round-2 pairs did again, by 0.9 to 1.8 points. Averaged per task, the
  differences were −1.25 (95% interval [−2.39, −0.14]) in round 1 and −1.44
  ([−3.04, +0.20]) in round 2. Both tests were chosen after seeing the family
  means, and Claude Haiku 4.5 moved the other way on Recap (+0.67 and +1.78).
  This is a hypothesis for repeated runs, not a finding.

### Run-to-run variation

The same-day no-skill runs can be compared with the paper's Deep Agents runs of
the same models, which used an earlier transport and a 120-second request
timeout. They scored lower by 1.68 points for Haiku 5.5 (95% interval
[−2.98, −0.48]), 0.53 for Sonnet 5.5 ([−1.77, +0.74]) and
2.27 for Haiku 4.5 ([−3.70, −0.85]). For Haiku, this gap is larger than
any skill effect measured here, which is why every skill is compared with a
same-day run rather than with the paper's numbers. The 2 same-day no-skill
runs agree closely: round 2 differs from round 1 by
+0.29 (Haiku 5.5) and −0.01 (Sonnet 5.5).

## Why the skills do not help here

The skills give general file-management procedure: folder templates by type,
project, vendor or date, naming rules, duplicate handling and asking before
moving files. InfoOrgBench is hard for a different reason. The agent must work
out which meeting, parent issue or owning group each record came from, and
none of the skills addresses that. The agents adopted the skills' naming rules
and otherwise organized as before.

## Limitations

- Each task ran once per condition, so a per-task difference mixes the skill's
  effect with run-to-run variation.
- The conclusions are about these 150 tasks. Thread and Design tasks share
  source material: all 50 Thread tasks draw on 3 parent issues, and the Design
  tasks share 16 SIGs. Resampling tasks treats them as independent, so the
  intervals are approximate and do not support generalizing to new sources.
- No equivalence margin was set in advance. The result is the absence of a
  detectable average effect, not proof that there is none.
- The study covers 1 harness, Claude models only and 1 transport. Pinned mode
  stands in for a user invoking the skill; when the skill was only offered,
  the agent mostly did not open it.
- The skills were chosen by install counts on 1 date. Installs measure
  adoption, not quality, and the 2 round-2 skills are specialized to invoices
  and email.

## Related work

These results agree with other paired evaluations of public skills.
SWE-Skills-Bench ([arXiv:2603.15401](https://arxiv.org/abs/2603.15401)) found
no significant effect for 92 of 98 public software-engineering skills.
WebDev-Skills-Bench ([arXiv:2608.23067](https://arxiv.org/abs/2608.23067))
found that target skills lowered Pass@2 by 1.3% to 4.2%, and that for some
models a length-matched irrelevant skill reproduced most of the loss.
SkillsBench ([arXiv:2602.12670](https://arxiv.org/abs/2602.12670)) reported
large gains, but from curated skills written for its tasks rather than from
general community skills.

## Try your own skill

Install the harness and Deep Agents as in [step 6 of the quick start](../README.md#6-rerun-a-system-from-the-paper)
and the [harness guide](../harness/README.md#deep-agents). Then run one family
with and without a skill, and compare the scores:

```bash
python -m infoorgbench_harness fetch-skills --out ../skills
python -m infoorgbench_harness run --harness deepagents --model claude-sonnet-5.5 --backend copilot --family Recap --out ../runs/no-skill
python -m infoorgbench_harness run --harness deepagents --model claude-sonnet-5.5 --backend copilot --family Recap --skill ../skills/composio-file-organizer/file-organizer --skill-mode pinned --out ../runs/with-skill
python -m infoorgbench_harness score --run ../runs/no-skill
python -m infoorgbench_harness score --run ../runs/with-skill
```

Single tasks vary by several points between runs, so compare whole families.

### Use your own skill

A skill is a folder that contains a `SKILL.md`:

```text
my-skill/
└── SKILL.md
```

```markdown
---
name: my-skill
description: Organize records by the meeting, issue or project they came from.
---

Read every record before creating any folder. Note the source each record
names, then build one top-level folder per source.
```

Pass the folder with `--skill ../my-skill`, and repeat `--skill` to load
several. `--skill-mode pinned` loads the skill before the agent starts;
`--skill-mode available` only lists it, and the agent decides. The
[harness guide](../harness/README.md#agent-skills-with-deep-agents-and-codex)
explains both modes.

## Reproduce

Install the harness and Deep Agents as described in the
[harness guide](../harness/README.md#deep-agents). From the repository root:

```bash
python -m infoorgbench_harness fetch-skills --out .local/community-skills
python tools/skill_study.py run --out .local/skill-study
python tools/skill_study.py run --out .local/skill-study --conditions available-composio-file-organizer pinned-irrelevant-mcp-builder
python tools/skill_study.py run --out .local/skill-study --conditions control-r2 pinned-office-invoice-organizer pinned-office-email-classifier
python tools/skill_study.py run --out .local/skill-study --models claude-haiku-4.5 --conditions control pinned-composio-file-organizer pinned-claude-office-file-organizer
python tools/skill_study.py analyze --out .local/skill-study
python tools/skill_study.py similarity --out .local/skill-study
python tools/skill_study.py cost --out .local/skill-study
python tools/skill_study_errors.py --out .local/skill-study
```

A rerun draws new samples, so its scores will differ somewhat. The saved runs
themselves (workspaces, logs and receipts) are not distributed.

| File | Contents |
| --- | --- |
| [summary.json](../results/agent-skills/summary.json) | Family and average scores for each condition and model, paired differences with intervals and p-values, and the comparison with the paper's runs |
| [per-task.csv](../results/agent-skills/per-task.csv) | One row per condition, model and task (3,150 rows): score, validity, records left in the inbox, tool calls, model turns, skill reads, tokens and seconds |
| [cost.json](../results/agent-skills/cost.json) | Tokens, API cost, model turns and time per task for each condition, with each skill's change and its interval |
| [folder-naming.json](../results/agent-skills/folder-naming.json) | Folder-name styles for each round-1 condition |
| [grouping-similarity.json](../results/agent-skills/grouping-similarity.json) | Adjusted Rand index between each round-1 condition's groupings and those of the no-skill run |
