FROM npm as claude-code
# Install Claude Code CLI globally
USER root
RUN npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/* \
    && which claude || echo "Claude not found in PATH"
# Ensure npm global bin is in PATH
ENV PATH="/usr/local/bin:$PATH"
USER wtd
