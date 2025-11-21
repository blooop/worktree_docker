#!/usr/bin/env bash
set -e

echo "=== TEST: WT COMMAND FUNCTIONALITY ==="
echo "Testing wt command (--no-docker wrapper)"

# Clean up any existing test worktrees and containers
echo "=== INITIAL CLEANUP ==="
rm -rf ~/.wtd/blooop/test_wtd 2>/dev/null || true
docker container stop test_wtd-main 2>/dev/null || true
docker rm -f test_wtd-main 2>/dev/null || true
echo "✓ Initial cleanup completed"

# Test 1: Basic wt command functionality (git operations without Docker)
echo "=== TEST 1: BASIC WT FUNCTIONALITY ==="
output=$(wt blooop/test_wtd git status 2>&1)
if echo "$output" | grep -q "On branch"; then
    echo "✓ wt command successfully runs git status without Docker"
else
    echo "✗ wt command failed to run git status"
    echo "Output: $output"
    exit 1
fi

# Test 2: Verify worktree creation and directory structure
echo "=== TEST 2: WORKTREE CREATION ==="
if [ -d ~/.wtd/blooop/test_wtd/wt-main ]; then
    echo "✓ Worktree directory created with correct structure"
else
    echo "✗ Worktree directory not found at expected location"
    find ~/.wtd -name "*test_wtd*" -type d 2>/dev/null || true
    exit 1
fi

# Test 3: Verify no Docker container was created
echo "=== TEST 3: NO DOCKER CONTAINER CHECK ==="
if docker ps -a --filter name=test_wtd-main --format "{{.Names}}" | grep -q test_wtd-main; then
    echo "✗ Docker container was created when using wt command (should not happen)"
    exit 1
else
    echo "✓ No Docker container created as expected"
fi

# Test 4: Test wt command with different git operations
echo "=== TEST 4: VARIOUS GIT OPERATIONS ==="
wt blooop/test_wtd git log --oneline -3
echo "✓ git log command works"

wt blooop/test_wtd git branch
echo "✓ git branch command works"

wt blooop/test_wtd ls -la
echo "✓ non-git commands work through wt"

# Test 5: Test wt command with branch switching
echo "=== TEST 5: BRANCH SWITCHING ==="
# Create a test branch if it doesn't exist
wt blooop/test_wtd git checkout -b wt_test_branch 2>/dev/null || wt blooop/test_wtd git checkout wt_test_branch

# Verify we're on the new branch
output=$(wt blooop/test_wtd git branch --show-current 2>&1)
if echo "$output" | grep -q "wt_test_branch"; then
    echo "✓ Successfully switched to test branch using wt"
else
    echo "✗ Branch switching failed"
    echo "Output: $output"
    exit 1
fi

# Test 6: Test wt with subfolder specification
echo "=== TEST 6: SUBFOLDER FUNCTIONALITY ==="
wt blooop/test_wtd#test_subfolder pwd
if [ -d ~/.wtd/blooop/test_wtd/wt-main/test_subfolder ]; then
    echo "✓ Subfolder created and accessible"
else
    echo "✗ Subfolder not created"
    exit 1
fi

# Test 7: Verify git functionality works correctly outside containers
echo "=== TEST 7: GIT FUNCTIONALITY VERIFICATION ==="
cd ~/.wtd/blooop/test_wtd/wt-main

# Test basic git operations in the worktree
git status
if [ $? -eq 0 ]; then
    echo "✓ Direct git operations work in worktree"
else
    echo "✗ Direct git operations failed in worktree"
    exit 1
fi

# Test git config and user setup
git config user.name "Test User" 2>/dev/null || true
git config user.email "test@example.com" 2>/dev/null || true

# Create a test file and commit
echo "test content" > wt_test_file.txt
git add wt_test_file.txt
git commit -m "Test commit for wt functionality" 2>/dev/null || echo "Commit may have already existed"

# Verify the commit worked
git log --oneline -1 | grep -q "Test commit\|test content\|wt_test_file" && echo "✓ Git commits work correctly"

cd - > /dev/null

# Test 8: Test wt help and version
echo "=== TEST 8: HELP AND VERSION ==="
wt --help | grep -q "no-docker" && echo "✓ wt help shows underlying --no-docker behavior"

# Test 9: Compare behavior with wtd --no-docker
echo "=== TEST 9: CONSISTENCY WITH WTD --NO-DOCKER ==="
wt_output=$(wt blooop/test_wtd pwd)
wtd_output=$(wtd --no-docker blooop/test_wtd pwd)

if [ "$wt_output" = "$wtd_output" ]; then
    echo "✓ wt command produces identical output to wtd --no-docker"
else
    echo "✗ wt output differs from wtd --no-docker"
    echo "wt output: $wt_output"
    echo "wtd output: $wtd_output"
    exit 1
fi

# Test 10: Test error handling
echo "=== TEST 10: ERROR HANDLING ==="
set +e  # Allow errors for this test
wt nonexistent/repo git status 2>/dev/null
exit_code=$?
set -e

if [ $exit_code -ne 0 ]; then
    echo "✓ wt properly handles non-existent repositories"
else
    echo "✗ wt should have failed for non-existent repository"
    exit 1
fi

# Clean up test files
echo "=== CLEANUP ==="
rm -rf ~/.wtd/blooop/test_wtd 2>/dev/null || true
echo "✓ Cleanup completed"

echo "=== WT COMMAND FUNCTIONALITY TEST PASSED ==="
