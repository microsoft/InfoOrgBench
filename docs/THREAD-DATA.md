# Building the Thread tasks

The 50 Thread tasks use issue, subtask and comment text from the public
[Apache Hadoop issue tracker](https://issues.apache.org/jira/projects/HADOOP).
That text belongs to its authors and is **not included** in this repository.
The repository provides the references (record IDs, Jira issue and comment IDs
and SHA-256 hashes), the list of issues below and a tool that rebuilds each
Thread packet exactly.

## 1. Download the 42 issues

Open each **JSON** link below in a web browser and save the page as the file
name shown, all in one folder. Each link is the issue's public REST response
with the fields the tasks use.

Apache's [robots.txt](https://issues.apache.org/robots.txt) asks operators of
automated clients to contact root@apache.org before crawling. Download the
files by hand, or obtain Apache's permission before scripting the downloads.
Use of the text is subject to the terms that apply on Apache Jira.

| # | Issue | Download | Save as |
|---|---|---|---|
| 1 | [HADOOP-13585](https://issues.apache.org/jira/browse/HADOOP-13585) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-13585?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-13585.json` |
| 2 | [HADOOP-14639](https://issues.apache.org/jira/browse/HADOOP-14639) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-14639?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-14639.json` |
| 3 | [HADOOP-14707](https://issues.apache.org/jira/browse/HADOOP-14707) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-14707?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-14707.json` |
| 4 | [HADOOP-15245](https://issues.apache.org/jira/browse/HADOOP-15245) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-15245?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-15245.json` |
| 5 | [HADOOP-15570](https://issues.apache.org/jira/browse/HADOOP-15570) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-15570?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-15570.json` |
| 6 | [HADOOP-15631](https://issues.apache.org/jira/browse/HADOOP-15631) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-15631?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-15631.json` |
| 7 | [HADOOP-15825](https://issues.apache.org/jira/browse/HADOOP-15825) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-15825?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-15825.json` |
| 8 | [HADOOP-16155](https://issues.apache.org/jira/browse/HADOOP-16155) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16155?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16155.json` |
| 9 | [HADOOP-16163](https://issues.apache.org/jira/browse/HADOOP-16163) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16163?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16163.json` |
| 10 | [HADOOP-16317](https://issues.apache.org/jira/browse/HADOOP-16317) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16317?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16317.json` |
| 11 | [HADOOP-16404](https://issues.apache.org/jira/browse/HADOOP-16404) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16404?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16404.json` |
| 12 | [HADOOP-16498](https://issues.apache.org/jira/browse/HADOOP-16498) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16498?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16498.json` |
| 13 | [HADOOP-16574](https://issues.apache.org/jira/browse/HADOOP-16574) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16574?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16574.json` |
| 14 | [HADOOP-16631](https://issues.apache.org/jira/browse/HADOOP-16631) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16631?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16631.json` |
| 15 | [HADOOP-16659](https://issues.apache.org/jira/browse/HADOOP-16659) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16659?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16659.json` |
| 16 | [HADOOP-16699](https://issues.apache.org/jira/browse/HADOOP-16699) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16699?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16699.json` |
| 17 | [HADOOP-16778](https://issues.apache.org/jira/browse/HADOOP-16778) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16778?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16778.json` |
| 18 | [HADOOP-16859](https://issues.apache.org/jira/browse/HADOOP-16859) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-16859?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-16859.json` |
| 19 | [HADOOP-17002](https://issues.apache.org/jira/browse/HADOOP-17002) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17002?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17002.json` |
| 20 | [HADOOP-17017](https://issues.apache.org/jira/browse/HADOOP-17017) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17017?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17017.json` |
| 21 | [HADOOP-17054](https://issues.apache.org/jira/browse/HADOOP-17054) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17054?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17054.json` |
| 22 | [HADOOP-17093](https://issues.apache.org/jira/browse/HADOOP-17093) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17093?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17093.json` |
| 23 | [HADOOP-17149](https://issues.apache.org/jira/browse/HADOOP-17149) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17149?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17149.json` |
| 24 | [HADOOP-17163](https://issues.apache.org/jira/browse/HADOOP-17163) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17163?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17163.json` |
| 25 | [HADOOP-17503](https://issues.apache.org/jira/browse/HADOOP-17503) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17503?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17503.json` |
| 26 | [HADOOP-17652](https://issues.apache.org/jira/browse/HADOOP-17652) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-17652?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-17652.json` |
| 27 | [HADOOP-18273](https://issues.apache.org/jira/browse/HADOOP-18273) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18273?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18273.json` |
| 28 | [HADOOP-18605](https://issues.apache.org/jira/browse/HADOOP-18605) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18605?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18605.json` |
| 29 | [HADOOP-18759](https://issues.apache.org/jira/browse/HADOOP-18759) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18759?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18759.json` |
| 30 | [HADOOP-18839](https://issues.apache.org/jira/browse/HADOOP-18839) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18839?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18839.json` |
| 31 | [HADOOP-18841](https://issues.apache.org/jira/browse/HADOOP-18841) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18841?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18841.json` |
| 32 | [HADOOP-18875](https://issues.apache.org/jira/browse/HADOOP-18875) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-18875?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-18875.json` |
| 33 | [HADOOP-19023](https://issues.apache.org/jira/browse/HADOOP-19023) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19023?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19023.json` |
| 34 | [HADOOP-19089](https://issues.apache.org/jira/browse/HADOOP-19089) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19089?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19089.json` |
| 35 | [HADOOP-19093](https://issues.apache.org/jira/browse/HADOOP-19093) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19093?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19093.json` |
| 36 | [HADOOP-19104](https://issues.apache.org/jira/browse/HADOOP-19104) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19104?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19104.json` |
| 37 | [HADOOP-19157](https://issues.apache.org/jira/browse/HADOOP-19157) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19157?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19157.json` |
| 38 | [HADOOP-19284](https://issues.apache.org/jira/browse/HADOOP-19284) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19284?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19284.json` |
| 39 | [HADOOP-19388](https://issues.apache.org/jira/browse/HADOOP-19388) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19388?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19388.json` |
| 40 | [HADOOP-19590](https://issues.apache.org/jira/browse/HADOOP-19590) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19590?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19590.json` |
| 41 | [HADOOP-19676](https://issues.apache.org/jira/browse/HADOOP-19676) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19676?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19676.json` |
| 42 | [HADOOP-19767](https://issues.apache.org/jira/browse/HADOOP-19767) | [JSON](https://issues.apache.org/jira/rest/api/2/issue/HADOOP-19767?fields=summary,description,parent,status,comment,subtasks) | `HADOOP-19767.json` |

The same list is in
[benchmark/sources/hadoop-jira/issues.json](../benchmark/sources/hadoop-jira/issues.json).

## 2. Build the packets

```bash
cd benchmark
python build_thread.py --responses <folder with the 42 files>
```

The tool needs only the Python standard library and never accesses the network.
For each record it takes the comment body, or for subtask records the summary,
description and status, and checks the result against the reference SHA-256.
It writes a packet to `benchmark/inputs/public/Thread/` only if every record
and the whole packet match the hashes in `benchmark/manifest.json`.

If an issue has been edited upstream since the study, the affected tasks are
listed and not written. The other tasks are still built.

## 3. Replay with Thread

```bash
python -I -S -B replay.py --require-thread --receipt replay-receipt.json
```

The built packets are ignored by Git; do not commit or redistribute them.
