---
name: exa-cli
description: "Use exa-cli to call the Exa API from the terminal: search, contents extraction, answer, Agent runs, monitors, and batches. Use when you need semantic web retrieval, page content, grounded answers, list-building/enrichment, or scheduled recurring searches — prefer exa-cli commands over SDK/HTTP."
metadata:
  project: exa-cli
  version: "0.1.0"
  docs: "https://exa.ai/docs"
  skill-basis: "skills/build-with-exa/SKILL.md (official, verbatim)"
---

# Exa CLI

`exa-cli` is the CLI surface for the Exa API. Same semantics as the official
`build-with-exa` skill and the Exa MCP tools, expressed as **commands +
subcommands** instead of SDK calls or raw HTTP.

## Scope

Included:

- Search: `exa-cli search` (highlights | text | summary | none)
- Contents: `exa-cli contents` (top-level content fields, statuses)
- Answer: `exa-cli answer` (grounded answer + citations)
- Agent: `exa-cli agent` (async runs, polling, structured output)
- Monitors: `exa-cli monitors` (create/get/update/delete/trigger/runs)
- Batches: `exa-cli batches` (create/get/list/cancel)
- Auth: `exa-cli auth login|status|logout`, `exa-cli config show`
- Snapshot: `--snapshot` on search/contents

Out of scope: Websets (deprecated, use Agent), OpenAI-compat endpoints.

Original official skill (SDK/HTTP framing) lives at
`skills/build-with-exa/` — this file is the CLI adaptation.

## Installation

```bash
uv tool install exa-cli
# or: pipx install exa-cli
# or from source: uv tool install git+https://github.com/Sami-754/exa-cli
```

## Authentication

```bash
export EXA_API_KEY="your_api_key_here"
# or first-run prompt
exa-cli auth login
exa-cli auth status
exa-cli auth logout
exa-cli config show
```

- Key resolution: `EXA_API_KEY` > `~/.config/exa-cli/config.toml` (0600) > prompt.
- Display is always masked (`sk_…`).
- Base URL: `https://api.exa.ai`, header `x-api-key`.

Every command has `-h`/`--help`. Data → stdout, diagnostics → stderr,
`--json` parses with zero preprocessing.

## Quick Start

```bash
exa-cli search "latest developments in LLMs"
exa-cli search "latest developments in LLMs" --limit 5 --json
exa-cli search "deep research into RAG evals" --type deep
exa-cli search "battery breakthroughs" --content text --max-chars 2000
exa-cli contents https://arxiv.org/abs/2307.06435
exa-cli contents https://exa.ai/blog/atlas-benchmark --content text --max-chars 4000
exa-cli answer "What is the latest valuation of SpaceX?" --json
exa-cli agent "Find engineering leaders at AI infra companies" --effort auto --wait
exa-cli monitors list
exa-cli batches list
```

## Command reference

### `exa-cli search QUERY [flags]`

Default (recommended) request:

```bash
exa-cli search "latest developments in LLMs"
# equals { "query": "...", "type": "auto", "contents": { "highlights": true } }
```

Flags (gated — add only when the task requires it):

- `--limit N`          numResults (1–100, default 10)
- `--type TYPE`        auto | lite | deep-lite | deep | deep-reasoning | fast | instant
- `--content MODE`     highlights | text | summary | none (default highlights)
- `--max-chars N`      with `--content text` only; otherwise `text:true` bare
- `--category CAT`     company | people | publication | news | "personal site" | "financial report"
- `--domain D`         includeDomains (repeatable)
- `--exclude-domain D` excludeDomains (repeatable)
- `--from ISO` / `--to ISO`  start/endPublishedDate (hard window only)
- `--fresh HOURS`      maxAgeHours (0=fresh, -1=cache only)
- `--snapshot ISO`     snapshotAsOf (ISO date-time pin)
- `--schema FILE`      outputSchema (JSON file; not with `--type lite`)
- `--prompt TEXT`      systemPrompt
- `--json`             raw JSON stdout

Pitfalls: pick **exactly one** content mode; never stack highlights+text+summary.
`--content summary` requires an explicit user request for per-result synthesis.

### `exa-cli contents URLS... [flags]`

```bash
exa-cli contents https://example.com/page
exa-cli contents https://a.com https://b.com --content text --json
# stdin also works: printf "%s\n" https://x.com | exa-cli contents
```

Flags: `--content highlights|text|summary`, `--max-chars N`,
`--fresh HOURS`, `--snapshot ISO`, `--crawl-timeout MS`,
`--subpages N`, `--subpage-target TEXT`, `--extras-links N`, `--extras-images N`,
`--json`. Top-level fields are used (not nested under `contents`).
`statuses` in the response mean HTTP 200 ≠ all URLs succeeded.

### `exa-cli similar URL [--limit N] [--json]`

Deprecated upstream. Prefer `search` with a query derived from the seed page
(after `contents` on the URL). Kept for compatibility.

### `exa-cli answer QUERY [flags]`

```bash
exa-cli answer "What is the valuation of SpaceX?" --json
exa-cli answer "Summarize: quantum computing" --stream
exa-cli answer "q" --schema schema.json --prompt "be concise"
```

Flags: `--stream` (SSE chunks), `--text` (full text in citations),
`--schema FILE` (outputSchema), `--prompt TEXT` (systemPrompt),
`--model M` (exa|exa-pro|exa-research|exa-fast), `--country CC`,
`--json`. Prefer `search` when the app already has its own LLM.

### `exa-cli agent QUERY [flags]`

```bash
exa-cli agent "Find 5 dev tools for evaluating AI agents" --effort auto --wait
exa-cli agent get <RUNID> | agent list | agent cancel|stop <RUNID>
```

Flags: `--effort minimal|low|medium|high|xhigh|auto|ultra`,
`--schema FILE` (outputSchema), `--prompt TEXT` (systemPrompt),
`--data FILE` (input.data JSON array), `--exclusion FILE` (input.exclusion),
`--previous ID` (previousRunId), `--max-cost N` (budget.maxCostDollars),
`--max-duration N` (budget.maxDurationSeconds),
`--wait` (poll until terminal), `--json`.

Lifecycle: create → `id` (`agent_run_*`) → poll `get` until
`completed|failed|cancelled` → only `completed` carries `output`.
Always set `--effort` explicitly.

### `exa-cli monitors CMD [args]`

```bash
exa-cli monitors create --query "AI startups funding" --webhook https://example.com/hook --interval 1d
exa-cli monitors list | get <ID> | update <ID> | delete <ID>
exa-cli monitors trigger <ID> | runs <ID> | run <ID> <RUNID>
```

`--webhook` is required on create (HTTPS; localhost/private rejected).
`webhookSecret` is returned **once** at creation — save it immediately.
Update: `--pause`/`--resume`, `--query`, `--interval`, `--webhook`, `--metadata K=V`.

### `exa-cli batches CMD [args]`

```bash
exa-cli batches create --mode search --requests reqs.json
exa-cli batches get <ID> | list [--limit N] | cancel <ID>
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok (including empty results) |
| 1 | generic error |
| 2 | usage / validation |
| 3 | auth (401/403, no key, missing key) |
| 4 | rate-limited (429 after retries) |
| 5 | network |
| 6 | upstream 5xx |

## Where the rules live

Command examples above mirror `skills/build-with-exa/references/`:

- `search.md` — request shape, types, categories
- `contents.md` — statuses, freshness
- `snapshot.md` — snapshotAsOf
- `answer.md`, `agent.md`, `monitors.md`, `http-requests.md`,
  `models-and-modes.md`, `common-mistakes.md`
