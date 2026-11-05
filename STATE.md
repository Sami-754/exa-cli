# Project State: exa-cli

## 1. Build Status Summary
- **Current Milestone:** Complete JavaScript / Node.js / Bun rewrite (zero external dependencies)
- **Status:** `search`/`contents`/`similar`/`answer`/`agent`/`monitors`/`batches`/`auth`/`config`/`version` wired in pure ES module JavaScript.
- **Production Asset:** `src/cli.js`, `src/client.js`, `src/config.js`, `bin/exa-cli.js` — zero-dep Node 18+ / Bun (native `fetch`), installed via `bun`, `pnpm`, or `npm`.

## 2. Integration & Credential Registry
| Service | Credential Name | Environment Variable | Status | Purpose |
|:---|:---|:---|:---|:---|
| Exa API | Exa production key | `EXA_API_KEY` | Live-verified (UUID key, 401 on bad key) | `/search`, `/contents`, `/findSimilar`, `/answer`, `/agent/runs`, `/monitors`, `/batches` |
| Local config | User config file | `~/.config/exa-cli/config.toml` | Working, mode 0600 | Fallback key storage |

Base URL: `https://api.exa.ai` · Auth header: `x-api-key` · Docs: `https://docs.exa.ai`

## 3. Verified Code Configurations
- Commands: `search` (pick-one contents: highlights|text|summary|none), `contents` (statuses), `similar` (deprecated note), `answer` (--text/--schema/--prompt/--model/--country/--stream), `agent` (create/get/list/cancel/stop/events + --wait polling + --schema/--prompt + input.data/exclusion + budget), `monitors` (list/create/get/update/delete/trigger/runs/run/batch), `batches` (create/get/list/cancel)
- Help: every command has `-h/--help` with full flag reference
- Auth: env `EXA_API_KEY` > `~/.config/exa-cli/config.toml` (0600) > interactive prompt. Display masked.
- Retry: 3 max, backoff honours `Retry-After` (cap 30s), attempts on stderr. 401/403 → exit 3, 429 → 4, 5xx → 6, network → 5, usage → 2.
- Stdout = data only (raw JSON under `--json`); stderr = diagnostics.
- Skill is `skills/exa-cli/SKILL.md` (CLI-native), packaged via `force-include` in wheel and installed via `scripts/install.sh` to `~/.agents/skills/exa-cli/SKILL.md`.
- Runtime `_copy_skill` is completely silent (no warning if absent, idempotent skip if matching).

## 4. Test Payloads & Verification Log
Stub + offline tests:
- 429 twice → retry → 200: exit 0, 3 attempts. PASSED.
- 429 exhausted (2 retries): exit 4, attempts on stderr. PASSED.
- `auth login --key` writes 0600 TOML; `auth status`/`config show` mask. PASSED.
- All `--help` variants: 0; missing query/unknown cmd: 2; bad key 401 → 3. PASSED.
- Pick-one contents: default minimal `{highlights:true}` matches skill recommendation. PASSED.
- Invalid `--content banana` → 2. PASSED.
- Agent arg parsing bug (first word swallowed as sub) fixed and live-verified.
- `scripts/install.sh` verified: builds/installs wheel and installs skill cleanly.
- `cd ~ && exa-cli search "..." --json | jq .` clean without stderr or stdout warning noise. PASSED.

Live API verified:
- `search` `--json` exit 0, highlights mode.
- `contents` URL works, 200-with-empty+statuses error correctly parsed (nonexistent host returns statuses, not crash).
- `similar` deprecated warning on stderr, results ok.
- `answer` `--json` + citations, `--stream` passes through.
- `agent` create → poll running → completed with grounding, exit 0.
- Full install: `uv tool install --force /home/sami/Tools/exa-cli` → `exa-cli --help` shows new surface.

## 5. Immediate Next Steps
1. `git commit` + push all upgrades (`install.sh`, `pyproject.toml` wheel force-include, silent skill handling, updated README).
2. Publish to PyPI for `uv tool install exa-cli` bare-name path.
3. Recreate `samples/` fixtures from live responses if desired; add exit-code matrix test.
