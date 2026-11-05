#!/usr/bin/env bash
set -euo pipefail

# exa-cli installer
# Installs both the exa-cli executable and the agent skill.

REPO="Sami-754/exa-cli"
BRANCH="master"
SKILL_DIR="${HOME}/.agents/skills/exa-cli"
SKILL_FILE="${SKILL_DIR}/SKILL.md"

echo "==> Installing exa-cli..."

# Check install method (uv tool > pipx > pip)
if command -v uv >/dev/null 2>&1; then
    if [ -f "pyproject.toml" ] && grep -q 'name = "exa-cli"' pyproject.toml 2>/dev/null; then
        echo "--> Installing from local checkout using uv..."
        uv tool install --force .
    else
        echo "--> Installing from GitHub using uv..."
        uv tool install --force "git+https://github.com/${REPO}.git"
    fi
elif command -v pipx >/dev/null 2>&1; then
    if [ -f "pyproject.toml" ] && grep -q 'name = "exa-cli"' pyproject.toml 2>/dev/null; then
        echo "--> Installing from local checkout using pipx..."
        pipx install --force .
    else
        echo "--> Installing from GitHub using pipx..."
        pipx install --force "git+https://github.com/${REPO}.git"
    fi
else
    echo "Error: neither 'uv' nor 'pipx' found. Please install uv (https://astral.sh/uv) or pipx." >&2
    exit 1
fi

echo "==> Installing agent skill to ${SKILL_FILE}..."
mkdir -p "${SKILL_DIR}"

if [ -f "skills/exa-cli/SKILL.md" ]; then
    cp "skills/exa-cli/SKILL.md" "${SKILL_FILE}"
else
    # Remote install via curl
    curl -fsSL "https://raw.githubusercontent.com/${REPO}/${BRANCH}/skills/exa-cli/SKILL.md" -o "${SKILL_FILE}"
fi

echo ""
echo "✓ exa-cli installed successfully"
echo "✓ Agent skill installed to ${SKILL_FILE}"
echo ""
echo "Next steps:"
echo "  1. Set your API key:"
echo "     export EXA_API_KEY=\"your-key\""
echo "     # or run: exa-cli auth login"
echo "  2. Run a search:"
echo "     exa-cli search \"latest AI search benchmarks\" --limit 5"
