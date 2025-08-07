FROM npm as claude-code
# Install Claude Code CLI globally
USER root
RUN npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*
USER wtd
