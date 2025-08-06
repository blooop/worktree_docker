#!/bin/bash
# Test SSH extension functionality

set -e

echo "Testing SSH extension..."

# Test SSH client is installed
if ! command -v ssh &> /dev/null; then
    echo "ERROR: ssh command not found"
    exit 1
fi

# Test SSH directory exists with correct permissions
if [[ ! -d ~/.ssh ]]; then
    echo "ERROR: ~/.ssh directory does not exist"
    exit 1
fi

# Test SSH directory permissions
SSH_PERMS=$(stat -c %a ~/.ssh)
if [[ "$SSH_PERMS" != "700" ]]; then
    echo "ERROR: ~/.ssh has incorrect permissions: $SSH_PERMS (expected 700)"
    exit 1
fi

# Test known_hosts exists
if [[ ! -f ~/.ssh/known_hosts ]]; then
    echo "ERROR: ~/.ssh/known_hosts does not exist"
    exit 1
fi

# Test GitHub is in known_hosts
if ! grep -q "github.com" ~/.ssh/known_hosts; then
    echo "ERROR: github.com not found in known_hosts"
    exit 1
fi

# Test SSH config exists
if [[ ! -f ~/.ssh/config ]]; then
    echo "ERROR: ~/.ssh/config does not exist"
    exit 1
fi

# Test SSH config permissions
CONFIG_PERMS=$(stat -c %a ~/.ssh/config)
if [[ "$CONFIG_PERMS" != "600" ]]; then
    echo "ERROR: ~/.ssh/config has incorrect permissions: $CONFIG_PERMS (expected 600)"
    exit 1
fi

# Test SSH agent socket if available
if [[ -n "$SSH_AUTH_SOCK" ]] && [[ -S "$SSH_AUTH_SOCK" ]]; then
    echo "✓ SSH agent socket available at $SSH_AUTH_SOCK"
else
    echo "⚠ SSH agent socket not available (this is OK if SSH agent is not running)"
fi

echo "✓ SSH extension test passed"
