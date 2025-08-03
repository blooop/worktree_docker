# worktree_docker

## Continuous Integration Status

[![Ci](https://github.com/blooop/worktree_docker/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/blooop/worktree_docker/actions/workflows/ci.yml?query=branch%3Amain)
[![Codecov](https://codecov.io/gh/blooop/worktree_docker/branch/main/graph/badge.svg?token=Y212GW1PG6)](https://codecov.io/gh/blooop/worktree_docker)
[![GitHub issues](https://img.shields.io/github/issues/blooop/worktree_docker.svg)](https://GitHub.com/blooop/worktree_docker/issues/)
[![GitHub pull-requests merged](https://badgen.net/github/merged-prs/blooop/worktree_docker)](https://github.com/blooop/worktree_docker/pulls?q=is%3Amerged)
[![GitHub release](https://img.shields.io/github/release/blooop/worktree_docker.svg)](https://GitHub.com/blooop/worktree_docker/releases/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/worktree_docker)](https://pypistats.org/packages/worktree_docker)
[![License](https://img.shields.io/github/license/blooop/worktree_docker)](https://opensource.org/license/mit/)
[![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads/)
[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)

## Installation

### Recommended Method:

Install [pipx](https://pypa.github.io/pipx/) (if not already installed):

```
sudo apt install pipx
pipx ensurepath
```

Then install worktree_docker and its dependencies globally with:

```
pipx install --include-deps worktree_docker
```

This will ensure that `worktree_docker` and `rocker` commands are available on your PATH.

## Usage

navigate to a directory with a `worktree_docker.yaml` file and run:
```
worktree_docker 
```

This will search recursively for worktree_docker.yaml and pass those arguments to rocker

## Motivation

[Rocker](https://github.com/osrf/rocker) is an alternative to docker-compose that makes it easier to run containers with access to features of the local environment and add extra capabilities to existing docker images.  However rocker has many configurable options and it can get hard to read or reuse those arguments.  This is a naive wrapper that read a worktree_docker.yaml file and passes them to rocker.  There are currently [no plans](https://github.com/osrf/rocker/issues/148) to integrate docker-compose like functionalty directly into rocker so I made this as a proof of concept to see what the ergonomics of it would be like. 

## Caveats

I'm not sure this is the best way of implementing worktree_docker like functionality.  It might be better to implmented it as a rocker extension, or in rocker itself.  This was just the simplest way to get started. I may explore those other options in more detail in the future. 


# rocker.yaml configuration

You need to pass either a docker image, or a relative path to a dockerfile

worktree_docker.yaml
```yaml
image: ubuntu:22.04
```

or

```yaml
dockerfile: Dockerfile
```

will look for the dockerfile relative to the worktree_docker.yaml file