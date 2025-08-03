#!/usr/bin/env bash
set -e

echo "=== wtd PRUNE FUNCTIONALITY TEST ==="
echo "Testing both selective and full prune operations"

# Clean up any existing test containers and cache
echo "=== INITIAL CLEANUP ==="
rm -rf ~/.wtd || true
docker container stop test_wtd-main 2>/dev/null || true
docker rm -f test_wtd-main 2>/dev/null || true
echo "Cleaned up existing test environment"

# Test 1: Set up test environment
echo "=== TEST 1: SETUP TEST ENVIRONMENT ==="
wtd blooop/test_renv git status
echo "✓ Test environment created"

# Verify container exists
docker ps | grep test_wtd-main
echo "✓ Container is running"

# Test 2: Selective prune - should remove only blooop/test_renv environment
echo "=== TEST 2: SELECTIVE PRUNE TEST ==="
wtd --prune blooop/test_renv
echo "✓ Selective prune completed"

# Verify specific container is gone (check exact name)
if docker ps --format "table {{.Names}}" | grep "^test_wtd-main$"; then
    echo "✗ Container should have been removed by selective prune"
    exit 1
else
    echo "✓ Container correctly removed by selective prune"
fi

# Verify worktree is gone
if [ -d ~/.wtd/workspaces/blooop/test_renv/worktree-main ]; then
    echo "✗ Worktree should have been removed by selective prune"
    exit 1
else
    echo "✓ Worktree correctly removed by selective prune"
fi

# Test 3: Set up multiple environments for full prune test
echo "=== TEST 3: SETUP MULTIPLE ENVIRONMENTS ==="
wtd blooop/test_renv git status
wtd blooop/test_renv@dev git status 2>/dev/null || wtd blooop/test_renv@main git status  # Use main if dev doesn't exist
echo "✓ Multiple environments created"

# Test 4: Full prune - should remove everything
echo "=== TEST 4: FULL PRUNE TEST ==="
wtd --prune
echo "✓ Full prune completed"

# Verify wtd-related containers are gone
if docker ps --format "table {{.Names}}" | grep -E "(test_wtd|wtd-)"; then
    echo "✗ No wtd containers should exist after full prune"
    exit 1
else
    echo "✓ All wtd containers correctly removed by full prune"
fi

if [ -d ~/.wtd ]; then
    echo "✗ .wtd directory should have been removed by full prune"
    exit 1
else
    echo "✓ .wtd directory correctly removed by full prune"
fi

echo "=== ALL PRUNE TESTS PASSED ==="