#!/usr/bin/env bash
set -e
cd /tmp


# Clean up test container for fresh start - only if exists and stale
echo "=== CLEANING TEST ENVIRONMENT ==="
# Only remove if container exists and is stopped/problematic
if docker ps -a --format "{{.Names}}" | grep -q "^test_wtd-main$"; then
    if ! docker ps --format "{{.Names}}" | grep -q "^test_wtd-main$"; then
        docker rm -f test_wtd-main >/dev/null 2>&1 || true
        echo "Removed stopped test container"
    else
        echo "Reusing existing test container"
    fi
fi
echo "Starting cache performance test..."
echo

# First create a container to establish baseline
echo "=== INITIAL BUILD ==="
echo "Creating initial container for cache testing"
start_time=$(date +%s)
wtd blooop/test_wtd date
end_time=$(date +%s)
initial_time=$((end_time - start_time))
echo "TIMING: Initial build took ${initial_time} seconds"
echo

# Normal run - should reuse existing container (fastest)
echo "=== CONTAINER REUSE TEST ==="
echo "Running: wtd blooop/test_wtd date should finish fast (reusing existing container)"
start_time=$(date +%s)
wtd blooop/test_wtd date
end_time=$(date +%s)
reuse_time=$((end_time - start_time))
echo "TIMING: Container reuse took ${reuse_time} seconds"
echo

# Force rebuild - removes and recreates container (test timing difference)
echo "=== FORCE REBUILD TEST ==="
echo "Running: wtd --rebuild blooop/test_wtd echo 'rebuild test' to force a rebuild"
start_time=$(date +%s)
wtd --rebuild blooop/test_wtd echo 'rebuild test'
end_time=$(date +%s)
force_time=$((end_time - start_time))
echo "TIMING: Force rebuild took ${force_time} seconds"
echo

# Skip nocache test by default - it's just for timing and causes cache break
# Only run if WTD_TEST_NOCACHE is set to preserve cache while still allowing full testing
if [ "${WTD_TEST_NOCACHE:-}" = "1" ]; then
    echo "=== NO-CACHE REBUILD TEST ==="
    echo "Running: wtd --nocache blooop/test_wtd date"
    start_time=$(date +%s)
    wtd --nocache blooop/test_wtd date
    end_time=$(date +%s)
    nocache_time=$((end_time - start_time))
    echo "TIMING: No-cache rebuild took ${nocache_time} seconds"
else
    echo "=== NO-CACHE REBUILD TEST (SKIPPED) ==="
    echo "Skipping nocache test to preserve cache (set WTD_TEST_NOCACHE=1 to enable)"
    nocache_time=0
fi
echo

# Print timing summary
echo "=== TIMING SUMMARY ==="
echo "Initial build:      ${initial_time}s"
echo "Force rebuild:      ${force_time}s"  
echo "Container reuse:    ${reuse_time}s"
echo "No-cache rebuild:   ${nocache_time}s"
echo
echo "Expected: container reuse should be fastest, force rebuild creates new container"
