---
name: exa-cli
description: |
  Use this skill whenever a task needs the web: searching for information, checking current facts or news, finding sources, reading a URL, finding a page on a site, extracting full-page content, getting a grounded answer with citations, building a list or enriching a dataset, or watching a topic/site for new results over time. Use it for anything past your training data or anything the user wants verified online. Prefer exa-cli commands over SDK/HTTP.
allowed-tools: Bash(exa-cli *)
metadata:
  project: exa-cli
  version: "0.1.0"
  docs: "https://exa.ai/docs"
---

# Exa CLI

`exa-cli` is the CLI surface for the Exa API: commands + subcommands that
call the API directly. Run `exa-cli --help` or `exa-cli <command> --help`
for full option details.

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

## Prerequisites

Must be installed and authenticated. Check with `exa-cli auth status`.

```bash
exa-cli auth status
# logged_in key=sk_…abcd
```

- **Key resolution:** `EXA_API_KEY` > `~/.config/exa-cli/config.toml` (0600) > prompt.
- **Display is always masked** (`sk_…`).
- **Base URL:** `https://api.exa.ai`, header `x-api-key`.

If not ready:

```bash
export EXA_API_KEY="your_api_key_here"
# or first-run prompt
exa-cli auth login
```

Before doing real work, verify the setup with one small request:

```bash
exa-cli search "what is exa ai" --limit 1 --json
```

## Workflow

Follow this escalation pattern:

1. **Search** - No specific URL yet. Find pages, answer questions, discover sources.
2. **Contents** - Have a URL. Extract its content directly.
3. **Answer** - Need a grounded answer with citations fast, no need for raw sources.
4. **Agent** - Complex multi-step research, list-building, or enrichment with schema.
5. **Monitor** - Need recurring checks or ongoing alerts on a topic. Prefer a monitor over repeated one-off searches.
6. **Batch** - Need many requests at once (async). Submit via batches, poll status.

| Need                        | Command               | When                                                      |
| --------------------------- | --------------------- | --------------------------------------------------------- |
| Find pages on a topic       | `search`              | No specific URL yet                                       |
| Get a page's content        | `contents`            | Have a URL, static or JS-rendered                         |
| Grounded answer + citations | `answer`              | Fast answer, no need to read sources yourself             |
| Multi-step research / list  | `agent`               | Structured output, web research, enrichment               |
| Watch topics for changes    | `monitors`            | Schedule recurring searches, webhook on new results       |
| Bulk async requests         | `batches`             | Submit many search/contents/agent requests at once        |
| Auth / config               | `auth` / `config`     | Login, logout, status, show masked config                 |

Every command has `-h`/`--help`. Data → stdout, diagnostics → stderr,
`--json` parses with zero preprocessing.

## How to use it (do's)

**Search:**
- **Write queries for a search engine.** Use names and terms you expect on the page, not the user's whole request. Split a question with several parts into one focused search per part.
- **Keep result counts tight.** Default `--limit 10`; raise only when you genuinely need a broad sweep. Narrow with `--domain`, `--exclude-domain`, `--from`, `--to`, `--category`, `--fresh`.
- **Pick exactly one content mode** (`highlights|text|summary|none`, default highlights). Never stack highlights+text+summary. `--content summary` requires an explicit user request for per-result synthesis.
- **Gated flags only.** Any extra flag must be task-justified (e.g. `--type deep` only when the user asked for deep research, `--max-chars` only with `--content text`).

**Contents:**
- URLs can be args or stdin (one per line). `statuses` in the response mean HTTP 200 ≠ all URLs succeeded — check non-`success` statuses.
- Top-level fields are used (not nested under `contents`).

**Answer / Agent:**
- Prefer `search` when the app already has its own LLM. `answer` is for a grounded answer + citations without reading sources yourself.
- `agent` lifecycle: create → `id` (`agent_run_*`) → poll `get` until `completed|failed|cancelled` → only `completed` carries `output`. Always set `--effort` explicitly.

**Monitors:**
- `--webhook` is required on create (HTTPS; localhost/private rejected). `webhookSecret` is returned **once** at creation — save it immediately.
- Update: `--pause`/`--resume`, `--query`, `--interval`, `--webhook`, `--metadata K=V`.
- Bias toward `monitors` when the user's goal is ongoing change detection or alerting over time. For a single topic/site, default to `monitors create` with `--query` and `--webhook`.

**Batches:**
- Useful when you need many requests at once. Submit via `batches create --mode search|contents|agent`, then `batches get`.

## When to stop

- Stop once two independent sources agree on a fact.
- Before you answer, close any gap your draft would mark unconfirmed: run one targeted search or reread the recommended pages.
- For releases, ownership, official figures and decisions by a named body, confirm on the official domain. A secondary site or a generated answer is not enough.
- Don't keep raising `--limit` to get "more" — narrow with filters instead.

## Hand off the job

When the user wants an in-depth report that needs many sources gathered and weighed (comparison across criteria, deep investigation), use `agent` with `--effort auto` or `deep` instead of doing many manual searches. If it isn't available, fall back to `search --type deep`.

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

Command examples are the skill. Flags map directly to the Exa API:
- `search.md` (search types, content modes, categories)
- `contents.md` (statuses, freshness)
- `snapshot.md` (snapshotAsOf)
- `answer.md`, `agent.md`, `monitors.md`, `http-requests.md`,
  `models-and-modes.md`, `common-mistakes.md`
