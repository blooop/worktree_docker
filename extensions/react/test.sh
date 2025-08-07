#!/bin/bash
# Test react extension

set -e

echo "Testing react extension..."

# Test that npm is available (from npm dependency)
npm --version

# Test that React tools are installed
create-react-app --version

# Test that TypeScript is available
tsc --version

# Test that ESLint is available  
eslint --version

# Test that Prettier is available
prettier --version

echo "react extension test passed!"
