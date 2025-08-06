#!/bin/bash
# Test SSH extension functionality

set -e

echo "Testing SSH extension..."

# Test SSH client is installed
if ! command -v ssh &> /dev/null; then
    echo "ERROR: ssh command not found"
    exit 1
fi

# Test SSH directory exists (should be mounted from host)
if [[ ! -d ~/.ssh ]]; then
    echo "ERROR: ~/.ssh directory does not exist (should be mounted from host)"
    exit 1
fi

# Test SSH agent socket if available
if [[ -n "$SSH_AUTH_SOCK" ]] && [[ -S "$SSH_AUTH_SOCK" ]]; then
    echo "✓ SSH agent socket available at $SSH_AUTH_SOCK"
else
    echo "⚠ SSH agent socket not available (this is OK if SSH agent is not running)"
fi

# Test that we can attempt SSH connections (will use host SSH config and keys)
if ssh -o BatchMode=yes -o ConnectTimeout=5 -T git@github.com 2>&1 | grep -q "successfully authenticated\|Permission denied"; then
    echo "✓ SSH connection to GitHub can be attempted (using host SSH setup)"
else
    echo "⚠ Could not test SSH connection to GitHub (this is OK if no SSH keys are configured)"
fi

echo "✓ SSH extension test passed"
