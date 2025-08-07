#!/bin/bash
# Test claude-code extension

set -e

echo "Testing claude-code extension..."

# Test that npm is available (dependency)
npm --version

# Test that claude is installed and executable
if ! command -v claude &> /dev/null; then
    echo "ERROR: claude command not found in PATH"
    echo "PATH: $PATH"
    echo "Searching for claude:"
    find /usr -name "claude" 2>/dev/null || echo "Claude not found in /usr"
    find /home -name "claude" 2>/dev/null || echo "Claude not found in /home"
    which node || echo "Node not found"
    npm list -g --depth=0 || echo "Failed to list global packages"
    exit 1
fi

# Test claude version (this actually executes claude)
claude --version

# Test claude help shows expected output
claude --help | head -10

# Verify the help contains basic usage info
if ! claude --help | grep -q "claude"; then
    echo "ERROR: claude help doesn't contain expected content"
    exit 1
fi

echo "claude-code extension test passed!"
