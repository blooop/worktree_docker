
 I am adding a new tool to complement rockerc.  its called wtd and uses rocker to create a development container. You
   can use rockerc as inspiration for how to manage rocker, but create wtd as a separate tool that calls rocker 
  directly. rockerc expects there to be rockerc files, whereas wtd shoudl work on any repo without a rockerc file and 
  defines its own require extension for basic development. I have included some tempalte workflows as bash scripts, you
   must implement rocker to meeting the all the specs in the markdown file and also the tests stubs I left in 
  test/worksflows. use the pixi environment and pixi tasks to run tests and ci. you are working on the host machine   where rocker is installed. aad an executable `wtd` to the pyproject.toml.  write lots of tests and work step by test
   to implement the features and higher level goal


# wtd - Rocker Environment Manager

## Overview

`wtd` is a tool for seamless multi-repo development using git worktrees and rocker containers. It automates cloning, worktree management, and container launching, making it easy to switch between branches and repositories in isolated environments.

The main workflow to support is the user can type a `wtd repo_owner/repo_name` and re enter the container seamlessly, ie, if it needs to be built, build and attach.  If the image is already built but not running, start the container and attach, and if the container is already running, it should attach to that container.  

wtd uses rocker to manage the building of the dockerfiles via extensions. wtd automatically loads some default extensions to provide a base level of developer experience such as ssh, git etc. The user can add their own develoment tools by creating an extension for it.  The aim is that you only have to write a dockerfile for your tools once, and then you can bring it along to any development environment you want via a flag. see https://github.com/blooop/deps_rocker and https://github.com/osrf/rocker.   When the use runs the wtd command on a repo, the user will enter a fully set up development container directly inside that git repository. 

wtd automatically names the containers based on the repo name and branch name. so wtd blooop/test_renv@feature1 creates a docker image and container named test_wtd-feature1 and enters a folder called test_wtd as that is the repo name. 

You can also use wtd to run commands directly in the container and branch.  The last arguments are passed on directly to rocker which passes them onto docker. The behavior between entering a container and running a command is identical to running that command inline

Enable shell autocompletion:
```bash
wtd --install
source ~/.bashrc  # or restart your terminal
```

## Usage

```
Usage: wtd [OPTIONS] <owner>/<repo>[@<branch>][#<subfolder>] [-- <command>...]

A development environment launcher using Docker, Git worktrees, and Buildx/Bake.

Clones and manages repositories in isolated git worktrees, builds cached container environments using Docker Buildx + Bake, and launches fully configured shells or commands inside each branch-specific container workspace.

Examples:
  wtd blooop/test_renv@main
  wtd blooop/test_renv@feature/foo
  wtd blooop/test_renv@main#src
  wtd blooop/test_renv git status
  wtd blooop/test_renv@dev "bash -c 'git pull && make test'"

Commands:
  launch       Launch container for the given repo and branch (default behavior)
  list         Show active worktrees and running containers
  destroy      Stop and remove container for a repo/branch
  prune        Remove unused containers and cached images
  help         Show this help message

Options:
  --install         Install shell auto-completion script (bash/zsh/fish)
  --rebuild         Force rebuild of container and extensions, even if cached
  --nocache         Disable use of Buildx cache (useful for clean debugging)
  --no-gui          Disable X11 socket mounting and GUI support
  --no-gpu          Disable GPU passthrough and NVIDIA runtime
  --builder NAME    Use a custom Buildx builder name (default: wtd_builder)
  --platforms LIST  Target platforms for Buildx (e.g. linux/amd64,linux/arm64)
  --log-level LEVEL Set log verbosity: debug, info, warn, error (default: info)
  -h, --help        Show this help message and exit

Arguments:
  <owner>/<repo>[@<branch>][#<subfolder>]
                   GitHub repository specifier:
                   - owner/repo (default branch = main)
                   - @branch    (e.g. main, feature/foo)
                   - #subfolder (working directory after container start)
  [-- <command>...] Any command string to run inside the container (e.g. bash -c ...)

Environment:
  wtd_CACHE_DIR            Set custom cache directory (default: ~/.wtd/)
  wtd_BASE_IMAGE           Override base image used for environments
  wtd_CACHE_REGISTRY       Push/pull extension build cache to a registry

Notes:
  - Worktrees are stored under ~/.wtd/workspaces/<owner>/<repo>/worktree-<branch>
  - Extensions can be configured via .wtd.yml in the repo
  - Extension images are hashed and reused across repos/branches automatically
  - Supports Docker socket sharing (DOOD) and Docker-in-Docker (DinD) setups
```

### Major Workflows

#### 1. Clone and Work on a Repo
```bash
wtd blooop/test_renv@main
```
- Clones as bare repo to `~/wtd/blooop/test_renv`
- Creates worktree for `main` at `~/wtd/blooop/test_renv/worktree-main`
- Launches a rocker container in that worktree
- git command work immediately on entering (ie, enter into the correct folder for git to work with worktrees, and bare repo is mounted properly)

#### 2. Switch Branches (Isolated Worktrees)
```bash
wtd blooop/test_renv@feature/new-feature
```
- Creates new worktree for the branch
- Launches container in the new worktree
- Previous worktrees remain intact

#### 3. Switch Back to Main
```bash
wtd blooop/test_renv@main
```
- Re-attaches to the main branch worktree and container. Does not need to rebuild

#### 4. Work on Multiple Repos
```bash
wtd osrf/rocker@main
```
- Sets up and launches a container for another repo while retaining access to existing repos and branches

#### 5. Run a command in a container

```bash
wtd blooop/test_renv git status
```
- Runs git status command and exit the container immediately

#### 5. Run a command in a container on a branch

```bash
wtd blooop/test_renv@main git status
```

- Runs git status command and exit the container immediately

#### 5. Run a multi stage command in a container

```bash
wtd blooop/test_renv "bash -c 'git status; pwd; ls -l'"

```

- prints the git status, the current working directory, and a list of files.

#### 5. Debug or Manual Management
```bash
wtd blooop/test_renv@main --no-container
```
- Sets up worktree but does not launch container


some of these workflows have been set up as scripts that must get run as part of testing. 

## Directory Structure
```
~/wtd/
├── blooop/
│   └── bencher/
│       ├── HEAD
│       ├── config
│       ├── worktrees
│   └── test_wtd/
│       ├── HEAD
│       ├── config
│       ├── worktrees
└── osrf/
    └── rocker/
        ├── HEAD
        └── worktrees
```

by default wtd will ignore the rocker extensions --cwd --nvidia  and it will pass --nocleanup and --persist image to rocker. It ignores --cwd because it uses its own volume mounting and workspace logic.


by default wtd has these extensions enabled

image: ubuntu:22.04
# Default arguments enabled for container setup
args:
  - user    # Enable user mapping for file permissions
  - pull    # Enable automatic image pulling
  - git     # Enable git integration
  - git-clone # Enable git clone support
  - ssh     # Enable SSH support
  - nocleanup # Prevent cleanup after run
  - persist-image # Persist built image after run so its always cached

extension-blacklist:
  - nvidia  # Disable NVIDIA GPU support by default
  - create-dockerfile # Overly verbose for 3rd party repos
  - cwd     # We have custom mounting logic




## Additional Commands

### List Active Environments
```bash
wtd list
```
Shows all active worktrees and running containers.

### Cleanup Commands
```bash
wtd prune                    # Remove all unused containers and images
wtd prune blooop/test_renv   # Remove specific repo's resources
```

### Advanced Options
```bash
wtd blooop/test_renv --rebuild    # Force rebuild even if cached
wtd blooop/test_renv --nocache    # Disable Buildx cache for debugging
wtd blooop/test_renv --no-gui     # Disable X11/GUI support
wtd blooop/test_renv --no-gpu     # Disable GPU passthrough
```

## Intelligent Autocompletion & Fuzzy Finder

When running `wtd` without arguments, or with partial input, interactive fuzzy finding is enabled using `iterfzf`:

- **Partial Matching**: As you type, `iterfzf` matches any part of the repo or branch name. For example, typing `bl tes ma` will match `blooop/test_renv@main`.
  - You can type fragments separated by spaces to quickly narrow down results.
  - Example prompt: `Select repo@branch (type 'bl tes ma' for blooop/test_renv@main):`
- **User Completion**: Type a partial username and press TAB to complete based on existing directories in `~/wtd/`.
  ```bash
  wtd blo<TAB>    # Completes to blooop/ if ~/wtd/blooop/ exists
  ```
- **Repository Completion**: After a username and `/`, TAB completes repository names.
  ```bash
  wtd blooop/tes<TAB>    # Completes to blooop/test_renv if ~/wtd/blooop/test_renv exists
  ```
- **Branch Completion**: After a repository and `@`, TAB completes branch names using git.
  ```bash
  wtd blooop/test_renv@fea<TAB>    # Completes to available branches like feature/xyz
  ```
- **Interactive Selection**: If no argument is provided, a fuzzy finder UI appears, allowing you to search and select from all available repo@branch combinations. You can use partial words and space-separated fragments for fast selection.

This makes switching between repos and branches fast and error-free, even in large multi-repo setups.

## Requirements
- Git
- rockerc
- rocker (Docker)

## Troubleshooting
- If repo exists, latest changes are fetched
- If worktree exists, it is reused
- If container build fails, check `rockerc.yaml`, Docker, and rocker installation

## Notes
- Branch names with `/` are converted to safe directory names
- Multiple worktrees and containers can be active in parallel
- Autocompletion covers user, repo, and branch names

---
For more details, see the project README or run `wtd --help`.


this is an example of how to use oyr-run-arg to pass arguments to docker through rocker.

