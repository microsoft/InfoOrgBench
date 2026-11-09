# Prompt v2

This directory defines the model-visible semantic task message independently of
model, reasoning effort, budget and harness-native instructions.

## Layers

1. Harness adapter context is owned by the pinned harness. For ReAct-FC, see
   `runtime/h0_system.txt`.
2. `protocol.v2.md` fixes the workspace, integrity, evidence, injection,
   forced-choice and finish rules. Development-only prompt revisions use a new
   protocol version rather than changing frozen v2 bytes.
3. `family-*.md` fixes the hierarchy and placement criterion for one source
   family. A family criterion must match the rule used to construct its
   evaluator reference.
4. `runtime/prompt_v2.py` fills public collection slots: workspace/checker
   paths, record counts and supplied meeting anchors.

For one collection, the canonical rendered message is invariant across models,
harnesses and repetitions. Real workspace/checker paths may differ, so manifests
also store a canonical hash rendered with placeholders.

## Main-condition decisions

- Every record, including meeting transcripts, starts in `inbox`.
- The task message does not disclose numeric time, turn or token budgets.
- Final JSON is requested but no provider-specific strict output schema is
  sent. The declaration is diagnostic; independently captured files are the
  result.
- Agents must read long records in parts when a tool truncates output.
- A meeting that only recaps or mentions another meeting's content is not
  positive support for placement.
- The legacy `task` string in older public packets is retained for provenance
  but is not sent.

Preplaced meeting anchors, evidence ablation and incremental arrival require
separate declared conditions and runner support. They must not silently alter
the main prompt.

The design family is a control. The meeting family remains under reference
validation, and the issue-family rule remains a candidate until lawful complete
issue packets and their reference protocol are admitted.

`protocol.v2.1.md` and `family-design-sections.v1.md` are restricted to the
three-task Kubernetes Hard development pilot. V2.1 changes only the complete
reading rule: agents read enough evidence to justify placement and continue a
shortened output only when needed. The section family receives complete,
bounded semantic excerpts and no metadata records. Neither artifact changes the
v2 main condition or admits a final benchmark track.

The first pilot is permanently bound to v2.1. After reviewing its wording, the
author replaced it prospectively with `protocol.v2.2.md`. V2.2 simply deletes
the complete-reading instruction; it adds no advice about how much to read or
when to continue. Future generated Kubernetes Hard development manifests name
v2.2. Existing v2.1 results are not relabeled.

`family-summary.v1.md` (`meeting | section`, no anchors) is the AMI Mini v1
family. Mini v1 AMI packets contain meeting-summary sentences without transcript
records or public anchors, so `meeting.v1` cannot render them. The author
admitted `summary.v1` for Mini v1 AMI on 11 October 2026. The file keeps its
original bytes, including the `status` header, so its SHA-256
(`9ee844b82540d0f56acace23e95ed0658c866ee1a478aa60d2b63e3a709062f3`) matches
the prompt hash recorded by the exploratory GPT-6.1 Sol Mini run described in
[CODEX-SOL-MINI-RUN.md](../../docs/CODEX-SOL-MINI-RUN.md).

## Freeze rule

Freeze the protocol, family files and renderer hashes before held-out inference.
Prompt changes may be developed on development packets only and cannot be
selected based on held-out model scores.
