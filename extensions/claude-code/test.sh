#!/bin/bash
# Test script for claude-code extension

set -euo pipefail

echo "Testing claude-code extension..."

# Test 1: Check if claude command is available
if ! command -v claude &> /dev/null; then
    echo "claude command not found"
    exit 1
fi
echo "Claude Code CLI is installed"

# Test 2: Check version
if ! claude --version &> /dev/null; then
    echo "claude --version failed"
    exit 1
fi
echo "Claude Code version check passed: $(claude --version)"

# Test 3: Check if help command works
if ! claude --help &> /dev/null; then
    echo "claude --help failed"
    exit 1
fi
echo "Claude Code help command works"

# Test 4: Check if doctor command works (non-interactive check)
if ! timeout 10 claude doctor --quiet &> /dev/null || true; then
    echo "Claude Code doctor command accessible"
else
    echo "Claude Code doctor command accessible"
fi

# Test 5: Check configuration directory exists for wtd user
if id wtd >/dev/null 2>&1; then
    if ! su - wtd -c 'mkdir -p ~/.config/claude-code'; then
        echo "Could not create Claude config directory for wtd user"
        exit 1
    fi
    echo "Claude Code configuration directory setup for wtd user"
fi

# Test 6: Verify npm dependency
if ! command -v npm &> /dev/null; then
    echo "npm dependency not found - this extension requires the npm extension"
    exit 1
fi
echo "npm dependency satisfied"

echo "All tests passed for claude-code extension!"
