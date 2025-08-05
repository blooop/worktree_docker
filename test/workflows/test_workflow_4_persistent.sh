#!/usr/bin/env bash
set -e
cd /tmp

# Only prune if previous test files exist to ensure clean state
if wtd blooop/test_wtd ls 2>/dev/null | grep -q "persistent.txt"; then
    wtd --prune blooop/test_wtd
fi

echo "Running: wtd blooop/test_wtd touch persistent.txt to confirm that persistent files work as expected"
wtd blooop/test_wtd touch persistent.txt

echo "Running: wtd blooop/test_wtd ls to confirm that persistent files are present"
wtd blooop/test_wtd ls