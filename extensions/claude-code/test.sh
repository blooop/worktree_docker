#!/bin/bash
# Test claude-code extension

set -e

echo "Testing claude-code extension..."

# Test that claude is installed
if ! command -v claude &> /dev/null; then
    echo "ERROR: claude command not found"
    exit 1
fi

# Test claude version
claude --version

# Test claude help shows expected commands
claude --help | grep -E "(chat|code|analyze)" || {
    echo "ERROR: Expected claude commands not found in help"
    exit 1
}

echo "claude-code extension test passed!"
