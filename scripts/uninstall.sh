#!/usr/bin/env bash
set -euo pipefail

# exa-cli uninstaller
# Removes the agent skill, configuration, and global binary.

echo "==> Uninstalling exa-cli..."

# 1. Remove agent skill
SKILL_DIR="${HOME}/.agents/skills/exa-cli"
if [ -d "${SKILL_DIR}" ]; then
    rm -rf "${SKILL_DIR}"
    echo "✓ Removed agent skill (${SKILL_DIR})"
fi

# 2. Remove configuration and keys
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/exa-cli"
if [ -d "${CONFIG_DIR}" ]; then
    rm -rf "${CONFIG_DIR}"
    echo "✓ Removed configuration (${CONFIG_DIR})"
fi

# 3. Uninstall global CLI package
echo "--> Removing binary via package managers..."
if command -v bun >/dev/null 2>&1; then
    bun remove -g exa-cli >/dev/null 2>&1 || true
fi
if command -v pnpm >/dev/null 2>&1; then
    pnpm remove -g exa-cli >/dev/null 2>&1 || true
fi
if command -v npm >/dev/null 2>&1; then
    npm uninstall -g exa-cli >/dev/null 2>&1 || true
fi

# Remove direct fallback binary if exists
if [ -f "${HOME}/.local/bin/exa-cli" ]; then
    rm -f "${HOME}/.local/bin/exa-cli"
fi

echo ""
echo "✓ exa-cli has been completely uninstalled."
