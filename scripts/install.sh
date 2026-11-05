#!/usr/bin/env bash
set -euo pipefail

# exa-cli installer (JavaScript / Node / Bun / pnpm / npm)
# Installs both the exa-cli executable and the agent skill.

REPO="Sami-754/exa-cli"
BRANCH="master"
SKILL_DIR="${HOME}/.agents/skills/exa-cli"
SKILL_FILE="${SKILL_DIR}/SKILL.md"

echo "==> Installing exa-cli..."

# Detect package manager: bun > pnpm > npm
if command -v bun >/dev/null 2>&1; then
    PM="bun"
    if [ -f "package.json" ] && grep -q '"name": "exa-cli"' package.json 2>/dev/null; then
        echo "--> Installing from local checkout using bun..."
        bun add -g .
    else
        echo "--> Installing from GitHub using bun..."
        bun add -g "git+https://github.com/${REPO}.git"
    fi
elif command -v pnpm >/dev/null 2>&1; then
    PM="pnpm"
    if [ -f "package.json" ] && grep -q '"name": "exa-cli"' package.json 2>/dev/null; then
        echo "--> Installing from local checkout using pnpm..."
        pnpm add -g .
    else
        echo "--> Installing from GitHub using pnpm..."
        pnpm add -g "git+https://github.com/${REPO}.git"
    fi
elif command -v npm >/dev/null 2>&1; then
    PM="npm"
    if [ -f "package.json" ] && grep -q '"name": "exa-cli"' package.json 2>/dev/null; then
        echo "--> Installing from local checkout using npm..."
        npm install -g .
    else
        echo "--> Installing from GitHub using npm..."
        npm install -g "git+https://github.com/${REPO}.git"
    fi
else
    echo "Error: no supported JavaScript package manager found (bun, pnpm, or npm is required)." >&2
    echo "Install Bun (https://bun.sh) or Node.js (https://nodejs.org) to continue." >&2
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
echo "✓ exa-cli installed successfully (via ${PM})"
echo "✓ Agent skill installed to ${SKILL_FILE}"
echo ""
echo "Next steps:"
echo "  1. Set your API key:"
echo "     export EXA_API_KEY=\"your-key\""
echo "     # or run: exa-cli auth login"
echo "  2. Run a search:"
echo "     exa-cli search \"latest AI search benchmarks\" --limit 5"
