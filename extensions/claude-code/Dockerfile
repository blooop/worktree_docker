# Install Claude Code CLI
# Note: This requires npm extension to be loaded first
RUN npm install -g @anthropic-ai/claude-code

# Verify installation
RUN claude --version

# Set up Claude Code configuration directory for wtd user if it exists
RUN if id wtd >/dev/null 2>&1; then \
        mkdir -p /home/wtd/.config/claude-code /home/wtd/.local/share/claude-code; \
        chown -R wtd:wtd /home/wtd/.config/claude-code /home/wtd/.local/share/claude-code; \
        su - wtd -c 'claude --version || true'; \
    fi
