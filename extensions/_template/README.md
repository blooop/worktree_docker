# Extension Template

This template provides the structure for creating new worktree_docker extensions.

## Extension Structure

Each extension consists of the following files:

### Required Files

- **`worktree_docker.yml`** - Extension manifest defining metadata, dependencies, and auto-detection rules
- **`Dockerfile`** - Docker layer definition for installing and configuring your tool
- **`docker-compose.yml`** - Docker Compose fragment for runtime configuration

### Optional Files

- **`test.sh`** - Test script to verify extension functionality
- **`README.md`** - Documentation for your extension
- **Configuration files** - Any additional files your extension needs

## Manifest Specification

The `worktree_docker.yml` file supports these fields:

### Required Fields

- **`name`** (string) - Unique extension name
- **`description`** (string) - Brief description of the extension

### Optional Fields

- **`dependencies`** (array) - List of extension names this extension depends on
- **`never_load`** (array) - List of extension that are incompatible with this extension
- **`always_load`** (boolean) - Always load this extension regardless of detection
- **`auto_detect`** (object) - Auto-detection rules
  - **`files`** (array) - File patterns (regex) to match in repo root
  - **`directories`** (array) - Directory patterns (regex) to match in repo root  
  - **`host_paths`** (array) - Host system paths to check for tool availability
- **`version`** (string) - Extension version
- **`min_wtd_version`** (string) - Minimum wtd version required
- **`platforms`** (array) - Supported platforms (e.g., linux/amd64)
- **`author`** (string) - Extension author
- **`homepage`** (string) - Extension homepage URL
- **`license`** (string) - Extension license
- **`keywords`** (array) - Keywords for discovery

## Extension Discovery

Extensions are discovered by:

1. **Always-load extensions** - Marked with `always_load: true`
2. **Auto-detection** - Based on patterns in `auto_detect` section
3. **Manual specification** - Via `-e` flag or config files
4. **Dependencies** - Automatically loaded when required by other extensions

## Creating a New Extension

1. Copy this template directory to `extensions/your_extension_name/`
2. Update `worktree_docker.yml` with your extension details
3. Modify `Dockerfile` to install and configure your tool
4. Update `docker-compose.yml` with runtime configuration
5. Create tests in `test.sh` to verify functionality

6. Test your extension with `wtd -e your_extension_name owner/repo`

## How wtd Searches for Extensions in Any Repo

When `wtd` loads a repository, it performs a recursive search for `worktree_docker.yml` files throughout the repo. Any directory containing this manifest is treated as an extension, allowing the repository to dynamically add new features to `wtd`—even if those features are not yet implemented in the main `wtd` project.

This means:

- **Any repository can define its own extensions** by including a properly formatted `worktree_docker.yml` file and supporting files (Dockerfile, docker-compose.yml, etc.).
- **Extensions are loaded automatically** if they match auto-detection rules, are required as dependencies, or are manually specified.
- **Local extensions take precedence** over built-in extensions with the same name, allowing for easy customization and overrides.
- **Dynamic feature support**: Repos can add support for new tools, workflows, or integrations simply by providing an extension directory, without waiting for upstream changes in `wtd`.

This approach makes `wtd` highly extensible and adaptable to new use cases, letting users and projects extend functionality as needed.

## Repository Extensions

When `wtd` loads a repo it will perform a recursive search for `worktree_docker.yml` files and load those extensions.  This lets a repo add support for `wtd`. Local extensions take precedence over built-in extensions with the same name.

## Extension Filtering

The goal is to make extensions as automatic as possible. Extensions should use:

- **Auto-detection patterns** to automatically load based on project files
- **Always-load flag** for essential tools (like x11, fzf)
- **Dependencies** to ensure required tools are available

Users should rarely need to manually specify extensions via `-e` flags.
