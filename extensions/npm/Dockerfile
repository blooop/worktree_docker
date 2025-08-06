# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Verify installation
RUN node --version && npm --version

# Set up npm global directory for wtd user if it exists
RUN if id wtd >/dev/null 2>&1; then \
        su - wtd -c 'mkdir -p ~/.npm-global && npm config set prefix ~/.npm-global'; \
        echo 'export PATH=~/.npm-global/bin:$PATH' >> /home/wtd/.bashrc; \
    fi
