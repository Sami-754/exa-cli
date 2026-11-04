# exa-cli — Agent Guidelines & Architecture

## 1. Project Context & Objectives
- **Project:** `exa-cli`
- **Objective:** An agent-native command-line client for the Exa API — natural-language web search, full-text content extraction, and similar-page lookup from the terminal, with machine-readable output.
- **Why it matters:** Turns a research question into cited, full-text JSON in one command, removing the manual scrape-and-stitch loop that agents otherwise spend tool calls on. Mirrors the Exa MCP tools (`web_search_exa`, `web_fetch_exa`) as CLI subcommands.
- **Full design:** See `PLAN.md` (auth flow, MCP→CLI mapping, distribution via `uv tool` + curl install script, milestones).

---

## 2. Session Continuity Protocol
1. **Session Start:** Read `AGENTS.md` (invariants/architecture) and `STATE.md` (live status/verified code) before writing code.
2. **Session End:** Update `STATE.md` with tested snippets, integration states, and next-step checklist.
3. **Security Invariant:** Never log secret API keys, tokens, or passwords into project files. Store only credential names and environment variable references.

---

## 3. System Architecture
```text
argv / stdin
      │
      ▼
┌──────────────────┐    ┌────────────────┐    ┌──────────────────┐
│ CLI Parser       │───►│ API Client     │───►│ api.exa.ai       │
│ (Typer commands) │    │ retry/backoff  │    │ /search ./contents│
└──────────────────┘    │ 401·429·5xx    │    │ /findSimilar     │
      │                 └────────────────┘    └──────────────────┘
      │                         │
      ▼                         ▼
┌──────────────────┐    ┌────────────────┐
│ Renderer         │◄───│ Normalizer     │
│ json | table | md│    │ typed results  │
└──────────────────┘    └────────────────┘
      │
      ▼
stdout (data)  ·  stderr (diagnostics)  ·  exit code
```

**Error isolation:** transport/API failures never mix into stdout. Data goes to stdout only; every diagnostic goes to stderr so piping stays clean.

---

## 4. Key Components Reference
| # | Component | Type | Responsibility |
|:--|:----------|:-----|:---------------|
| 1 | `cli.py` | Typer app | Command surface, flag parsing, exit-code mapping |
| 2 | `client.py` | HTTP client | Auth header, timeouts, retry/backoff on 429 + 5xx |
| 3 | `models.py` | Typed payloads | Request/response schemas, validation |
| 4 | `render.py` | Formatter | table / json / markdown output, truncation |
| 5 | `config.py` | Config loader | `EXA_API_KEY` env > `~/.config/exa-cli/config.toml` |

---

## 5. Non-Negotiable Invariants
1. **Zero Secret Leaks:** No API keys in code, docs, samples, or logs. The key is never echoed — `config show` prints `sk-…abcd` form at most.
2. **Stream Discipline:** Data → stdout. Logs/errors → stderr. `--json` output must parse with zero preprocessing.
3. **Deterministic Exit Codes:** `0` ok · `1` generic · `2` usage · `3` auth · `4` rate-limited · `5` network · `6` upstream 5xx.
4. **Bounded Output:** Every command respects `--limit` / `--max-chars`; never dump an unbounded API body to the terminal.
5. **No Silent Retries on Non-Idempotent Work:** search/contents may retry; anything that spends credits must surface the attempt count on stderr.
6. **Command Name Safety:** Entry point is `exa-cli`, **not** `exa` — the bare `exa` binary is the `ls` replacement (eza) on this machine and must not be shadowed.

---

## 6. Phased Build Checklist
### Milestone 1: Core Skeleton & Client
- [x] Doc scaffold (`AGENTS.md`, `STATE.md`, `PLAN.md`)
- [x] `client.py` with auth, timeout, 429/5xx retry
- [x] `config.py` env → file fallback
- [x] `version` / `config` commands operational

### Milestone 2: Core Commands
- [ ] `search` with `--limit`, `--domains`, `--category`, `--json`
- [ ] `contents` (URLs → text/highlights/summary)
- [ ] `similar` (URL → related pages)
- [ ] Fixtures in `samples/` drive the parser tests

### Milestone 3: Hardening & Distribution
- [ ] Exit-code contract verified against all four fixtures
- [ ] `uv tool install` install path verified
- [ ] README quickstart validated on a clean shell

---

## 7. Out of Scope (V1)
- Agentic/deep-research multi-step orchestration (single-shot calls only)
- Interactive REPL mode
- Websets, Places, and other Exa endpoints beyond search/contents/findSimilar
