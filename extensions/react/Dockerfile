# syntax=docker/dockerfile:1
# React extension - provides React development tools
# Depends on npm extension for Node.js and npm

# Import the npm stage which includes user + base + npm
FROM npm-stage as react-base

# Install React development tools globally
RUN npm install -g create-react-app @vitejs/create-app

# Install common development dependencies
RUN npm install -g typescript eslint prettier

# Final stage
FROM react-base
# Additional React-specific configuration can go here
