# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Build the README figures in docs/assets.

    python docs/assets/build_readme_assets.py

Every figure is written as a light and a dark SVG. The family examples come
from the reference hierarchies in benchmark/inputs/reference; the results and
error figures use the paper's numbers in docs/assets/paper-results.json.
Standard library only.
"""

from __future__ import annotations

import json
import statistics
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BENCH = ROOT / "benchmark"
PAPER = json.loads((OUT / "paper-results.json").read_text(encoding="utf-8"))

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "light": {
        "panel": "#f6f8fa", "card": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
        "faint": "#eaeef2", "brand": "#0969da", "brand2": "#8250df", "grad_a": "#eef4ff", "grad_b": "#f6f0ff",
        "good": "#1a7f37", "bad": "#cf222e", "base": "#8c959f", "range": "#24292f",
        "good_bg": "#dafbe1", "bad_bg": "#ffebe9", "visible": "#eef4fb", "hidden": "#fdf4e4", "hidden_ink": "#9a6700",
        "highlight": "#dbe7f7", "Recap": "#0e8a7e", "Thread": "#c4510b", "Design": "#7048e8",
    },
    "dark": {
        "panel": "#151b23", "card": "#0d1117", "border": "#3d444d", "text": "#f0f6fc", "muted": "#9198a1",
        "faint": "#262c36", "brand": "#4493f8", "brand2": "#ab7df8", "grad_a": "#0f1b33", "grad_b": "#1c1533",
        "good": "#3fb950", "bad": "#f85149", "base": "#656c76", "range": "#e6edf3",
        "good_bg": "#12301c", "bad_bg": "#3a1518", "visible": "#0f1a2b", "hidden": "#261d0e", "hidden_ink": "#d29922",
        "highlight": "#1b2c47", "Recap": "#2dd4bf", "Thread": "#ff922b", "Design": "#b197fc",
    },
}
FAMILIES = ("Recap", "Thread", "Design")


def text(x, y, value, size=18, fill="#000", weight=400, anchor="start", family=SANS, extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(str(value))}</text>')


def rect(x, y, w, h, fill="none", stroke="none", rx=0, width=1, extra=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"{extra}/>')


def arrow(x1, y1, x2, y2, color, width=2.5):
    """Straight arrow with an open head at (x2, y2)."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / length, dy / length
    hx, hy = x2 - 10 * ux, y2 - 10 * uy
    return (f'<path d="M{x1} {y1} L{x2} {y2} M{hx - 6 * uy:.1f} {hy + 6 * ux:.1f} L{x2} {y2} L{hx + 6 * uy:.1f} {hy - 6 * ux:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def folder(x, y, color):
    return f'<path d="M{x} {y - 13} h8 l3 3 h11 v12 h-22 z" fill="{color}"/>'


def check(x, y, color, ok=True, r=10):
    mark = (f'<path d="M{x - 5} {y} l3.5 3.5 l7 -7.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
            if ok else f'<path d="M{x - 4} {y - 4} l8 8 m0 -8 l-8 8" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>')
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>' + mark


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">\n'
            f'<title>{escape(title)}</title>\n' + "\n".join(body) + "\n</svg>\n")


# ---------------------------------------------------------------- banner

def banner(t):
    W, H = 1280, 300
    b = [
        "<defs>",
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["grad_a"]}"/>'
        f'<stop offset="1" stop-color="{t["grad_b"]}"/></linearGradient>',
        f'<linearGradient id="word" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["brand"]}"/>'
        f'<stop offset="1" stop-color="{t["brand2"]}"/></linearGradient>',
        "</defs>",
        rect(1, 1, W - 2, H - 2, "url(#bg)", t["border"], 18, 1.5),
    ]
    cloud = [(62, 92, -12, "Recap"), (104, 70, 9, "Design"), (146, 104, -6, "Thread"), (70, 142, 14, "Thread"),
             (116, 150, -10, "Recap"), (160, 160, 7, "Design"), (60, 196, -7, "Design"), (108, 212, 12, "Thread"),
             (154, 214, -15, "Recap")]
    for x, y, angle, fam in cloud:
        b.append(rect(x - 13, y - 9, 26, 18, t[fam], "none", 4, extra=f' transform="rotate({angle} {x} {y})" opacity="0.92"'))
    b.append(arrow(198, 150, 236, 150, t["muted"], 4))
    b.append(f'<circle cx="262" cy="150" r="13" fill="{t["brand"]}"/>')
    for gy, fam in zip((86, 150, 214), FAMILIES):
        b.append(f'<path d="M275 150 H292 V{gy} H312" fill="none" stroke="{t["muted"]}" stroke-width="3"/>')
        b.append(rect(312, gy - 12, 24, 24, t["card"], t[fam], 6, 3))
        b.append(f'<path d="M336 {gy} H350" stroke="{t["muted"]}" stroke-width="3"/>')
        for k in range(3):
            b.append(rect(352 + k * 30, gy - 9, 26, 18, t[fam], "none", 4))
    b.append(f'<text x="470" y="150" font-family="{SANS}" font-size="88" font-weight="800" letter-spacing="-2" '
             f'fill="{t["text"]}">Info<tspan fill="url(#word)">Org</tspan>Bench</text>')
    b.append(text(472, 196, "Can agents turn scattered information into coherent hierarchies?", 25, t["muted"], 500))
    x = 472
    for label in ("150 tasks", "3 task families", "45 agent systems", "No LLM judge"):
        w = int(len(label) * 17 * 0.58) + 30
        b.append(rect(x, 222, w, 34, t["card"], t["border"], 17, 1.2))
        b.append(text(x + w / 2, 245, label, 17, t["text"], 600, "middle"))
        x += w + 12
    return svg(W, H, b, "InfoOrgBench: Can agents turn scattered information into coherent hierarchies?")


# ---------------------------------------------------------------- overview (paper Figure 1)

def overview(t):
    W, H = 1280, 610
    b = [rect(16, 16, 760, 578, t["visible"], "none", 16), rect(796, 16, 468, 578, t["hidden"], "none", 16),
         f'<path d="M786 24 V586" stroke="{t["muted"]}" stroke-width="2" stroke-dasharray="6 6"/>']
    # Panel headers: an eye for what the agent sees, a lock for what only the evaluator sees.
    b.append(f'<path d="M34 46 q10 -10 20 0 q-10 10 -20 0 z" fill="none" stroke="{t["muted"]}" stroke-width="2"/>'
             f'<circle cx="44" cy="46" r="3.5" fill="{t["muted"]}"/>')
    b.append(text(64, 52, "Visible to the agent", 17, t["muted"], 500))
    b.append(rect(816, 44, 16, 12, t["hidden_ink"], "none", 2) +
             f'<path d="M819 44 v-4 a5 5 0 0 1 10 0 v4" fill="none" stroke="{t["hidden_ink"]}" stroke-width="2"/>')
    b.append(text(842, 54, "Evaluator only", 17, t["hidden_ink"], 600))
    for x, num, title in ((44, "1", "Task input"), (468, "2", "Agent execution"), (824, "3", "Evaluation")):
        b.append(f'<circle cx="{x}" cy="88" r="13" fill="{t["text"]}"/>')
        b.append(text(x, 94, num, 16, t["card"], 700, "middle"))
        b.append(text(x + 22, 96, title, 22, t["text"], 700))

    # 1. Task input
    b.append(rect(32, 112, 400, 150, t["card"], t["border"], 10, 1.2))
    b.append(text(50, 140, "Task families", 18, t["text"], 700))
    b.append(rect(40, 216, 384, 30, t["highlight"], "none", 6))
    for y, (fam, mapping, source) in zip((172, 202, 237), (("Recap", "Meeting → Section", "AMI"),
                                                          ("Thread", "Issue → Subtask", "Jira"),
                                                          ("Design", "SIG → KEP", "Kubernetes"))):
        b.append(text(50, y, fam, 17, t[fam], 700))
        b.append(text(134, y, mapping, 16, t["text"], 400, family=MONO))
        b.append(text(414, y, source, 15, t["muted"], 400, "end"))
    b.append(rect(32, 278, 400, 300, t["card"], t["border"], 10, 1.2))
    b.append(folder(50, 312, t["muted"]))
    b.append(text(80, 312, "inbox/", 17, t["text"], 700, family=MONO))
    b.append(text(146, 312, "(Design)", 15, t["muted"]))
    quotes = [("F004", "extend ConfigMap and Secret", "with an immutable field"),
              ("F023", "immutable Secrets protect", "against accidental updates"),
              ("F006", "validate VolumeSnapshot and", "VolumeSnapshotContent"),
              ("F017", "allow StatefulSet rolling", "updates with maxUnavailable")]
    for i, (rid, line1, line2) in enumerate(quotes):
        y = 348 + i * 54
        b.append(f'<path d="M54 {y - 13} h10 l5 5 v13 h-15 z" fill="none" stroke="{t["muted"]}" stroke-width="1.6"/>')
        b.append(text(78, y, rid, 16, t["text"], 700, family=MONO))
        b.append(text(134, y, f"“{line1}", 15, t["text"], 400, extra=' font-style="italic"'))
        b.append(text(134, y + 20, f"{line2}”", 15, t["text"], 400, extra=' font-style="italic"'))
    b.append(text(78, 562, "…", 18, t["muted"], 700))

    # 2. Agent execution
    b.append(rect(456, 112, 304, 150, t["card"], t["border"], 10, 1.2))
    b.append(folder(474, 140, t["muted"]))
    b.append(text(504, 140, "Workspace", 18, t["text"], 700))
    for y, name in zip((176, 204, 232), ("inbox/", "apps/", "storage/")):
        b.append(text(480, y, name, 16, t["text"], 400, family=MONO))
    b.append(arrow(520, 272, 520, 322, t["muted"]))
    b.append(text(534, 292, "observe", 16, t["text"], 700))
    b.append(text(534, 312, "read files", 15, t["muted"]))
    b.append(arrow(660, 322, 660, 272, t["muted"]))
    b.append(text(674, 292, "act", 16, t["text"], 700))
    b.append(text(674, 312, "move files", 15, t["muted"]))
    b.append(rect(456, 330, 304, 248, t["card"], t["border"], 10, 1.2))
    b.append(text(476, 360, "Agent", 18, t["text"], 700))
    b.append(text(476, 388, "9 models × 5 harnesses", 16, t["muted"]))
    for i, name in enumerate(("Claude", "GPT", "Grok", "MAI")):
        b.append(f'<circle cx="484" cy="{419 + i * 32}" r="5" fill="{t["brand"]}"/>')
        b.append(text(496, 425 + i * 32, name, 16, t["text"]))
    for i, name in enumerate(("Codex", "DSH", "Pi", "Deep Agents", "ReAct-FC")):
        b.append(f'<circle cx="604" cy="{419 + i * 32}" r="5" fill="{t["brand2"]}"/>')
        b.append(text(616, 425 + i * 32, name, 16, t["text"]))
    b.append(arrow(434, 187, 452, 187, t["muted"]))
    b.append(arrow(434, 440, 452, 440, t["muted"]))
    b.append(arrow(762, 160, 808, 160, t["hidden_ink"], 3))

    # 3. Evaluation: output vs hidden reference
    b.append(rect(812, 112, 216, 252, t["card"], t["border"], 10, 1.2))
    b.append(text(828, 140, "Agent output", 17, t["text"], 700))
    b.append(rect(818, 184, 204, 46, t["bad_bg"], "none", 5))
    rows = [(172, "apps/", t["bad"], 700), (200, "├ immutable/", t["text"], 400), (224, "│   F004 F023", t["text"], 400),
            (250, "└ sts-rollout/", t["text"], 400), (274, "    F017", t["text"], 400), (302, "storage/", t["text"], 700),
            (326, "└ snapshot/", t["text"], 400), (350, "    F006", t["text"], 400)]
    for y, label, color, weight in rows:
        b.append(text(828, y, label, 15, color, weight, family=MONO, extra=' xml:space="preserve"'))
    b.append(check(896, 166, t["bad"], ok=False, r=8))
    b.append(text(910, 171, "wrong SIG", 14, t["bad"], 600))
    b.append(check(958, 195, t["good"], ok=True, r=8))
    b.append(rect(1036, 112, 216, 252, t["card"], t["hidden_ink"], 10, 1.5, ' stroke-dasharray="6 5"'))
    b.append(text(1052, 140, "Hidden reference", 17, t["text"], 700))
    b.append(rect(1042, 258, 204, 46, t["good_bg"], "none", 5))
    rows = [(172, "apps/", t["text"], 700), (196, "└ sts-rollout/", t["text"], 400), (220, "    F017", t["text"], 400),
            (246, "storage/", t["good"], 700), (274, "├ immutable/", t["text"], 400), (298, "│   F004 F023", t["text"], 400),
            (324, "└ snapshot/", t["text"], 400), (348, "    F006", t["text"], 400)]
    for y, label, color, weight in rows:
        b.append(text(1052, y, label, 15, color, weight, family=MONO, extra=' xml:space="preserve"'))
    b.append(arrow(920, 366, 920, 376, t["muted"]))
    b.append(arrow(1144, 366, 1144, 376, t["muted"]))
    b.append(rect(812, 380, 440, 198, t["card"], t["border"], 10, 1.2))
    b.append(text(830, 414, "Integrity:", 16, t["text"], 700))
    b.append(text(918, 414, "every record kept once and unchanged", 15, t["text"]))
    b.append(f'<text x="830" y="450" font-family="{SANS}" font-size="16" fill="{t["text"]}"><tspan font-weight="700">'
             f'Structure Score:</tspan> S = F<tspan font-size="11" dy="4">1</tspan><tspan font-size="11" dy="-12">bal</tspan>'
             f'<tspan dy="8">(parent, leaf) × E</tspan></text>')
    b.append(f'<path d="M830 470 H1234" stroke="{t["faint"]}" stroke-width="2"/>')
    b.append(check(840, 504, t["good"], ok=True))
    b.append(text(858, 510, "Leaf (KEP)", 16, t["good"], 700))
    b.append(text(984, 510, "F004 F023 | F006", 15, t["text"], 400, family=MONO))
    b.append(text(1236, 510, "agreed", 15, t["good"], 600, "end"))
    b.append(check(840, 546, t["bad"], ok=False))
    b.append(text(858, 552, "Parent (SIG)", 16, t["bad"], 700))
    b.append(text(984, 552, "F004 F006 | F017", 15, t["text"], 400, family=MONO))
    b.append(text(1236, 552, "conflict", 15, t["bad"], 600, "end"))
    return svg(W, H, b, "Overview: agents see an inbox of records and move them into folders; the evaluator compares the "
                        "final tree with a hidden source hierarchy at the parent and leaf levels.")


# ---------------------------------------------------------------- families

def family_examples():
    """Pick, per family, the first task whose largest parent group has at least three children."""
    examples = {}
    for fam in FAMILIES:
        for path in sorted((BENCH / "inputs" / "reference" / fam).glob("*.json")):
            ref = json.loads(path.read_text(encoding="utf-8"))
            tree: dict[str, dict[str, int]] = {}
            for record in ref["records"]:
                parent, child = record["path"][0], record["path"][1]
                tree.setdefault(parent, {}).setdefault(child, 0)
                tree[parent][child] += 1
            if max(len(children) for children in tree.values()) >= 3:
                examples[fam] = (ref.get("task_id", path.stem), tree)
                break
    return examples


def families(t):
    W, H = 1280, 400
    info = {
        "Recap": ("AMI Meeting Corpus", "meeting summaries", "Meeting", "summary section", "40-60"),
        "Thread": ("Apache Hadoop Jira", "issue threads", "Parent issue", "subtask", "41-60"),
        "Design": ("Kubernetes KEPs", "design proposals", "Owning SIG", "proposal", "36"),
    }
    examples = family_examples()
    b = [rect(1, 1, W - 2, H - 2, t["panel"], t["border"], 16, 1.2)]
    for i, fam in enumerate(FAMILIES):
        x = 24 + i * 418
        c = t[fam]
        src, kind, top, leaf, recs = info[fam]
        b.append(rect(x, 24, 396, 352, t["card"], t["border"], 12, 1.2))
        b.append(rect(x, 24, 396, 8, c, "none", 4))
        b.append(f'<text x="{x + 22}" y="72" font-family="{SANS}" font-size="19" font-weight="500" fill="{t["muted"]}">'
                 f'<tspan font-size="30" font-weight="800" fill="{c}">{fam}</tspan><tspan dx="12">{kind}</tspan></text>')
        b.append(text(x + 22, 104, f"Source: {src}", 18, t["text"], 500))
        b.append(text(x + 22, 130, f"Hierarchy: {top} > {leaf}", 18, t["text"], 500))
        b.append(text(x + 22, 156, f"50 tasks, {recs} records each", 18, t["text"], 500))
        b.append(f'<path d="M{x + 22} 174 H{x + 374}" stroke="{t["faint"]}" stroke-width="2"/>')
        task, tree = examples[fam]
        parent = sorted(tree, key=lambda p: (-len(tree[p]), p))[0]
        children = sorted(tree[parent].items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        b.append(text(x + 22, 202, f"Reference excerpt, {task}", 16, t["muted"], 500))
        b.append(rect(x + 22, 215, 18, 18, c, "none", 4))
        b.append(text(x + 50, 230, parent, 17, t["text"], 700, family=MONO))
        for k, (child, n) in enumerate(children):
            y = 266 + k * 30
            b.append(f'<path d="M{x + 31} {y - 32 if k == 0 else y - 30} V{y - 5} H{x + 50}" fill="none" stroke="{t["border"]}" stroke-width="2"/>')
            label = child if len(child) <= 21 else child[:20] + "..."
            b.append(rect(x + 52, y - 13, 14, 14, t["card"], c, 3, 2))
            b.append(text(x + 74, y - 1, label, 16, t["text"], 500, family=MONO))
            b.append(text(x + 374, y - 1, f"{n} record{'s' if n != 1 else ''}", 15, t["muted"], 400, "end"))
    return svg(W, H, b, "The three InfoOrgBench task families")


# ---------------------------------------------------------------- results (paper Tables 3, 11 and 12)

def result_rows():
    systems = PAPER["systems"]
    rows = []
    for model, mean in sorted(PAPER["model_means"].items(), key=lambda kv: -kv[1]):
        mine = [s for s in systems if s["model"] == model]
        cells = {}
        for fam in FAMILIES:
            scores = [s[fam]["score"] for s in mine]
            cells[fam] = (statistics.fmean(scores), min(scores), max(scores))
        avgs = [s["Avg"]["score"] for s in mine]
        cells["Avg"] = (mean, min(avgs), max(avgs))
        rows.append((model, cells, True))
    for name, label in (("Silhouette", "Silhouette clustering"), ("Random shape", "Random shape"), ("Fixed cuts", "Fixed distance cuts")):
        values = PAPER["baselines"][name]
        cells = {fam: (values[fam], None, None) for fam in FAMILIES}
        cells["Avg"] = (statistics.fmean(values[f] for f in FAMILIES), None, None)
        rows.append((label, cells, False))
    return rows


def results(t):
    rows = result_rows()
    W, H = 1280, 660
    label_end, col0, colw, barw = 236, 258, 250, 172
    top, row_h, gap = 112, 36, 40
    b = [rect(1, 1, W - 2, H - 2, t["panel"], t["border"], 16, 1.2)]
    b.append(text(28, 46, "Structure Score (0 to 100) of nine models and three baselines", 21, t["text"], 700))
    b.append(text(28, 72, "Each bar is a model's average over the five harnesses; the line runs from its lowest to its highest harness.", 16, t["muted"]))
    panels = list(FAMILIES) + ["Avg"]
    y_end = top + row_h * len(rows) + gap
    for j, name in enumerate(panels):
        cx = col0 + j * colw
        color = t[name] if name in FAMILIES else t["brand"]
        b.append(f'<circle cx="{cx + 8}" cy="{top - 18}" r="7" fill="{color}"/>')
        b.append(text(cx + 22, top - 12, "Average" if name == "Avg" else name, 18, t["text"], 700))
        for tick in (0, 50, 100):
            gx = cx + barw * tick / 100
            b.append(f'<path d="M{gx} {top} V{y_end - 6}" stroke="{t["faint"]}" stroke-width="1.5"/>')
            b.append(text(gx, y_end + 12, tick, 14, t["muted"], 400, "middle"))
    y = top
    for i, (label, cells, model) in enumerate(rows):
        if i == 9:
            b.append(f'<path d="M24 {y + 8} H{W - 24}" stroke="{t["border"]}" stroke-width="1.2" stroke-dasharray="4 5"/>')
            b.append(text(label_end, y + 30, "Baselines without a model", 15, t["muted"], 600, "end", extra=' font-style="italic"'))
            y += gap
        b.append(text(label_end, y + 23, label, 16, t["text"], 600 if model else 400, "end"))
        for j, name in enumerate(panels):
            cx = col0 + j * colw
            mean, low, high = cells[name]
            fill = (t[name] if name in FAMILIES else t["brand"]) if model else t["base"]
            b.append(rect(cx, y + 9, max(barw * mean / 100, 2), 20, fill, "none", 4, extra=' opacity="0.9"'))
            end = cx + barw * (high if high is not None else mean) / 100
            if low is not None:
                lx, hx = cx + barw * low / 100, end
                b.append(f'<path d="M{lx:.1f} {y + 19} H{hx:.1f} M{lx:.1f} {y + 13} V{y + 25} M{hx:.1f} {y + 13} V{y + 25}" '
                         f'stroke="{t["range"]}" stroke-width="1.8"/>')
            b.append(text(end + 6, y + 25, f"{mean:.1f}", 14, t["text"], 700))
        y += row_h
    b.append(text(28, H - 22, "Scores from the paper's Tables 3, 11 and 12. Each system ran once on each of the 150 tasks.", 15, t["muted"]))
    return svg(W, H, b, "Structure Score of nine models and three baselines without a language model on Recap, Thread and Design")


# ---------------------------------------------------------------- error rates by level (paper Figure 2)

def errors(t):
    data = PAPER["level_errors"]
    W, H = 1280, 430
    x_axis, y0, scale = 104, 330, 3.0  # 3 px per percentage point
    b = [rect(1, 1, W - 2, H - 2, t["panel"], t["border"], 16, 1.2)]
    b.append(text(28, 44, "Share of record relations placed wrong, at each level of the hierarchy", 21, t["text"], 700))
    b.append(text(28, 70, "Each bar is the median over systems with per-level data. In parentheses: the share of outputs with at least one error at that level.", 16, t["muted"]))
    for tick in range(0, 81, 20):
        y = y0 - tick * scale
        b.append(f'<path d="M{x_axis} {y} H1190" stroke="{t["faint"]}" stroke-width="1.5"/>')
        b.append(text(x_axis - 10, y + 5, f"{tick}%", 14, t["muted"], 400, "end"))
    for i, fam in enumerate(FAMILIES):
        center = 300 + i * 340
        for j, level in enumerate(("parent", "leaf")):
            cell = data[fam][level]
            x = center + (j - 0.5) * 112 - 48
            conflicting, unresolved = 100 * cell["conflicting"], 100 * cell["unresolved"]
            b.append(rect(x, y0 - conflicting * scale, 96, conflicting * scale, t["bad"], "none", 0))
            b.append(rect(x, y0 - (conflicting + unresolved) * scale, 96, unresolved * scale, t["base"], "none", 0))
            top = y0 - (conflicting + unresolved) * scale
            b.append(text(x + 48, top - 8, f"{conflicting + unresolved:.0f}%", 18, t["text"], 700, "middle"))
            b.append(text(x + 48, top - 30, f"({100 * cell['any_error']:.0f}%)", 14, t["muted"], 400, "middle"))
            b.append(text(x + 48, y0 + 24, level, 15, t["text"], 500, "middle"))
            b.append(text(x + 48, y0 + 43, cell["name"], 15, t["muted"], 400, "middle"))
        b.append(text(center, y0 + 76, fam, 19, t[fam], 800, "middle"))
    for k, (color, label) in enumerate(((t["bad"], "conflicting: a different pair is grouped together"),
                                        (t["base"], "unresolved: the three records are not separated"))):
        b.append(rect(820, 104 + k * 28, 16, 16, color, "none", 3))
        b.append(text(844, 117 + k * 28, label, 15, t["text"]))
    return svg(W, H, b, "Parent-level error rates exceed leaf-level error rates in every family")


def main():
    figures = {"banner": banner, "overview": overview, "families": families, "results": results, "errors": errors}
    for name, build in figures.items():
        for theme, palette in THEMES.items():
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(build(palette), encoding="utf-8", newline="\n")
            print(path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
