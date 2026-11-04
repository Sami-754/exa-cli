# Project State: exa-cli

## 1. Build Status Summary
- **Current Milestone:** Milestone 2 — Core Commands (M1 done)
- **Status:** Working CLI skeleton. `search`/`contents`/`similar`/`answer`/`auth`/`config`/`version` wired.
- **Production Asset:** `src/exa_cli/` — zero-dep Python (urllib), run via `python3 -m exa_cli.cli` or `PYTHONPATH=src`.

## 2. Integration & Credential Registry
| Service | Credential Name | Environment Variable | Status | Purpose |
|:---|:---|:---|:---|:---|
| Exa API | Exa production key | `EXA_API_KEY` | Unverified (key rejected 401) | `/search`, `/contents`, `/findSimilar`, `/answer` |
| Local config | User config file | `~/.config/exa-cli/config.toml` | Working, mode 0600 | Fallback key storage |

Base URL: `https://api.exa.ai` · Auth header: `x-api-key` · Docs: `https://docs.exa.ai`

## 3. Verified Code Configurations
- Commands: `search QUERY [--limit N] [--json] [--type TYPE] [--category CAT] [--domain D] [--max-chars N]`,
  `contents URLS... [--max-chars N] [--json]`, `similar URL [--limit N] [--json]`,
  `answer QUERY [--stream] [--json]`, `auth login|status|logout`, `config show`, `version`
- Auth: env `EXA_API_KEY` > `~/.config/exa-cli/config.toml` (0600) > interactive prompt. Display masked `sk_…abcd`.
- Retry: 3 max, backoff honours `Retry-After` (cap 30s), attempts on stderr. 401/403 → exit 3, 429 → 4, 5xx → 6, network → 5, usage → 2.
- Stdout = data only (raw JSON under `--json`); stderr = diagnostics.
- One verified live call so far: bad key correctly exits 3 with `INVALID_API_KEY` body.

## 4. Test Payloads & Verification Log
Stub-server tests (no network, `http.server` on localhost):
- 429 twice → retry → 200: exit 0, 3 attempts. PASSED.
- 429 exhausted (2 retries): exit 4, attempts on stderr. PASSED.
- `auth login --key` writes 0600 TOML; `auth status`/`config show` mask. PASSED.
- `search --help`, `unknowncmd`, missing query, bad key → 0/2/2/3. PASSED.
- Key never present in `src/` (grep checked). PASSED.

No live search with a valid key yet — the supplied key returned 401, needs a fresh one from dashboard.

## 5. Immediate Next Steps
1. Get a valid `EXA_API_KEY`, run `exa-cli auth login` (or set env), then live `search "test" --limit 2 --json | jq .`.
2. Verify `contents`, `similar`, `answer` against live API; fix any schema mismatches.
3. Recreate `samples/` fixtures from live responses; add exit-code matrix test.
4. Write `scripts/install.sh` (download binary / `uv tool install` fallback) + curl distribution.
5. Write `skills/exa-cli/SKILL.md` (CLI adaptation of Exa's MCP skill).
