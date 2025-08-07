# syntax=docker/dockerfile:1
# NPM extension - provides Node.js and npm
# This stage can be reused by other extensions that need npm

# Import the npm stage from the multi-stage build
FROM ubuntu:22.04 as npm-stage
COPY --from=npm / /

# Final stage
FROM npm-stage
# Extension-specific configuration can go here if needed
