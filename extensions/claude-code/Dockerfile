# Install Claude Code CLI as root (global installation requires root)
# Note: This requires npm extension to be loaded first
USER root
RUN npm install -g @anthropic-ai/claude-code

# Verify installation
RUN claude --version

# Set up Claude Code configuration directories
# Create for root first, then for wtd user if it exists
RUN mkdir -p /root/.config/claude-code /root/.local/share/claude-code

# Set up for wtd user if it exists (after user extension creates the user)
RUN if id wtd >/dev/null 2>&1; then \
        mkdir -p /home/wtd/.config/claude-code /home/wtd/.local/share/claude-code; \
        chown -R wtd:wtd /home/wtd/.config/claude-code /home/wtd/.local/share/claude-code; \
        su - wtd -c 'claude --version || true'; \
    fi
