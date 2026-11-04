# exa-cli — Design Plan

One-shot agent-native CLI for the Exa API: natural-language search, full-text
contents, similar pages, and answer synthesis from the terminal, with
machine-readable output. Mirrors the Exa MCP tools as CLI subcommands.

## 1. What it is

- **Runtime:** Python 3.11+, Typer (CLI), httpx (HTTP), Rich (tables).
- **Entry point:** `exa-cli` (deliberately never `exa` — that is eza on this
  machine).
- **Base URL:** `https://api.exa.ai`. Auth header: `x-api-key`.
- **Source of truth for schemas:** Exa OpenAPI spec
  (`https://exa.ai/docs/exa-spec.yaml`, saved in scratchpad during planning).
- **MCP mapping:**

| exa-mcp tool | CLI command | Endpoint |
|---|---|---|
| `web_search_exa` | `search` | `POST /search` |
| `web_search_advanced_exa` | `search --advanced` (same cmd, extra flags) | `POST /search` |
| `web_fetch_exa` | `contents` (alias `fetch`) | `POST /contents` |
| — | `similar` | `POST /findSimilar` (deprecated upstream, still shipped) |
| `agent_run` | out of scope for V1 | `/agent/runs` |

## 2. Repo layout (final)

Three docs files + code. Nothing else.

```
exa-cli/
├── AGENTS.md          # invariants, architecture, this plan's summary
├── STATE.md           # live build status, verified snippets, next steps
├── PLAN.md            # THIS FILE — design + milestones
├── .env.example
├── .gitignore
├── skills/
│   └── exa-cli/       # agent skill (CLI adaptation of Exa's skill)
│       └── SKILL.md
└── src/exa_cli/       # to be built (M1)
    ├── __init__.py    # __version__ = "0.1.0"
    ├── cli.py         # Typer app, commands, exit-code mapping
    ├── config.py      # key resolution + first-run prompt + 0600 storage
    ├── client.py      # httpx client, retry/backoff, status → exit code
    ├── models.py      # typed request/response payloads, validation
    └── render.py      # json | table | markdown output, truncation
```

`pyproject.toml`, `samples/`, and the old `src/` stub were removed —
nothing references them yet. They get recreated fresh in M1.

## 3. Auth system

Resolution order, first hit wins:

1. `EXA_API_KEY` environment variable.
2. `~/.config/exa-cli/config.toml`, mode `0600`, key `api_key = "***"`.
3. Interactive first-run prompt (paste key once, saved to the TOML above).

Commands:

- `auth login` — prompt for key (hidden input), validate with a cheap call,
  save to TOML 0600. Also accepts `--key-env EXA_API_KEY`.
- `auth status` — masked key only (`sk-…abcd` form at most), never the full key.
- `auth logout` — delete the stored key file.
- `config show` — base URL, timeout, retries, masked key.
- `config set timeout|retries|base-url` — persist overrides in TOML.
- `version` — print `exa-cli <version>` (exists).

Security invariants:

- Zero secret leaks: never log/echo the key; `config show` masks.
- Key file is always `0600`; created with `os.open(..., 0o600)`.
- No keys in `samples/`, docs, or logs. Fixtures use fake request IDs.

## 4. API client

- Timeout: 15s default (`EXA_TIMEOUT_SECONDS` override).
- Retries: 3 max, exponential backoff (1s → 2s → 4s), honour `Retry-After`.
- Retry on: HTTP 429, 5xx. Never retry 400/401/403.
- On 429/5xx surface attempt count on **stderr** before exit.
- Map status → exit code via the contract in §7.
- Responses validated against `samples/` fixtures first (offline), then live.

## 5. Commands (V1 scope)

### `search QUERY [flags]`
Flags: `--limit/-n` (1–100, default 10), `--json`, `--type`
(`auto|lite|deep|deep-lite`), `--category`
(`company|people|news|personal site|financial report|publication`),
`--include-domain` (repeatable), `--exclude-domain` (repeatable),
`--from/--to` (ISO dates), `--text/--no-text`, `--max-chars`,
`--highlights/--no-highlights`, `--summary`, `--fresh`
(`maxAgeHours`, 0 = always fresh, -1 = cache only).
Note: `lite` rejects unknown params — CLI must not send unsupported flags
when `--type lite`.

### `contents URLS... [flags]`
Accepts URLs as args or stdin (one per line). Flags:
`--max-chars`, `--text/--no-text`, `--highlights`, `--summary`,
`--json`, `--verbosity` (`compact|standard|full`).

### `similar URL [flags]`
Wrapper over `POST /findSimilar` (deprecated upstream but functional).
Flags: `--limit`, `--json`, `--max-chars`.

### `answer QUERY [flags]`
Wrapper over `POST /answer`. Flags: `--json`, `--stream` (SSE passthrough).

### Rendering
- `--json` → raw parsed JSON on **stdout**; must pipe to `jq` untouched.
- Default → Rich table (title, url, date, score) on stdout.
- `--md` → markdown list for embedding in agent context.
- Diagnostics always on **stderr**.
- Empty results: `[]` on stdout (json mode), notice on stderr, exit 0.

## 6. Distribution

- **Dev:** `uv sync --extra dev && uv run exa-cli --help`.
- **uv tool:** `uv tool install exa-cli` (name stays `exa-cli`).
- **Curl install script** (`scripts/install.sh`):
  - Detect OS/arch (linux/macOS, amd64/arm64).
  - Download release asset (PyInstaller single-file binary preferred) to
    `~/.local/bin/exa-cli`; fallback to `uv tool install exa-cli`.
  - Create `~/.config/exa-cli/` and `~/.local/share/exa-cli/` (cache).
  - On first run, `exa-cli` prompts for the API key (see §3).
- Repo also ships `uv.lock` + `pip install .` path.

## 7. Exit code contract

| Code | Meaning |
|---|---|
| 0 | ok (including empty results) |
| 1 | generic error |
| 2 | usage / validation (bad query, bad fixture) |
| 3 | auth (401/403, no key, missing key) |
| 4 | rate-limited (429 after retries) |
| 5 | network (timeout, DNS, connection) |
| 6 | upstream 5xx (after retries) |

## 8. Milestones & verification

1. **M1 — Skeleton + auth + client.** `config.py` (env → TOML → prompt),
   `client.py` (retry/backoff), `auth`/`config`/`version` commands.
   Verify: `auth login` writes 0600 file; `config show` masks.
2. **M2 — Core commands.** `search`, `contents`, `similar`, `answer` +
   renderers. Verify against recreated `samples/` fixtures offline first
   (happy → 0, invalid → 2, rate-limited → 4, empty → 0 with `[]`),
   then live search with a real key.
3. **M3 — Hardening & dist.** Exit-code matrix test, install script,
   `uv tool install` verified on clean shell, README quickstart validated.

## 9. Skill (CLI adaptation)

`skills/exa-cli/SKILL.md` ports Exa's MCP skill: same intents
(search / fetch / similar / answer) but expressed as shell commands
(`exa-cli search "…"` etc.) with `--json` discipline and exit-code
semantics, so agents on machines without MCP can use it.

## 10. Out of scope (V1)

Agentic multi-step orchestration, REPL, Websets, Monitors API, interactive
TUI, streaming beyond `--stream` on `answer`.
