#!/bin/bash
# Test npm extension

set -e

echo "Testing npm extension..."

# Test that npm is installed
npm --version

# Test that node is installed  
node --version

# Test basic npm functionality
npm list -g --depth=0

echo "npm extension test passed!"
