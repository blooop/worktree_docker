# Template Dockerfile for worktree_docker extension
# This file defines the Docker layer for your extension

# Install your tool/package (example using apt)
RUN apt-get update && apt-get install -y \
    my-package \
    my-dependency \
    && rm -rf /var/lib/apt/lists/*

# Alternative: Install from source or binary
# RUN curl -L https://example.com/my-tool.tar.gz | tar -xzC /usr/local/bin/

# Alternative: Install using language package manager
# RUN npm install -g my-tool
# RUN pip install my-python-tool
# RUN cargo install my-rust-tool

# Set up environment variables
ENV MY_TOOL_CONFIG=/workspace/.my-tool

# Create directories or configuration files if needed
RUN mkdir -p /workspace/.my-tool

# Optional: Copy configuration files from the extension directory
# COPY config.json /etc/my-tool/config.json

# Optional: Set up user-specific configurations
# This will run as both root and the wtd user
RUN echo 'export PATH="/path/to/my-tool:$PATH"' >> /etc/bash.bashrc

# Optional: Run as the wtd user for user-specific setup
RUN if id wtd >/dev/null 2>&1; then \
        su - wtd -c 'echo "User-specific setup here"'; \
    fi
