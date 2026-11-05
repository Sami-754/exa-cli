# exa-cli

Agent-native CLI for the Exa API. Natural-language search, full-text contents, similar pages, answer synthesis, agent runs, monitors, and batches. Alias `fetch` for `contents`.

Skill (CLI-native): `skills/exa-cli/SKILL.md`.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/Sami-754/exa-cli/master/scripts/install.sh | bash
```

## Uninstall

```bash
exa-cli uninstall
# or one-liner:
# curl -fsSL https://raw.githubusercontent.com/Sami-754/exa-cli/master/scripts/uninstall.sh | bash
```

## Auth

```bash
export EXA_API_KEY="your-key"      # or:
exa-cli auth login                  # prompts once, saves to ~/.config/exa-cli/config.toml (0600)
exa-cli auth status                 # masked key
exa-cli auth logout                 # deletes stored key
exa-cli config show                 # base_url, timeout, retries, masked key
```

Get a key at https://dashboard.exa.ai/api-keys

## Usage

```bash
exa-cli search "latest AI search benchmarks" --limit 5 --json
exa-cli search "companies named exa" --category company --limit 10
exa-cli search "deep research into RAG evals" --type deep
exa-cli search "latest LLM news" --content text --max-chars 2000
exa-cli search "latest LLM news" --content summary
exa-cli contents https://exa.ai/blog/atlas-benchmark --max-chars 4000
exa-cli contents https://exa.ai/blog/atlas-benchmark --content highlights --json
exa-cli similar https://exa.ai/blog/atlas-benchmark --limit 5
exa-cli answer "what is Exa Search" --json
exa-cli answer "summarize: new AI tools" --stream
exa-cli agent "find five dev tools for evaluating AI agents" --effort auto --wait
exa-cli agent get agent_run_xyz
exa-cli agent list --limit 10
exa-cli monitors list
exa-cli monitors create --query "AI startups funding" --webhook https://example.com/hook --interval 1d
exa-cli monitors runs <id> --limit 5
exa-cli monitors trigger <id>
exa-cli batches list
exa-cli version
```

Every command has `-h`/`--help` with full flag reference. Data on stdout, diagnostics on stderr — `--json` output parses with zero preprocessing.

## Ref (full skill)

- Commands: `search` (`--content highlights|text|summary|none`, default highlights per skill), `contents`/`fetch` (statuses-aware), `similar` (deprecated upstream), `answer` (`--text/--schema/--prompt/--model/--country/--stream`), `agent` (`--effort minimal|low|medium|high|xhigh|auto|ultra --schema/--prompt/--data/--exclusion/--previous/--max-cost/--wait`), `monitors` (create/get/update/delete/trigger/runs/run/batch), `batches` (create/get/list/cancel)
- Skill: `skills/exa-cli/SKILL.md`

## Docs

- `AGENTS.md` — invariants, architecture
- `PLAN.md` — design + milestones
- `STATE.md` — live build status
