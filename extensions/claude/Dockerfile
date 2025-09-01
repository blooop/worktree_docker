# Claude Code extension for worktree_docker
# This extension installs Claude Code CLI

# Install Claude Code using the official installation script
RUN curl -fsSL https://claude.ai/install.sh | bash

# Make Claude accessible to all users by creating a symlink in /usr/local/bin
RUN ln -sf /root/.local/bin/claude /usr/local/bin/claude

# Add Claude Code to PATH for all users (backup approach)
RUN echo 'export PATH="$HOME/.local/bin:/root/.local/bin:$PATH"' >> /etc/bash.bashrc

# Install Claude Code for the wtd user when it's created
RUN if id wtd >/dev/null 2>&1; then \
        su - wtd -c 'curl -fsSL https://claude.ai/install.sh | bash'; \
    fi

