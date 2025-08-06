#!/bin/bash
# Template test script for worktree_docker extension
# This script tests that your extension is working correctly

set -e  # Exit on any error

echo "Testing my_extension..."

# Test 1: Check if the tool is installed and accessible
if ! command -v my-tool &> /dev/null; then
    echo "❌ my-tool command not found"
    exit 1
fi
echo "✅ my-tool is installed"

# Test 2: Check version/basic functionality
if ! my-tool --version &> /dev/null; then
    echo "❌ my-tool --version failed"
    exit 1
fi
echo "✅ my-tool version check passed"

# Test 3: Check environment variables
if [[ -z "${MY_TOOL_ENV}" ]]; then
    echo "❌ MY_TOOL_ENV environment variable not set"
    exit 1
fi
echo "✅ Environment variables configured"

# Test 4: Check mounted directories/files
if [[ ! -d "/workspace/.my-tool" ]]; then
    echo "❌ Tool directory not found"
    exit 1
fi
echo "✅ Tool directories mounted correctly"

# Test 5: Test basic functionality
echo "Hello from my-tool" | my-tool process || {
    echo "❌ Basic functionality test failed"
    exit 1
}
echo "✅ Basic functionality works"

echo "🎉 All tests passed for my_extension!"
