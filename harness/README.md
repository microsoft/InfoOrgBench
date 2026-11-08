# InfoOrgBench agent harnesses

This directory contains the agent code used for the systems in Table 3. It is
separate from the benchmark scorer. The release supports Python 3.11 or newer
and does not install or contact a model service during setup or testing.

## Harnesses

| CLI name | Paper configuration | Agent-visible actions |
| --- | --- | --- |
| `react-fc` | Reference ReAct-FC function-calling loop | `list_files`, `read_file`, `search_files`, `move_files`, `check_inventory` |
| `codex` | Codex CLI 0.162.1 | Native command and file-edit tools |
| `pi` | Pi 1.1.0 | Five bounded tools named `record_list`, `record_read`, `record_search`, `record_move`, and `record_inventory` |
| `dsh` | DeepSeek Harness 0.2.1-alpha.1 | Native DSH tools in a workspace-write sandbox |
| `deepagents` | Deep Agents 0.7.23 | The same five bounded record tools as Pi |

ReAct-FC resends the complete episode history. It keeps every output item,
including provider-returned reasoning items, and every function result. Its
record operations, argument schemas, pagination, folder validation, packet
layout, full-history behavior, incremental instructions, final-state capture,
and integrity check are the released experiment implementations.

Pi uses a fresh in-memory session with compaction, cache warming, skills, and
extensions disabled. Deep Agents uses a fresh graph with summarization,
built-in file and shell tools, planning, and subagents disabled. DSH disables
telemetry, memory, and subagents. Codex uses its built-in instructions,
conversation management, native commands, and workspace-write sandbox; web
search, apps, memories, and multi-agent operation are disabled. All harnesses
use a new workspace for each task. The independently captured final filesystem,
not the model's final declaration, determines the prediction.

### Host-access boundary

Codex and DSH run model-controlled shells. As in the paper, their sandbox
allows host reads outside the writable task workspace. This release denies the
benchmark, result ledger, common credential/configuration locations, and
network access to Codex, and gives every child process a strict environment
allowlist. These controls do not establish complete host isolation. Run Codex
and DSH in a disposable virtual machine, container, or dedicated user account
that contains no credentials or unrelated private files.

Codex additionally denies existing locations such as `.ssh`, `.aws`, `.azure`,
`.config/gh`, `.copilot`, `.docker`, `.kube`, `.git-credentials`, `.npmrc`,
`.netrc`, and the GitHub CLI configuration directory. Add site-specific paths
with a repeatable option:

```powershell
python -m infoorgbench_harness run --harness codex --model gpt-6.1-sol `
  --backend copilot --family Recap --tasks mini-001 --out .\run-codex `
  --codex-deny-root D:\sensitive --codex-deny-root D:\other-private-data
```

The shared paper profile has medium reasoning effort, 128,000 maximum output
tokens per response, a 2,400-second request timeout, and no episode-time,
decision-turn, or cumulative-token limit. Claude Haiku 4.5 omits the reasoning
field and therefore uses the provider default. Exact defaults and the 45
system entries are in `configs/`.

## Install this package

From the repository root:

```powershell
python -m pip install -e .\harness
python -m unittest discover -s tests -p "test_harness_*.py" -v
```

The Python package uses only the standard library. The native third-party
harnesses have their own pinned installations. The repository MIT license
covers the adapter code, not the separately installed Copilot CLI or other
third-party runtimes; those retain their own terms.

### Codex CLI

```powershell
npm install -g @openai/codex@0.162.1
codex --version
$env:INFOORGBENCH_CODEX = (Get-Command codex).Source
```

The version command must report `codex-cli 0.162.1`.

### Pi

Pin every `@earendil-works` package to 1.1.0. Without the explicit pins, npm
resolves the sibling packages to newer releases that the 1.1.0 agent cannot
load.

```powershell
npm install --prefix .\harness\.third-party\pi `
  @earendil-works/pi-coding-agent@1.1.0 @earendil-works/pi-ai@1.1.0 `
  @earendil-works/pi-agent-core@1.1.0 @earendil-works/pi-codemode@1.1.0 `
  @earendil-works/pi-mcp@1.1.0 @earendil-works/pi-tui@1.1.0 @earendil-works/chord@1.1.0
$env:INFOORGBENCH_PI_ROOT = (Resolve-Path .\harness\.third-party\pi)
```

### DeepSeek Harness

```powershell
git clone https://github.com/deepseek-ai/deepseek-harness.git .\harness\.third-party\dsh
git -C .\harness\.third-party\dsh checkout 5badb15009ae1756c3afe0ae0cef1faafc290ccc
corepack enable
pnpm --dir .\harness\.third-party\dsh install
pnpm --dir .\harness\.third-party\dsh run build
$env:INFOORGBENCH_DSH_SOURCE = (Resolve-Path .\harness\.third-party\dsh)
```

This is the source commit for release 0.2.1-alpha.1. It requires Node 22.19 or
24 and pnpm 11.28.5.

### Deep Agents

```powershell
python -m pip install `
  deepagents==0.7.23 langchain==1.4.4 langchain-core==1.6.9 `
  langchain-openai==1.7.0 langchain-anthropic==1.7.5 langgraph==1.2.14
```

## Model backends

Every harness uses a loopback gateway at `127.0.0.1`. Each run receives a
random in-memory bearer token. The gateway authenticates model and record-tool
requests before reading their bodies, accepts JSON only, limits request size,
read time and concurrency, and never writes the token to receipts or logs. The
gateway exposes OpenAI Responses, OpenAI Chat Completions, and Anthropic
Messages, including SSE responses. It passes a request through unchanged when
the client and upstream use the same protocol, except for required storage
controls, and translates it otherwise. Codex always uses Responses.
The paper runs used Anthropic Messages for Claude models and Responses for the
other released models. Pi and Deep Agents retain that selection at their
client boundary. DSH uses its Responses adapter. Responses reasoning effort
maps to Anthropic adaptive thinking plus `output_config.effort`. Chat `length`
and Anthropic `max_tokens` stops remain incomplete responses and are captured
with the same final-state behavior as the original ReAct-FC runtime.

The gateway is the default reproducible path. A third-party harness can instead
use its documented native provider-key configuration, but that changes the
released adapter boundary and must be reported as a different condition.

Provider base URLs must use HTTPS; plain HTTP is accepted only on loopback.
Model transports reject redirects rather than forwarding credentials to a new
location. No inference request is retried by default. `--transport-retries 1` enables one
small retry for a connection failure or a provider refusal that reports no
completed inference; `Retry-After` is honored. Provider-reported usage is
included in the content-free receipt.

### GitHub Copilot

This option uses the user's own GitHub Copilot entitlement and quotas through
the official Copilot SDK provider-endpoint API. The API is experimental and
must be opted into. The helper keeps endpoint metadata and short-lived headers
in memory, sends them only through a process pipe, refreshes before expiry and
after HTTP 401 or 403, and never includes them in logs or receipts.

Install the Copilot CLI package whose bundled SDK and runtime were verified,
either globally or in `harness/copilot` (`npm install` there uses the pinned
version), and sign in interactively:

```powershell
npm install -g @github/copilot@1.0.67
copilot
```

The helper checks the version of the runtime bundled in that npm package. The
CLI can update itself, so `copilot --version` may report a newer build; the
check uses the bundled runtime, not that build. To try another version, set
`INFOORGBENCH_COPILOT_ALLOW_UNVERIFIED=1` or point
`INFOORGBENCH_COPILOT_RUNTIME` at a folder containing `copilot.exe` (or
`copilot`) and `copilot-sdk/index.js`.

A stored `github.com` login from GitHub CLI is also supported:

```powershell
gh auth login --hostname github.com
```

For a non-interactive run, place a GitHub token in an environment variable that
you choose and pass its name. The token must identify an account with Copilot:

```powershell
if (-not $env:COPILOT_GITHUB_TOKEN) { throw 'Set COPILOT_GITHUB_TOKEN in this process.' }
python -m infoorgbench_harness run `
  --harness react-fc --model gpt-6-luna --backend copilot `
  --copilot-token-env COPILOT_GITHUB_TOKEN --family Recap --tasks mini-001 `
  --out .\run-reactfc-copilot
```

The model list depends on account, plan, policy, and time. Models verified while
preparing this release included `claude-haiku-4.5`, `claude-haiku-5.5`,
`claude-sonnet-5.5`, `mai-code-1.1-flash`, `grok-4.7`, `gpt-5.6-luna`,
`gpt-5.6-terra`, `gpt-6-luna`, and `gpt-6.1-sol`. Availability is not
promised. Individual and enterprise plans can return different hosts; the code
does not hard-code one.

### Provider API keys

Keys are read only from named environment variables. They are never accepted as
CLI values. OpenAI Responses uses `openai`:

```powershell
$env:OPENAI_API_KEY = '<provider key>'
python -m infoorgbench_harness run `
  --harness react-fc --model gpt-6.1-sol --backend openai `
  --family Recap --tasks mini-001 --out .\run-reactfc-openai
```

Anthropic Messages uses `anthropic` and `ANTHROPIC_API_KEY`. Chat Completions
supports OpenAI-compatible services such as xAI and OpenRouter:

```powershell
$env:XAI_API_KEY = '<provider key>'
python -m infoorgbench_harness run `
  --harness react-fc --model grok-4.7 --backend openai-chat `
  --base-url https://api.x.ai/v1 --key-env XAI_API_KEY `
  --family Recap --tasks mini-001 --out .\run-reactfc-xai
```

For Azure OpenAI, pass the full deployment endpoint, including its API version,
and select the API-key header:

```powershell
$env:AZURE_OPENAI_API_KEY = '<provider key>'
python -m infoorgbench_harness run `
  --harness react-fc --model '<deployment name>' --backend openai-chat `
  --base-url 'https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=<version>' `
  --key-env AZURE_OPENAI_API_KEY --key-header api-key `
  --family Recap --tasks mini-001 --out .\run-reactfc-azure
```

## Reproduce a system

This command reproduces one Table 3 system on one released Recap task after
backend setup:

```powershell
python -m infoorgbench_harness run `
  --harness react-fc --model claude-haiku-4.5 --backend anthropic `
  --family Recap --tasks mini-001 --out .\run-one-system
python -m infoorgbench_harness score --run .\run-one-system `
  --out .\run-one-system\scores.json
```

Use `--family Design` for Design. Thread record text is not distributed. Build
its packets first from the public Jira responses:

```powershell
python .\benchmark\build_thread.py --responses <folder-with-Hadoop-Jira-responses>
```

If the packets are absent, `run` and `score` stop with this instruction rather
than treating missing records as tasks.

For Codex with the same Copilot backend:

```powershell
python -m infoorgbench_harness run `
  --harness codex --model gpt-6.1-sol --backend copilot `
  --copilot-token-env COPILOT_GITHUB_TOKEN --family Recap --tasks mini-001 `
  --out .\run-codex-copilot
```

Each task prediction has the release format
`{"assignments":[{"id":"...","path":["..."]}]}`. `receipt.json` contains
versions, hashes, settings, task status, and provider-reported usage. It omits
prompts, record text, conversations, credentials, and endpoint metadata.

## Relation to the paper runs

The exact shared and family prompts, ReAct-FC system and incremental
instructions, and record workspace implementation are copied from the executed
code. The Pi and Deep Agents workers retain their executed session and tool
setup, with the request timeout parameterized by the released profile. The
public ReAct-FC loop is rewritten to
remove experiment bookkeeping and retained transcripts while preserving the
model-visible request sequence and stopping behavior. The Codex and DSH
adapters are rewritten around the public loopback gateway but retain their
pinned native versions, prompt delivery, tools, permission settings, history,
and limits. Record tool calls from Pi and Deep Agents are applied to the
workspace one at a time, and invalid arguments return to the model as tool
errors. For Codex these include the Windows `mxc` sandbox, read denial of
the repository's `benchmark/` and `results/` folders and disabled network
access. Only the model transport changed: the paper's earlier transport is
replaced by Copilot provider endpoints or ordinary provider API keys. Requests
for 128,000 output tokens are capped at a model's provider limit (64,000 for
Claude Haiku 4.5), as the paper's transport did.

## Verification

On 2026-11-07 each harness completed Recap task `mini-001` through the GitHub
Copilot backend, signed in as a github.com personal account whose Copilot
entitlement comes from an organization seat. Each run produced a valid tree
that the released scorer accepted:

| Harness | Model | Upstream protocol | Structure Score |
| --- | --- | --- | ---: |
| ReAct-FC | GPT-6 Luna | Responses | 42.3 |
| ReAct-FC | Claude Haiku 4.5 | Anthropic Messages | 29.1 |
| Codex CLI 0.162.1 | GPT-6 Luna | Responses through the gateway | 22.0 |
| Pi 1.1.0 | GPT-6 Luna | Responses through the gateway | 45.7 |
| DeepSeek Harness 0.2.1-alpha.1 | GPT-6 Luna | Responses through the gateway | 39.3 |
| Deep Agents 0.7.23 | Claude Haiku 4.5 | Anthropic Messages through the gateway | 33.2 |

These are single-task checks of the software, not results. An individual
Copilot Free or Pro plan was not tested. The provider API-key backends were
tested against local mock servers for all three protocols, not against a
live provider account.

## Limitations

- The Copilot provider-endpoint API is experimental. It may change or be
  unavailable, and all calls consume the user's own allowance.
- Model access, rate limits, output limits, and usage accounting depend on the
  selected plan and provider. A model name in Table 3 does not grant access.
- Gemini 4 Argon is not reproducible through the released backends.
- Protocol translation preserves text, tool calls, tool results, system blocks,
  and provider usage. Opaque reasoning items are passed only when the protocol
  permits them; otherwise they are omitted.
- Third-party harness packages can change behavior if their exact pins are not
  installed. The adapters reject version mismatches where the package exposes a
  version check.
