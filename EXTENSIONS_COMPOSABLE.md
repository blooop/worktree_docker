# Composable Extension System Specification

## Overview

The worktree_docker extension system is designed around **true composability** using Docker multi-stage builds. Each extension builds as its own Docker stage and can inherit from other extensions, creating reusable, cacheable, and modular development environments.

## Architecture

### Core Principles

1. **Multi-Stage Builds**: Each extension is a Docker stage that can be used as a base for other extensions
2. **Dependency Inheritance**: Extensions inherit from their dependencies using `FROM dependency_name as extension_name`
3. **Layer Reuse**: Each extension stage can be cached and reused independently
4. **Proper Permission Management**: Root operations for package installation, user context for configuration

### Extension Structure

Each extension consists of:

```
extensions/extension_name/
├── Dockerfile              # Docker instructions for this extension
├── docker-compose.yml      # Compose configuration (optional)
├── worktree_docker.yml     # Extension manifest and metadata
└── test.sh                # Extension test script (optional)
```

## Extension Manifest (`worktree_docker.yml`)

### Required Fields

```yaml
name: extension_name
description: Human-readable description of the extension
```

### Optional Fields

```yaml
# Dependencies - extensions this extension builds upon
dependencies:
  - base        # This extension will inherit FROM base
  - user        # If multiple dependencies, inherits from the last one

# Auto-detection patterns
auto_detect:
  files:
    - "^package\\.json$"     # Regex patterns for files
    - "^requirements\\.txt$"
  directories:
    - "^\\.git$"             # Regex patterns for directories  
  host_paths:
    - "/tmp/.X11-unix"       # Host paths that must exist
  file_contents:
    "package.json":          # Content patterns within files
      - "\"react\""
      - "\"next\""

# Extension behavior
always_load: true           # Always include this extension
```

## Multi-Stage Build Generation

The system generates Dockerfiles with proper dependency inheritance:

### Example Generated Dockerfile

```dockerfile
# Base system packages
FROM ubuntu:22.04 as base
RUN apt-get update && apt-get install -y \
    curl wget unzip build-essential \
    ca-certificates gnupg lsb-release \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# User management - inherits from base
FROM base as user
ARG USERNAME=wtd
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME && \
    echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME
USER $USERNAME
WORKDIR /workspace

# Git support - inherits from user (gets base + user)
FROM user as git
USER root
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
USER wtd
RUN git config --global --add safe.directory '*'

# Final stage - inherits from the last extension
FROM git as final
WORKDIR /workspace
CMD ["bash"]
```

## Extension Dependency Resolution

### Dependency Chain Example

```yaml
# base extension - no dependencies (inherits from base image)
name: base
description: Base system packages

---
# user extension - depends on base
name: user
dependencies: [base]        # FROM base as user

---
# git extension - depends on base and user  
name: git
dependencies: [base, user]  # FROM user as git (inherits base → user → git)
```

### Resolution Algorithm

1. **Topological Sort**: Dependencies are resolved in dependency order
2. **Inheritance Chain**: Each extension inherits `FROM last_dependency as extension_name`
3. **Base Fallback**: Extensions with no dependencies inherit from the base image
4. **Circular Detection**: Circular dependencies are detected and warned

## Permission Management Patterns

### Pattern 1: Root Installation + User Configuration

For extensions that need to install packages but run user-specific configuration:

```dockerfile
# Install packages as root
USER root
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Configure as user
USER wtd  
RUN git config --global --add safe.directory '*'
```

### Pattern 2: Pure User Extensions

For extensions that only do user-level operations:

```dockerfile
# Already running as user from parent stage
RUN git clone --depth 1 https://github.com/junegunn/fzf.git /home/wtd/.fzf
RUN /home/wtd/.fzf/install --all
```

### Pattern 3: System-Only Extensions  

For extensions that only install system packages:

```dockerfile
# Inherits from base (runs as root)
RUN apt-get update && apt-get install -y \
    xauth x11-apps libgl1-mesa-glx libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*
```

## Built-in Extensions

### Core Extensions

| Extension | Dependencies | Purpose | Dockerfile Content |
|-----------|-------------|---------|-------------------|
| `base` | none | System packages | curl, wget, build-essential, sudo |
| `user` | base | User creation | Creates wtd user with sudo access |  
| `git` | base, user | Git VCS | Installs git, configures safe directories |
| `x11` | base | GUI support | X11 packages for graphical applications |

### Language Extensions

| Extension | Dependencies | Purpose | Auto-Detection |
|-----------|-------------|---------|----------------|
| `uv` | none | Python packaging | pyproject.toml, requirements.txt |
| `pixi` | user | Conda-compatible PM | pixi.toml |
| `npm` | user | Node.js/npm | package.json, package-lock.json |
| `react` | npm | React development | package.json with "react" |

### Utility Extensions

| Extension | Dependencies | Purpose | Auto-Detection |
|-----------|-------------|---------|----------------|
| `ssh` | user | SSH client | ~/.ssh directory |
| `fzf` | user | Fuzzy finder | Always detected |
| `default` | base, user, git, x11, ssh | Common setup | Always loaded |

## Creating Custom Extensions

### 1. Basic Extension Structure

```bash
mkdir -p .wtd/extensions/my_extension
cd .wtd/extensions/my_extension
```

### 2. Extension Manifest

```yaml
# .wtd/extensions/my_extension/worktree_docker.yml
name: my_extension
description: My custom development tool
dependencies:
  - user                    # Inherit user environment

auto_detect:
  files:
    - "^my_config\\.yml$"   # Auto-detect when this file exists
```

### 3. Dockerfile Content

```dockerfile
# .wtd/extensions/my_extension/Dockerfile

# Install system dependencies (runs as wtd user, inherited from user stage)
USER root
RUN apt-get update && apt-get install -y my-system-package && rm -rf /var/lib/apt/lists/*

# User-level installation and configuration
USER wtd
RUN curl -sSL https://example.com/install.sh | bash
RUN echo 'export PATH="$HOME/.my_tool/bin:$PATH"' >> ~/.bashrc
```

### 4. Docker Compose Integration

```yaml
# .wtd/extensions/my_extension/docker-compose.yml
volumes:
  - "${HOME}/.my_config:/home/wtd/.my_config:ro"
environment:
  MY_TOOL_CONFIG: "/home/wtd/.my_config"
```

## Extension Loading Process

1. **Discovery**: Scan built-in and local (`.wtd/extensions/`) directories
2. **Auto-Detection**: Run auto-detection patterns against repository
3. **Dependency Resolution**: Resolve and order extensions by dependencies  
4. **Multi-Stage Generation**: Generate Dockerfile with proper `FROM` inheritance
5. **Build**: Use BuildKit to build with layer caching and reuse
6. **Launch**: Start container from final stage

## Best Practices

### Extension Design

1. **Single Responsibility**: Each extension should have one clear purpose
2. **Minimal Dependencies**: Only depend on extensions you actually need
3. **Idempotent Operations**: Extensions should be safe to rebuild/run multiple times
4. **Layer Optimization**: Group related operations to minimize layers
5. **Variable Consistency**: Use hardcoded `wtd` user rather than variables across stages

### Dockerfile Patterns

```dockerfile
# ✅ Good: Clear permission switching
USER root
RUN apt-get update && apt-get install -y package
USER wtd  
RUN user-specific-config

# ✅ Good: Group related operations
RUN apt-get update && apt-get install -y \
    package1 package2 package3 \
    && rm -rf /var/lib/apt/lists/*

# ❌ Bad: Mixed permissions in single RUN
RUN apt-get update && apt-get install -y package && \
    su wtd -c "user-config"
```

### Dependency Management

```yaml
# ✅ Good: Clear, minimal dependencies
dependencies:
  - base
  - user

# ✅ Good: Language extension depending on language manager  
dependencies:
  - npm

# ❌ Bad: Circular dependencies
# Extension A depends on B, Extension B depends on A
```

## Advanced Topics

### Multi-Stage Caching

Each extension stage can be cached independently:

```bash
# Only rebuild stages that changed
docker buildx build --cache-from=type=local,src=.buildx-cache
```

### Extension Composition

Extensions can be composed to create specialized environments:

```bash
# Python AI/ML environment  
wtd myrepo/ai-project -e uv,jupyter,cuda

# React development environment
wtd myrepo/web-app -e npm,react,x11
```

### Cross-Extension Communication

Extensions can share files and configuration through the inherited filesystem:

```dockerfile
# Extension A creates shared config
RUN mkdir -p /workspace/.shared && echo "config" > /workspace/.shared/config

# Extension B (depends on A) uses shared config  
RUN cat /workspace/.shared/config
```

This composable system ensures that extensions are truly reusable building blocks that can be combined, cached, and extended to create powerful, efficient development environments.
