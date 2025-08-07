FROM mcr.microsoft.com/devcontainers/base:jammy

ARG PIXI_VERSION=v0.41.4

RUN curl -L -o /usr/local/bin/pixi -fsSL --compressed "https://github.com/prefix-dev/pixi/releases/download/${PIXI_VERSION}/pixi-$(uname -m)-unknown-linux-musl" \
    && chmod +x /usr/local/bin/pixi \
    && pixi info

# Install npm and claude-code
USER root
RUN apt-get update && apt-get install -y npm \
    && npm install -g @anthropic-ai/claude-code

# set some user and workdir settings to work nicely with vscode
USER vscode
WORKDIR /home/vscode

RUN echo 'eval "$(pixi completion -s bash)"' >> /home/vscode/.bashrc
