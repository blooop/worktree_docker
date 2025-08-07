# Install and configure Git (run as root, then switch back to user)
USER root
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
USER wtd
RUN git config --global --add safe.directory '*'
