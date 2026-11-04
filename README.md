# exa-cli

Agent-native CLI for the Exa API. Natural-language search, full-text contents, similar pages, answer synthesis.

## Install

```bash
uv tool install exa-cli
# or
pipx install exa-cli
# or (from GitHub)
uv tool install git+https://github.com/Sami-754/exa-cli
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
exa-cli contents https://exa.ai/blog/atlas-benchmark --max-chars 4000
exa-cli similar https://exa.ai/blog/atlas-benchmark --limit 5
exa-cli answer "what is Exa Search" --json
exa-cli version
```

Every command is pipe-clean: data on stdout, diagnostics on stderr. `--json` output parses with zero preprocessing.

## Docs

- `AGENTS.md` — invariants, architecture
- `PLAN.md` — design + milestones
- `STATE.md` — live build status
