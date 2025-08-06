# Install OpenSSH client and configure SSH properly for Git operations
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Ensure SSH directory exists with correct permissions
RUN mkdir -p /home/wtd/.ssh && \
    chown wtd:wtd /home/wtd/.ssh && \
    chmod 700 /home/wtd/.ssh

# Add GitHub and GitLab to known_hosts to avoid fingerprint prompts
RUN ssh-keyscan -H github.com >> /home/wtd/.ssh/known_hosts && \
    ssh-keyscan -H gitlab.com >> /home/wtd/.ssh/known_hosts && \
    chown wtd:wtd /home/wtd/.ssh/known_hosts && \
    chmod 644 /home/wtd/.ssh/known_hosts

# Create SSH config with proper settings for Git operations
RUN echo "Host *\n\
    StrictHostKeyChecking no\n\
    UserKnownHostsFile /home/wtd/.ssh/known_hosts\n\
    IdentitiesOnly yes\n\
    AddKeysToAgent yes" > /home/wtd/.ssh/config && \
    chown wtd:wtd /home/wtd/.ssh/config && \
    chmod 600 /home/wtd/.ssh/config
