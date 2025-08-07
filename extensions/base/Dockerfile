FROM ubuntu:22.04 as base
RUN apt-get update && apt-get install -y \
    curl wget unzip build-essential \
    ca-certificates gnupg lsb-release \
    sudo \
    && rm -rf /var/lib/apt/lists/*
