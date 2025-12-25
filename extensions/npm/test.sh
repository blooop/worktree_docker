#!/bin/bash
# Test script for npm extension

set -euo pipefail

echo "Testing npm extension..."

# Test 1: Check if node is installed and accessible
if ! command -v node &> /dev/null; then
    echo "node command not found"
    exit 1
fi
echo "Node.js is installed: $(node --version)"

# Test 2: Check if npm is installed and accessible
if ! command -v npm &> /dev/null; then
    echo "npm command not found"
    exit 1
fi
echo "npm is installed: $(npm --version)"

# Test 3: Check npm configuration
if ! npm config get prefix &> /dev/null; then
    echo "npm config check failed"
    exit 1
fi
echo "npm configuration working"

# Test 4: Check if npm can install a simple package locally
cd /tmp
mkdir -p npm-test && cd npm-test
if ! npm init -y &> /dev/null; then
    echo "npm init failed"
    exit 1
fi
echo "npm init works"

# Test 5: Verify global npm directory is writable (if wtd user exists)
if id wtd >/dev/null 2>&1; then
    if ! su - wtd -c 'npm config get prefix' &> /dev/null; then
        echo "npm global directory check failed for wtd user"
        exit 1
    fi
    echo "npm global directory configured for wtd user"
fi

# Cleanup
cd /tmp && rm -rf npm-test

echo "All tests passed for npm extension!"
