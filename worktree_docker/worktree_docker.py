"""
wtd - Development environment launcher using Docker, Git worktrees, and Buildx/Bake

A tool that combines git worktrees with Docker Compose and Buildx to provide
isolated development environments for each repository branch.
"""

import sys
import subprocess
import logging
import argparse
import time
import json
import yaml
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    from iterfzf import iterfzf
except ImportError:
    iterfzf = None


@dataclass
class RepoSpec:
    """Repository specification parser and container."""

    owner: str
    repo: str
    branch: str = "main"
    subfolder: Optional[str] = None

    @classmethod
    def parse(cls, spec: str) -> "RepoSpec":
        """Parse repo specification: owner/repo[@branch][#subfolder]"""
        # Split by # for subfolder
        parts = spec.split("#", 1)
        repo_branch = parts[0]
        subfolder = parts[1] if len(parts) > 1 else None

        # Split by @ for branch
        parts = repo_branch.split("@", 1)
        owner_repo = parts[0]
        branch = parts[1] if len(parts) > 1 else "main"

        # Split by / for owner/repo
        owner, repo = owner_repo.split("/", 1)

        return cls(owner=owner, repo=repo, branch=branch, subfolder=subfolder)

    def __str__(self) -> str:
        result = f"{self.owner}/{self.repo}@{self.branch}"
        if self.subfolder:
            result += f"#{self.subfolder}"
        return result

    @property
    def compose_project_name(self) -> str:
        """Generate Docker Compose project name."""
        safe_branch = self.branch.replace("/", "-").replace("_", "-")
        return f"{self.repo}-{safe_branch}"


@dataclass
class Extension:
    """Represents a wtd extension with its configuration."""

    name: str
    dockerfile_content: str
    compose_fragment: Dict[str, Any]
    files: Dict[str, str] = field(default_factory=dict)  # Additional files to copy
    manifest: Dict[str, Any] = field(default_factory=dict)  # Extension manifest data

    @property
    def hash(self) -> str:
        """Generate SHA256 hash for cache tagging."""
        content = f"{self.dockerfile_content}{json.dumps(self.compose_fragment, sort_keys=True)}"
        for filename, file_content in sorted(self.files.items()):
            content += f"{filename}:{file_content}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class RenvConfig:
    """Manages wtd configuration from .wtd.yml/.wtd.json files."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from repo directory."""
        for config_file in [".wtd.yml", ".wtd.yaml", ".wtd.json"]:
            config_path = self.repo_path / config_file
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        if config_file.endswith(".json"):
                            return json.load(f)
                        return yaml.safe_load(f) or {}
                except Exception as e:
                    logging.warning(f"Failed to load {config_file}: {e}")
        return {}

    @property
    def extensions(self) -> List[str]:
        """Get list of default extensions."""
        return self.config.get("extensions", [])

    @property
    def base_image(self) -> str:
        """Get base image for containers."""
        return self.config.get("base_image", "ubuntu:22.04")

    @property
    def platforms(self) -> List[str]:
        """Get target platforms for multi-arch builds."""
        return self.config.get("platforms", ["linux/amd64"])


class ExtensionManager:
    """Manages extensions and their definitions."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.extensions_dir = cache_dir / "extensions"
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        # Load extensions from global extensions directory
        self.global_extensions_dir = Path(__file__).parent.parent / "extensions"
        self._builtin_extensions = self._load_builtin_extensions()

    def _load_builtin_extensions(self) -> Dict[str, Extension]:
        """Load built-in extension definitions from the global extensions directory."""
        extensions = {}

        if not self.global_extensions_dir.exists():
            print(f"Warning: Global extensions directory not found: {self.global_extensions_dir}")
            return extensions

        for ext_dir in self.global_extensions_dir.iterdir():
            if ext_dir.is_dir():
                try:
                    extension = self._load_extension_from_dir(ext_dir.name, ext_dir)
                    extensions[ext_dir.name] = extension
                except Exception as e:
                    print(f"Warning: Failed to load extension {ext_dir.name}: {e}")

        return extensions

    def _load_extension_from_dir(self, name: str, ext_dir: Path) -> Extension:
        """Load extension from directory (used for global extensions)."""
        dockerfile_path = ext_dir / "Dockerfile"
        compose_path = ext_dir / "docker-compose.yml"

        dockerfile_content = ""
        if dockerfile_path.exists():
            dockerfile_content = dockerfile_path.read_text(encoding="utf-8")

        compose_fragment = {}
        if compose_path.exists():
            with open(compose_path, "r", encoding="utf-8") as f:
                compose_fragment = yaml.safe_load(f) or {}

        # Load manifest data if available
        manifest_path = ext_dir / "worktree_docker.yaml"
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f) or {}

        # Load any additional files (including test.sh)
        files = {}
        for file_path in ext_dir.glob("*"):
            if file_path.name not in ["Dockerfile", "docker-compose.yml", "worktree_docker.yaml"]:
                if file_path.is_file():
                    files[file_path.name] = file_path.read_text(encoding="utf-8")

        return Extension(
            name=name,
            dockerfile_content=dockerfile_content,
            compose_fragment=compose_fragment,
            files=files,
            manifest=manifest,
        )

    def get_extension(self, name: str, repo_path: Optional[Path] = None) -> Optional[Extension]:
        """Get extension by name, checking repo-local first, then built-in."""
        # Check repo-local extensions first
        if repo_path:
            local_ext_dir = repo_path / ".wtd" / "exts" / name
            if local_ext_dir.exists():
                return self._load_local_extension(name, local_ext_dir)

        # Check built-in extensions
        return self._builtin_extensions.get(name)

    def _load_local_extension(self, name: str, ext_dir: Path) -> Extension:
        """Load extension from local repository directory."""
        dockerfile_path = ext_dir / "Dockerfile"
        compose_path = ext_dir / "docker-compose.fragment.yml"

        dockerfile_content = ""
        if dockerfile_path.exists():
            dockerfile_content = dockerfile_path.read_text(encoding="utf-8")

        compose_fragment = {}
        if compose_path.exists():
            with open(compose_path, "r", encoding="utf-8") as f:
                compose_fragment = yaml.safe_load(f) or {}

        # Load any additional files
        files = {}
        for file_path in ext_dir.glob("*"):
            if file_path.name not in ["Dockerfile", "docker-compose.fragment.yml"]:
                files[file_path.name] = file_path.read_text(encoding="utf-8")

        return Extension(
            name=name,
            dockerfile_content=dockerfile_content,
            compose_fragment=compose_fragment,
            files=files,
        )

    def list_extensions(self, repo_path: Optional[Path] = None) -> List[str]:
        """List all available extensions."""
        extensions = set(self._builtin_extensions.keys())

        if repo_path:
            local_exts_dir = repo_path / ".wtd" / "exts"
            if local_exts_dir.exists():
                extensions.update(d.name for d in local_exts_dir.iterdir() if d.is_dir())

        return sorted(extensions)


def get_cache_dir() -> Path:
    """Get wtd cache directory."""
    cache_dir = os.getenv("WTD_CACHE_DIR")
    if cache_dir:
        return Path(cache_dir)
    return Path.home() / ".wtd"


def get_workspaces_dir() -> Path:
    """Get workspaces directory."""
    return get_cache_dir() / "workspaces"


def get_available_users() -> List[str]:
    """Get list of available users from workspaces directory."""
    workspaces_dir = get_workspaces_dir()
    if not workspaces_dir.exists():
        return []
    return [d.name for d in workspaces_dir.iterdir() if d.is_dir()]


def get_available_repos(user: str) -> List[str]:
    """Get list of available repositories for a user."""
    user_dir = get_workspaces_dir() / user
    if not user_dir.exists():
        return []
    return [d.name for d in user_dir.iterdir() if d.is_dir()]


def get_available_branches(repo_spec: RepoSpec) -> List[str]:
    """Get list of available branches for a repository using local refs (fast, no network calls)."""
    repo_dir = get_repo_dir(repo_spec)
    if not repo_dir.exists():
        return []

    branches = set()

    # Get branches from packed-refs file (common in bare repos)
    packed_refs_file = repo_dir / "packed-refs"
    if packed_refs_file.exists():
        try:
            with open(packed_refs_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "refs/heads/" in line:
                        # Format: <hash> refs/heads/branch_name
                        parts = line.split("refs/heads/", 1)
                        if len(parts) == 2:
                            branches.add(parts[1])
        except Exception:
            pass

    # Get branches from individual ref files in refs/heads/
    refs_heads_dir = repo_dir / "refs" / "heads"
    if refs_heads_dir.exists():
        try:
            for ref_file in refs_heads_dir.iterdir():
                if ref_file.is_file():
                    branches.add(ref_file.name)
        except Exception:
            pass

    # Also get branches from existing worktrees
    try:
        for item in repo_dir.iterdir():
            if item.is_dir() and item.name.startswith("worktree-"):
                branch = item.name[9:]  # Remove "worktree-" prefix
                # Convert hyphens back to slashes for feature branches
                if "-" in branch and branch not in [
                    "main",
                    "master",
                    "develop",
                    "staging",
                    "production",
                ]:
                    actual_branch = branch.replace("-", "/")
                else:
                    actual_branch = branch
                branches.add(actual_branch)
    except Exception:
        pass

    return sorted(list(branches))


def get_available_repo_branch_combinations() -> List[str]:
    """Get all available repo@branch combinations for fuzzy finder (fast, local-only)."""
    combinations = []

    for user in get_available_users():
        for repo in get_available_repos(user):
            repo_spec = RepoSpec(user, repo, "main")
            branches = get_available_branches(repo_spec)

            if branches:
                for branch in branches:
                    combinations.append(f"{user}/{repo}@{branch}")
            else:
                # If no branches found, still add with main
                combinations.append(f"{user}/{repo}@main")

    return sorted(combinations)


def interactive_repo_selection() -> Optional[str]:
    """Use fuzzy finder to select repo@branch combination."""
    if iterfzf is None:
        print("Error: iterfzf not available. Install with: pip install iterfzf")
        return None

    # Check if we have a terminal (stdin is a tty)
    if not sys.stdin.isatty():
        print("Error: Interactive selection requires a terminal.")
        print("Existing repo@branch combinations:")
        combinations = get_available_repo_branch_combinations()
        for combo in combinations:
            print(f"  {combo}")
        return None

    combinations = get_available_repo_branch_combinations()

    if not combinations:
        print("No existing worktrees found.")
        print("Create your first environment by running:")
        print("  wtd owner/repo@branch")
        return None

    # Use iterfzf for interactive selection
    try:
        selected = iterfzf(
            combinations,
            prompt="> ",
        )
        return selected
    except KeyboardInterrupt:
        print("\nSelection cancelled.")
        return None
    except Exception as e:
        print(f"Error during selection: {e}")
        print("Available combinations:")
        for combo in combinations:
            print(f"  {combo}")
        return None


def get_build_cache_dir(repo_spec: RepoSpec) -> Path:
    """Get build cache directory for a specific repo spec."""
    safe_branch = repo_spec.branch.replace("/", "-")
    return get_cache_dir() / "builds" / repo_spec.owner / repo_spec.repo / safe_branch


def get_repo_dir(repo_spec: RepoSpec) -> Path:
    """Get bare repository directory."""
    return get_workspaces_dir() / repo_spec.owner / repo_spec.repo


def get_worktree_dir(repo_spec: RepoSpec) -> Path:
    """Get worktree directory for a specific branch."""
    safe_branch = repo_spec.branch.replace("/", "-")
    return get_repo_dir(repo_spec) / f"worktree-{safe_branch}"


def auto_detect_extensions(repo_path: Path, extension_manager: "ExtensionManager") -> List[str]:
    """Auto-detect extensions based on patterns defined in extension manifests."""
    detected_extensions = []

    try:
        # Get all files and directories in the repository root
        if not repo_path.exists():
            return detected_extensions

        repo_files = []
        repo_directories = []

        for item in repo_path.iterdir():
            if item.is_file():
                repo_files.append(item.name)
            elif item.is_dir():
                repo_directories.append(item.name)

        # Check each extension's auto-detection patterns
        for ext_name in extension_manager.list_extensions():
            extension = extension_manager.get_extension(ext_name)
            if not extension.manifest or "auto_detect" not in extension.manifest:
                continue

            auto_detect_config = extension.manifest["auto_detect"]
            if not auto_detect_config:  # Skip if auto_detect is None or empty
                continue

            detected = False

            # Check file patterns
            if "files" in auto_detect_config:
                for pattern in auto_detect_config["files"]:
                    for filename in repo_files:
                        if re.match(pattern, filename, re.IGNORECASE):
                            detected = True
                            logging.info(
                                f"Auto-detected extension '{ext_name}' from file '{filename}'"
                            )
                            break
                    if detected:
                        break

            # Check directory patterns
            if not detected and "directories" in auto_detect_config:
                for pattern in auto_detect_config["directories"]:
                    for dirname in repo_directories:
                        if re.match(pattern, dirname, re.IGNORECASE):
                            detected = True
                            logging.info(
                                f"Auto-detected extension '{ext_name}' from directory '{dirname}'"
                            )
                            break
                    if detected:
                        break

            # Check host paths
            if not detected and "host_paths" in auto_detect_config:
                for host_path_str in auto_detect_config["host_paths"]:
                    host_path = Path(host_path_str).expanduser()
                    if host_path.exists():
                        detected = True
                        logging.info(
                            f"Auto-detected extension '{ext_name}' from host path '{host_path}'"
                        )
                        break

            if detected and ext_name not in detected_extensions:
                detected_extensions.append(ext_name)

    except Exception as e:
        logging.warning(f"Failed to auto-detect extensions: {e}")

    return detected_extensions


def setup_bare_repo(repo_spec: RepoSpec) -> Path:
    """Clone or update bare repository."""
    repo_dir = get_repo_dir(repo_spec)
    repo_url = f"git@github.com:{repo_spec.owner}/{repo_spec.repo}.git"
    https_url = f"https://github.com/{repo_spec.owner}/{repo_spec.repo}.git"
    if not repo_dir.exists():
        logging.info(f"Cloning bare repository: {repo_url}")
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["git", "clone", "--bare", repo_url, str(repo_dir)], check=True)
        except Exception as e:
            logging.warning(f"SSH clone failed ({e}), retrying with HTTPS: {https_url}")
            subprocess.run(["git", "clone", "--bare", https_url, str(repo_dir)], check=True)
    else:
        logging.info(f"Fetching updates for: {repo_url}")
        subprocess.run(["git", "-C", str(repo_dir), "fetch", "--all"], check=True)

    return repo_dir


def setup_worktree(repo_spec: RepoSpec) -> Path:
    """Set up git worktree for the specified branch."""
    repo_dir = get_repo_dir(repo_spec)
    worktree_dir = get_worktree_dir(repo_spec)

    # Ensure bare repo exists
    setup_bare_repo(repo_spec)

    if not worktree_dir.exists():
        logging.info(f"Creating worktree for branch: {repo_spec.branch}")

        # Check if branch exists, if not create it
        try:
            # Try to create worktree with existing branch
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "worktree",
                    "add",
                    str(worktree_dir),
                    repo_spec.branch,
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            # Branch doesn't exist, create new branch and worktree
            logging.info(f"Branch {repo_spec.branch} doesn't exist, creating new branch")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "worktree",
                    "add",
                    "-b",
                    repo_spec.branch,
                    str(worktree_dir),
                ],
                check=True,
            )

        time.sleep(0.1)  # Allow filesystem to sync
    else:
        logging.info(f"Worktree already exists: {worktree_dir}")

    return worktree_dir


def ensure_buildx_builder(builder_name: str = "wtd_builder") -> bool:
    """Ensure Buildx builder exists and is active."""
    try:
        # Check if builder exists
        result = subprocess.run(
            ["docker", "buildx", "inspect", builder_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # Create builder
            logging.info(f"Creating Buildx builder: {builder_name}")
            subprocess.run(
                [
                    "docker",
                    "buildx",
                    "create",
                    "--name",
                    builder_name,
                    "--driver",
                    "docker-container",
                    "--use",
                ],
                check=True,
            )
        else:
            # Use existing builder
            subprocess.run(["docker", "buildx", "use", builder_name], check=True)

        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to set up Buildx builder: {e}")
        return False


def generate_dockerfile(extensions: List[Extension], base_image: str, build_dir: Path) -> str:
    """Generate Dockerfile combining all extensions."""
    lines = [f"FROM {base_image} as base"]

    # Add each extension's Dockerfile content
    for ext in extensions:
        if ext.dockerfile_content.strip():
            lines.append(f"\n# Extension: {ext.name}")
            lines.append(ext.dockerfile_content.strip())

    # Ensure we end up in the right working directory
    lines.append("\nWORKDIR /workspace")
    lines.append('CMD ["bash"]')

    dockerfile_content = "\n".join(lines)

    # Ensure build directory exists
    build_dir.mkdir(parents=True, exist_ok=True)

    # Write Dockerfile to build directory
    dockerfile_path = build_dir / "Dockerfile"
    dockerfile_path.write_text(dockerfile_content, encoding="utf-8")

    return dockerfile_content


@dataclass
class ComposeConfig:
    """Configuration for generating compose files."""

    repo_spec: RepoSpec
    extensions: List[Extension]
    image_name: str
    work_dir: Path
    worktree_dir: Path
    repo_dir: Path
    build_dir: Optional[Path] = None


def generate_compose_file(config: ComposeConfig) -> Dict[str, Any]:
    """Generate docker-compose.yml for the environment."""
    # For git worktrees, we need to mount the worktree git metadata directory as well
    safe_branch = config.repo_spec.branch.replace("/", "-")
    worktree_git_dir = config.repo_dir / "worktrees" / f"worktree-{safe_branch}"

    # Start with base service
    service = {
        "image": config.image_name,
        "container_name": config.repo_spec.compose_project_name,
        "hostname": config.repo_spec.compose_project_name,
        "working_dir": f"/workspace/{config.repo_spec.repo}",
        "volumes": [
            f"{config.worktree_dir}:/workspace/{config.repo_spec.repo}",
            f"{config.repo_dir}:/workspace/{config.repo_spec.repo}.git",
            f"{worktree_git_dir}:/workspace/{config.repo_spec.repo}.git/worktrees/worktree-{safe_branch}",
        ],
        "environment": {
            "REPO_NAME": config.repo_spec.repo,
            "BRANCH_NAME": config.repo_spec.branch.replace("/", "-"),
        },
        "labels": {"wtd.managed": "true"},
        "stdin_open": True,
        "tty": True,
        "command": ["tail", "-f", "/dev/null"],
    }

    # Apply subfolder if specified
    if config.repo_spec.subfolder:
        service["working_dir"] = f"/workspace/{config.repo_spec.repo}/{config.repo_spec.subfolder}"

    # Merge extension compose fragments
    for ext in config.extensions:
        fragment = ext.compose_fragment
        if not fragment:
            continue

        # Special handling for SSH extension when SSH_AUTH_SOCK is not available
        if ext.name == "ssh":
            fragment = fragment.copy()  # Don't modify the original
            ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")

            # Only include SSH agent socket mount if available and valid
            if ssh_auth_sock and os.path.exists(ssh_auth_sock):
                # SSH agent socket is available, keep original fragment
                pass
            else:
                # SSH agent socket not available, filter out SSH_AUTH_SOCK references
                if "volumes" in fragment:
                    fragment["volumes"] = [
                        vol for vol in fragment["volumes"] if "${SSH_AUTH_SOCK}" not in vol
                    ]
                if "environment" in fragment and fragment["environment"]:
                    fragment["environment"] = {
                        k: v for k, v in fragment["environment"].items() if k != "SSH_AUTH_SOCK"
                    }

        # Merge volumes
        if "volumes" in fragment:
            service.setdefault("volumes", []).extend(fragment["volumes"])

        # Merge environment
        if "environment" in fragment:
            service.setdefault("environment", {}).update(fragment["environment"])

        # Set runtime if specified
        if "runtime" in fragment:
            service["runtime"] = fragment["runtime"]

        # Set network mode if specified
        if "network_mode" in fragment:
            service["network_mode"] = fragment["network_mode"]

        # Merge build args if specified
        if "build" in fragment:
            if "build" not in service:
                service["build"] = {"context": ".", "dockerfile": "Dockerfile"}
            if "args" in fragment["build"]:
                service["build"].setdefault("args", {}).update(fragment["build"]["args"])

    # If we have build args, enable building
    if any(ext.compose_fragment.get("build", {}).get("args") for ext in config.extensions):
        service["build"] = service.get("build", {"context": ".", "dockerfile": "Dockerfile"})

    compose_config = {"services": {"dev": service}}

    # Write compose file to build directory to keep worktree clean
    # Use work_dir as fallback for cases where we don't have a separate build dir
    compose_dir = config.build_dir if config.build_dir is not None else config.work_dir
    if config.build_dir is not None:
        config.build_dir.mkdir(parents=True, exist_ok=True)

    compose_path = compose_dir / "docker-compose.yml"
    with open(compose_path, "w", encoding="utf-8") as f:
        yaml.dump(compose_config, f, default_flow_style=False)

    return compose_config


def generate_bake_file(
    extensions: List[Extension], base_image: str, platforms: List[str], build_dir: Path
) -> str:
    """Generate docker-bake.hcl file for Buildx."""
    # Create targets for each extension layer
    targets = []

    # Convert platforms list to proper HCL array syntax
    platforms_hcl = "[" + ", ".join(f'"{platform}"' for platform in platforms) + "]"

    current_image = base_image
    for ext in extensions:
        if not ext.dockerfile_content.strip():
            continue

        target_name = f"ext-{ext.name}"
        target = f"""
target "{target_name}" {{
    context = "."
    dockerfile = "Dockerfile.{ext.name}"
    tags = ["wtd/{ext.name}:{ext.hash}"]
    platforms = {platforms_hcl}
    cache-from = ["type=local,src=.buildx-cache"]
    cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}}"""
        targets.append(target)

        # Ensure build directory exists
        build_dir.mkdir(parents=True, exist_ok=True)

        # Write individual Dockerfile for this extension
        ext_dockerfile = f"FROM {current_image}\n{ext.dockerfile_content}"
        dockerfile_path = build_dir / f"Dockerfile.{ext.name}"
        dockerfile_path.write_text(ext_dockerfile, encoding="utf-8")

        current_image = f"wtd/{ext.name}:{ext.hash}"

    # Final target combining all extensions
    final_target = f"""
target "final" {{
    context = "."
    dockerfile = "Dockerfile"
    tags = ["wtd/final:{"-".join(ext.hash for ext in extensions)}"]
    platforms = {platforms_hcl}
    cache-from = ["type=local,src=.buildx-cache"]
    cache-to = ["type=local,dest=.buildx-cache,mode=max"]
}}"""
    targets.append(final_target)

    bake_content = "\n".join(targets)

    # Write bake file
    bake_path = build_dir / "docker-bake.hcl"
    bake_path.write_text(bake_content, encoding="utf-8")

    return bake_content


def should_rebuild_image(
    image_name: str,
    extensions: List[Extension],  # pylint: disable=unused-argument
) -> bool:
    """Check if image needs rebuilding based on extension hashes."""
    try:
        # Check if image exists
        result = subprocess.run(
            ["docker", "image", "inspect", image_name], capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            return True  # Image doesn't exist

        # Check if any extension hash changed
        # This is a simplified check - in production you'd want to store metadata
        return False

    except subprocess.CalledProcessError:
        return True


def build_image_with_bake(
    build_dir: Path, builder_name: str = "wtd_builder", load: bool = True, nocache: bool = False
) -> bool:
    """Build images using docker buildx bake."""
    try:
        cmd = ["docker", "buildx", "bake", "--builder", builder_name]
        if load:
            cmd.append("--load")
        if nocache:
            cmd.append("--no-cache")
        # Always build the 'final' target, never 'default'
        cmd.append("final")
        print(f"Building with bake: {' '.join(cmd)}", flush=True)
        logging.info(f"Building with bake: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=build_dir, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to build with bake: {e}")
        return False


def is_container_usable(repo_spec: RepoSpec, work_dir: Path) -> bool:
    """Check if the existing container is usable and accessible."""
    container_name = repo_spec.compose_project_name

    try:
        # Check if container exists and is running
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False  # Container doesn't exist

        status = result.stdout.strip()
        if status != "running":
            logging.info(f"Container {container_name} exists but is not running (status: {status})")
            return False

        # Try to execute a simple command to test accessibility
        env = os.environ.copy()
        env["COMPOSE_PROJECT_NAME"] = repo_spec.compose_project_name

        test_cmd = ["docker", "compose", "exec", "-T", "dev", "echo", "test"]
        test_result = subprocess.run(
            test_cmd, cwd=work_dir, env=env, capture_output=True, check=False, timeout=5
        )

        if test_result.returncode == 0:
            logging.info(f"Reusing existing container: {container_name}")
            return True
        logging.info(f"Container {container_name} is not accessible, will recreate")
        return False

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logging.info(f"Failed to check container {container_name} accessibility")
        return False


def cleanup_stale_container(repo_spec: RepoSpec) -> None:
    """Clean up stale containers that are not usable."""
    container_name = repo_spec.compose_project_name
    try:
        # Check if container exists
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            logging.info(f"Removing stale container: {container_name}")
            # Stop and remove the container
            subprocess.run(["docker", "stop", container_name], check=False, capture_output=True)
            subprocess.run(["docker", "rm", container_name], check=False, capture_output=True)
    except subprocess.CalledProcessError:
        pass  # Container doesn't exist or already removed


def run_compose_service(
    compose_dir: Path, repo_spec: RepoSpec, command: Optional[List[str]] = None
) -> int:
    """Run Docker Compose service and optionally execute command."""
    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = repo_spec.compose_project_name
    env["USER_ID"] = str(os.getuid())
    env["GROUP_ID"] = str(os.getgid())

    try:
        # Check if we can reuse existing container
        # Use compose_dir for container accessibility test since that's where compose file is
        container_is_usable = is_container_usable(repo_spec, compose_dir)

        if not container_is_usable:
            # Clean up stale container if it exists but is not usable
            cleanup_stale_container(repo_spec)

            # Start the service
            subprocess.run(["docker", "compose", "up", "-d"], cwd=compose_dir, env=env, check=True)

            # Fix git worktree configuration in the container
            safe_branch = repo_spec.branch.replace("/", "-")
            fix_git_cmd = [
                "docker",
                "compose",
                "exec",
                "-T",
                "dev",
                "bash",
                "-c",
                f"echo 'gitdir: /workspace/{repo_spec.repo}.git/worktrees/worktree-{safe_branch}' > /workspace/{repo_spec.repo}/.git",
            ]
            subprocess.run(fix_git_cmd, cwd=compose_dir, env=env, check=False)

        if command:
            # Execute command in running container
            if len(command) == 1 and (
                any(char in command[0] for char in [";", "&&", "||", "|"])
                or command[0].startswith("bash -c")
                or "'" in command[0]
                or '"' in command[0]
            ):
                # Complex shell command or bash -c format
                exec_cmd = ["docker", "compose", "exec", "dev", "bash", "-c", command[0]]
            else:
                # Simple command
                exec_cmd = ["docker", "compose", "exec", "dev"] + command

            return subprocess.run(exec_cmd, cwd=compose_dir, env=env, check=False).returncode
        # Interactive shell
        exec_cmd = ["docker", "compose", "exec", "dev", "bash"]
        return subprocess.run(exec_cmd, cwd=compose_dir, env=env, check=False).returncode

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to run compose service: {e}")
        return e.returncode


def list_active_containers() -> List[Dict[str, str]]:
    """List active wtd containers."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "label=com.docker.compose.project",
                "--format",
                "table {{.Names}}\\t{{.Status}}\\t{{.Image}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        containers = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 3:
                    containers.append({"name": parts[0], "status": parts[1], "image": parts[2]})
        return containers
    except subprocess.CalledProcessError:
        return []


def destroy_environment(repo_spec: RepoSpec) -> bool:
    """Destroy Docker Compose environment for repo/branch."""
    build_dir = get_build_cache_dir(repo_spec)
    if not build_dir.exists():
        logging.warning(f"Environment not found: {repo_spec}")
        return False

    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = repo_spec.compose_project_name

    try:
        subprocess.run(["docker", "compose", "down", "-v"], cwd=build_dir, env=env, check=True)
        logging.info(f"Destroyed environment: {repo_spec}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to destroy environment: {e}")
        return False


@dataclass
class LaunchConfig:
    """Configuration for launching environments."""

    repo_spec: RepoSpec
    extensions: List[str]
    command: Optional[List[str]] = None
    rebuild: bool = False
    nocache: bool = False
    no_gui: bool = False
    no_gpu: bool = False
    platforms: Optional[List[str]] = None
    builder_name: str = "wtd_builder"


def launch_environment(config: LaunchConfig) -> int:
    """Launch development environment for repository/branch."""
    platforms = config.platforms or ["linux/amd64"]

    # Set up worktree
    worktree_dir = setup_worktree(config.repo_spec)
    repo_dir = get_repo_dir(config.repo_spec)

    # Load repo configuration
    repo_config = RenvConfig(worktree_dir)

    # Load extension definitions first so we can use them for auto-detection
    ext_manager = ExtensionManager(get_cache_dir())

    # Auto-detect extensions based on repository contents using extension manifests
    auto_detected = auto_detect_extensions(worktree_dir, ext_manager)
    if auto_detected:
        print(f"Auto-detected extensions: {', '.join(auto_detected)}")

    # Merge extensions: manual config + repo config + auto-detected
    # Remove duplicates while preserving order
    all_extensions = []
    for ext in list(config.extensions) + repo_config.extensions + auto_detected:
        if ext not in all_extensions:
            all_extensions.append(ext)

    if config.no_gui and "x11" in all_extensions:
        all_extensions.remove("x11")
    if config.no_gpu and "nvidia" in all_extensions:
        all_extensions.remove("nvidia")

    # Add required base extensions
    if "base" not in all_extensions:
        all_extensions.insert(0, "base")
    if "user" not in all_extensions:
        all_extensions.append("user")

    # Load extensions
    loaded_extensions = []
    print(f"Loading extensions: {', '.join(all_extensions)}")
    for ext_name in all_extensions:
        ext = ext_manager.get_extension(ext_name, worktree_dir)
        if ext:
            loaded_extensions.append(ext)
            print(f"✓ Loaded extension: {ext_name}")
        else:
            logging.warning(f"Extension not found: {ext_name}")
            print(f"✗ Extension not found: {ext_name}")

    # Generate combined hash for image name
    combined_hash = hashlib.sha256(
        "".join(ext.hash for ext in loaded_extensions).encode()
    ).hexdigest()[:12]

    image_name = f"wtd/{config.repo_spec.repo}:{combined_hash}"
    base_image = repo_config.base_image

    # Check if rebuild needed: always rebuild if --rebuild or --nocache is set
    if config.rebuild or config.nocache or should_rebuild_image(image_name, loaded_extensions):
        # Ensure Buildx builder
        if not ensure_buildx_builder(config.builder_name):
            return 1

        # Get build cache directory to keep worktree clean
        build_dir = get_build_cache_dir(config.repo_spec)

        # Generate build files in build cache directory
        generate_dockerfile(loaded_extensions, base_image, build_dir)
        generate_bake_file(loaded_extensions, base_image, platforms, build_dir)

        # Build image
        if not build_image_with_bake(build_dir, config.builder_name, nocache=config.nocache):
            return 1

        logging.info(f"Built image: {image_name}")

        # Always remove any existing container if rebuilding (for nocache or rebuild)
        cleanup_stale_container(config.repo_spec)

    # Get build cache directory for compose file
    build_dir = get_build_cache_dir(config.repo_spec)

    # Generate compose file
    compose_config = ComposeConfig(
        repo_spec=config.repo_spec,
        extensions=loaded_extensions,
        image_name=image_name,
        work_dir=worktree_dir,
        worktree_dir=worktree_dir,
        repo_dir=repo_dir,
        build_dir=build_dir,
    )
    generate_compose_file(compose_config)

    # Run environment using build directory for compose file
    return run_compose_service(build_dir, config.repo_spec, config.command)


def cmd_launch(args) -> int:
    """Launch command implementation."""
    repo_spec = RepoSpec.parse(args.repo_spec)
    config = LaunchConfig(
        repo_spec=repo_spec,
        extensions=args.extensions or [],
        command=args.command or None,
        rebuild=args.rebuild,
        nocache=args.nocache,
        no_gui=args.no_gui,
        no_gpu=args.no_gpu,
        platforms=args.platforms.split(",") if args.platforms else None,
        builder_name=args.builder,
    )
    return launch_environment(config)


def cmd_list(args) -> int:  # pylint: disable=unused-argument
    """List active environments."""
    del args  # Unused parameter
    containers = list_active_containers()
    if not containers:
        print("No active environments found.")
        return 0

    print("Active environments:")
    for container in containers:
        print(f"  {container['name']}: {container['status']}")
    return 0


def cmd_install(args) -> int:  # pylint: disable=unused-argument
    """Install shell completion scripts."""
    import os  # pylint: disable=reimported,redefined-outer-name

    # Bash completion script
    bash_completion = """# wtd bash completion
_wtd_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Don't complete after flags that take arguments
    case "${prev}" in
        --extensions|-e|--builder|--platforms|--log-level)
            return 0
            ;;
    esac
    
    # If current word starts with -, complete options
    if [[ "${cur}" == -* ]]; then
        local opts="--help -h --extensions -e --list --prune --ext-list --doctor --install --rebuild --nocache --no-gui --no-gpu --builder --platforms --log-level"
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi
    
    # Handle repo specifications
    if [[ "${cur}" == *@* ]]; then
        # Has @, complete branches
        local owner_repo="${cur%@*}"
        local branch_prefix="${cur##*@}"
        local owner="${owner_repo%/*}"
        local repo="${owner_repo##*/}"
        
        if [[ -d ~/.wtd/workspaces/${owner}/${repo} ]]; then
            local completions=()
            
            # Get remote branches
            if command -v git >/dev/null 2>&1; then
                while IFS= read -r branch; do
                    if [[ -n "${branch}" && "${branch}" == "${branch_prefix}"* ]]; then
                        completions+=("${owner_repo}@${branch}")
                    fi
                done < <(git -C ~/.wtd/workspaces/${owner}/${repo} ls-remote --heads origin 2>/dev/null | sed 's/.*refs\\/heads\\///' | sort -u)
            fi
            
            # Get local worktree branches
            while IFS= read -r branch; do
                if [[ -n "${branch}" && "${branch}" == "${branch_prefix}"* ]]; then
                    completions+=("${owner_repo}@${branch}")
                fi
            done < <(find ~/.wtd/workspaces/${owner}/${repo} -name "worktree-*" -type d 2>/dev/null | sed 's|.*worktree-||' | sort -u)
            
            COMPREPLY=("${completions[@]}")
        fi
    elif [[ "${cur}" == */* ]]; then
        # Contains slash but no @, complete repo names
        local owner="${cur%/*}"
        local repo_prefix="${cur##*/}"
        
        if [[ -d ~/.wtd/workspaces/${owner} ]]; then
            local completions=()
            while IFS= read -r repo; do
                if [[ -n "${repo}" && "${repo}" == "${repo_prefix}"* ]]; then
                    completions+=("${owner}/${repo}")
                fi
            done < <(find ~/.wtd/workspaces/${owner} -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null | sort -u)
            
            COMPREPLY=("${completions[@]}")
            # Don't add space after repo name so user can type @branch
            if [[ ${#completions[@]} -gt 0 ]]; then
                compopt -o nospace
            fi
        fi
    else
        # No slash yet - could be command or user name
        local completions=()
        
        # Add commands if this looks like a command
        local has_repo_arg=0
        for word in "${COMP_WORDS[@]:1}"; do
            if [[ "${word}" == */* && "${word}" != -* ]]; then
                has_repo_arg=1
                break
            fi
        done
        
        if [[ ${has_repo_arg} -eq 0 ]]; then
            if [[ "launch" == "${cur}"* ]]; then completions+=("launch"); fi
            if [[ "list" == "${cur}"* ]]; then completions+=("list"); fi
            if [[ "prune" == "${cur}"* ]]; then completions+=("prune"); fi
            if [[ "help" == "${cur}"* ]]; then completions+=("help"); fi
        fi
        
        # Add user names if we have workspaces
        if [[ -d ~/.wtd/workspaces ]]; then
            while IFS= read -r user; do
                if [[ -n "${user}" && "${user}" == "${cur}"* ]]; then
                    completions+=("${user}/")
                fi
            done < <(find ~/.wtd/workspaces -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null | sort -u)
        fi
        
        # Set compopt to not add trailing space for directory-like completions
        COMPREPLY=("${completions[@]}")
        if [[ ${#completions[@]} -eq 1 && "${completions[0]}" == */ ]]; then
            compopt -o nospace
        fi
    fi
}
complete -F _wtd_complete wtd
"""

    # Zsh completion script
    zsh_completion = """#compdef wtd
_wtd() {
    local context state line
    typeset -A opt_args
    
    _arguments \\
        '1: :->repo_spec' \\
        '*: :->args'
        
    case $state in
        repo_spec)
            _wtd_repo_spec
            ;;
        args)
            # Complete remaining arguments as commands
            _command_names
            ;;
    esac
}

_wtd_repo_spec() {
    local current=${words[CURRENT]}
    
    if [[ $current == *@* ]]; then
        # Complete branches after @
        local owner_repo="${current%@*}"
        local branch_prefix="${current##*@}"
        local owner="${owner_repo%/*}"
        local repo="${owner_repo##*/}"
        
        if [[ -d ~/.wtd/workspaces/$owner/$repo ]]; then
            local branches
            branches=($(git -C ~/.wtd/workspaces/$owner/$repo ls-remote --heads origin 2>/dev/null | sed 's/.*refs\\/heads\\///'))
            # Add worktree branches
            branches+=($(find ~/.wtd/workspaces/$owner/$repo -name "worktree-*" -type d 2>/dev/null | sed 's|.*worktree-||'))
            
            local completions
            for branch in $branches; do
                completions+=("$owner_repo@$branch:branch $branch")
            done
            _describe 'branches' completions
        fi
    elif [[ $current == */* ]]; then
        # Complete repo names after owner/
        local owner="${current%/*}"
        local repo_prefix="${current##*/}"
        
        if [[ -d ~/.wtd/workspaces/$owner ]]; then
            local repos
            repos=($(find ~/.wtd/workspaces/$owner -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null))
            
            local completions
            for repo in $repos; do
                completions+=("$owner/$repo:repository $owner/$repo")
            done
            _describe 'repositories' completions
        fi
    else
        # Complete commands and user names
        local commands=(launch list prune help)
        local users
        if [[ -d ~/.wtd/workspaces ]]; then
            users=($(find ~/.wtd/workspaces -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null))
        fi
        
        local completions
        for cmd in $commands; do
            completions+=("$cmd:command")
        done
        for user in $users; do
            completions+=("$user/:user $user")
        done
        _describe 'commands and users' completions
    fi
}

_wtd "$@"
"""

    # Fish completion script
    fish_completion = """# wtd fish completion
complete -c wtd -f

# Commands
complete -c wtd -n "not __fish_seen_subcommand_from launch list prune help" -a "launch" -d "Launch container for repo and branch"
complete -c wtd -n "not __fish_seen_subcommand_from launch list prune help" -a "list" -d "Show active worktrees and containers"  
complete -c wtd -n "not __fish_seen_subcommand_from launch list prune help" -a "prune" -d "Remove unused containers and images"
complete -c wtd -n "not __fish_seen_subcommand_from launch list prune help" -a "help" -d "Show help message"

# Options
complete -c wtd -l install -d "Install shell auto-completion"
complete -c wtd -l rebuild -d "Force rebuild of container"
complete -c wtd -l nocache -d "Disable Buildx cache"
complete -c wtd -l no-gui -d "Disable X11/GUI support"
complete -c wtd -l no-gpu -d "Disable GPU passthrough"
complete -c wtd -l log-level -d "Set log level" -xa "debug info warn error"

# Dynamic completion functions
function __wtd_complete_owners
    if test -d ~/.wtd/workspaces
        find ~/.wtd/workspaces -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null
    end
end

function __wtd_complete_repos
    set -l current (commandline -ct)
    set -l owner (string split -f 1 / $current)
    if test -d ~/.wtd/workspaces/$owner
        find ~/.wtd/workspaces/$owner -maxdepth 1 -mindepth 1 -type d -exec basename {} \\; 2>/dev/null | string replace -r "^" "$owner/"
    end
end

function __wtd_complete_branches
    set -l current (commandline -ct)
    set -l owner_repo (string split -f 1 @ $current)
    set -l owner (string split -f 1 / $owner_repo)
    set -l repo (string split -f 2 / $owner_repo)
    if test -d ~/.wtd/workspaces/$owner/$repo
        # Get remote branches
        git -C ~/.wtd/workspaces/$owner/$repo ls-remote --heads origin 2>/dev/null | sed 's/.*refs\\/heads\\///' | string replace -r "^" "$owner_repo@"
        # Get worktree branches
        find ~/.wtd/workspaces/$owner/$repo -name "worktree-*" -type d 2>/dev/null | sed 's|.*worktree-||' | string replace -r "^" "$owner_repo@"
    end
end

# Repository completion based on current input
complete -c wtd -n "not string match -q '*/*' (commandline -ct); and not string match -q '*@*' (commandline -ct)" -a "(__wtd_complete_owners)" -d "Owner"
complete -c wtd -n "string match -q '*/*' (commandline -ct); and not string match -q '*@*' (commandline -ct)" -a "(__wtd_complete_repos)" -d "Repository"  
complete -c wtd -n "string match -q '*@*' (commandline -ct)" -a "(__wtd_complete_branches)" -d "Branch"

# Legacy repo@branch completion for existing worktrees
if test -d ~/.wtd/workspaces
    for combo in (find ~/.wtd/workspaces -name "worktree-*" -type d 2>/dev/null | sed 's|.*workspaces/||; s|/worktree-|@|' | sort -u)
        complete -c wtd -a "$combo" -d "Existing worktree"
    end
end
"""

    # Detect shell and install appropriate completion
    shell = os.environ.get("SHELL", "").split("/")[-1]
    home = os.path.expanduser("~")

    success = False

    if shell == "bash":
        # Install bash completion
        bash_completion_dir = f"{home}/.bash_completion.d"
        os.makedirs(bash_completion_dir, exist_ok=True)
        completion_file = f"{bash_completion_dir}/wtd"

        with open(completion_file, "w", encoding="utf-8") as f:
            f.write(bash_completion)

        # Check if .bashrc sources .bash_completion.d directory
        bashrc_path = f"{home}/.bashrc"
        bashrc_content = ""
        if os.path.exists(bashrc_path):
            with open(bashrc_path, "r", encoding="utf-8") as f:
                bashrc_content = f.read()

        # Add sourcing of .bash_completion.d if not present
        bash_completion_d_source = """
# Source bash completion files from ~/.bash_completion.d/
if [ -d ~/.bash_completion.d ]; then
    for file in ~/.bash_completion.d/*; do
        [ -r "$file" ] && . "$file"
    done
fi"""

        needs_update = False
        if ".bash_completion.d" not in bashrc_content:
            needs_update = True
        elif "for file in ~/.bash_completion.d" not in bashrc_content:
            needs_update = True

        if needs_update:
            with open(bashrc_path, "a", encoding="utf-8") as f:
                f.write(bash_completion_d_source)
            print(f"✓ Bash completion installed to {completion_file}")
            print("✓ Added .bash_completion.d sourcing to ~/.bashrc")
            print("Run 'source ~/.bashrc' or restart your terminal to enable completion")
        else:
            print(f"✓ Bash completion installed to {completion_file}")
            print("✓ .bashrc already configured to load completion files")
            print("Run 'source ~/.bashrc' or restart your terminal to enable completion")

        success = True

    elif shell == "zsh":
        # Install zsh completion
        zsh_completion_dir = f"{home}/.zsh/completions"
        os.makedirs(zsh_completion_dir, exist_ok=True)
        completion_file = f"{zsh_completion_dir}/_wtd"

        with open(completion_file, "w", encoding="utf-8") as f:
            f.write(zsh_completion)

        print(f"✓ Zsh completion installed to {completion_file}")
        print("Add 'fpath=(~/.zsh/completions $fpath)' to your ~/.zshrc if not already present")
        print("Run 'autoload -U compinit && compinit' or restart your terminal")
        success = True

    elif shell == "fish":
        # Install fish completion
        fish_completion_dir = f"{home}/.config/fish/completions"
        os.makedirs(fish_completion_dir, exist_ok=True)
        completion_file = f"{fish_completion_dir}/wtd.fish"

        with open(completion_file, "w", encoding="utf-8") as f:
            f.write(fish_completion)

        print(f"✓ Fish completion installed to {completion_file}")
        print("Restart your fish shell to enable completion")
        success = True

    else:
        print(f"✗ Unknown shell: {shell}")
        print("Supported shells: bash, zsh, fish")
        print("You can manually install completion scripts:")
        print("\nBash completion script:")
        print(bash_completion)
        print("\nZsh completion script:")
        print(zsh_completion)
        print("\nFish completion script:")
        print(fish_completion)

    return 0 if success else 1


def cmd_prune(args) -> int:
    """Prune containers, images, volumes, and wtd folders."""
    try:
        if hasattr(args, "repo_spec") and args.repo_spec:
            # Selective pruning for specific repo spec
            repo_spec = RepoSpec.parse(args.repo_spec)
            return prune_repo_environment(repo_spec)
        # Prune everything
        return prune_all()
    except Exception as e:
        logging.error(f"Failed to prune: {e}")
        return 1


def prune_repo_environment(repo_spec: RepoSpec) -> int:
    """Prune containers, images, and worktree for a specific repo spec."""
    try:
        container_name = repo_spec.compose_project_name
        worktree_dir = get_worktree_dir(repo_spec)

        # Stop and remove container
        print(f"Removing container: {container_name}")
        subprocess.run(["docker", "stop", container_name], check=False, capture_output=True)
        subprocess.run(["docker", "rm", container_name], check=False, capture_output=True)

        # Remove associated images (wtd images for this repo)
        removed_images = []
        try:
            result = subprocess.run(
                ["docker", "images", "--filter", f"reference=wtd/{repo_spec.repo}*", "-q"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                image_ids = result.stdout.strip().split("\n")
                # Get image names before removing
                for image_id in image_ids:
                    name_result = subprocess.run(
                        ["docker", "inspect", "--format", "{{.RepoTags}}", image_id],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if name_result.stdout.strip():
                        removed_images.append(name_result.stdout.strip())

                subprocess.run(
                    ["docker", "rmi", "-f"] + image_ids, check=False, capture_output=True
                )
                for image in removed_images:
                    print(f"Removed image: {image}")
        except subprocess.CalledProcessError:
            pass

        # Clean up compose volumes first from build directory
        build_dir = get_build_cache_dir(repo_spec)
        if build_dir.exists():
            env = os.environ.copy()
            env["COMPOSE_PROJECT_NAME"] = repo_spec.compose_project_name
            subprocess.run(
                ["docker", "compose", "down", "-v"],
                cwd=build_dir,
                env=env,
                check=False,
                capture_output=True,
            )

        # Remove worktree directory
        if worktree_dir.exists():
            print(f"Removing worktree: {worktree_dir}")
            subprocess.run(["rm", "-rf", str(worktree_dir)], check=False)

        # Remove build cache directory
        if build_dir.exists():
            print(f"Removing build cache: {build_dir}")
            subprocess.run(["rm", "-rf", str(build_dir)], check=False)

        # Clean up git worktree registration if repo exists
        repo_dir = get_repo_dir(repo_spec)
        if repo_dir.exists():
            safe_branch = repo_spec.branch.replace("/", "-")
            worktree_name = f"worktree-{safe_branch}"
            subprocess.run(
                ["git", "-C", str(repo_dir), "worktree", "remove", worktree_name],
                check=False,
                capture_output=True,
            )

        logging.info(f"Pruned environment for {repo_spec}")
        return 0
    except Exception as e:
        logging.error(f"Failed to prune repo environment: {e}")
        return 1


def prune_all() -> int:
    """Prune all wtd-related containers, images, and folders."""
    try:
        removed_containers = []
        removed_images = []

        # Get all wtd-related containers and remove them
        try:
            # Only prune containers with the wtd.managed label
            result = subprocess.run(
                ["docker", "ps", "-aq", "--filter", "label=wtd.managed=true"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                container_ids = result.stdout.strip().split("\n")
                for container_id in container_ids:
                    inspect_result = subprocess.run(
                        ["docker", "inspect", "--format", "{{.Name}}", container_id],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if inspect_result.stdout.strip():
                        container_name = inspect_result.stdout.strip().lstrip("/")
                        print(f"Removing container: {container_name}")
                        subprocess.run(
                            ["docker", "stop", container_id], check=False, capture_output=True
                        )
                        subprocess.run(
                            ["docker", "rm", "-f", container_id],
                            check=False,
                            capture_output=True,
                        )
                        removed_containers.append(container_name)
        except subprocess.CalledProcessError:
            pass

        # Get wtd-managed images and remove them
        try:
            # Only prune images with the wtd.managed label
            result = subprocess.run(
                ["docker", "images", "-q", "--filter", "label=wtd.managed=true"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                image_ids = result.stdout.strip().split("\n")
                for image_id in image_ids:
                    name_result = subprocess.run(
                        ["docker", "inspect", "--format", "{{.RepoTags}}", image_id],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if name_result.stdout.strip():
                        image_tags = name_result.stdout.strip()
                        print(f"Removing image: {image_tags}")
                        removed_images.append(image_tags)
                        subprocess.run(
                            ["docker", "rmi", "-f", image_id], check=False, capture_output=True
                        )
        except subprocess.CalledProcessError:
            pass

        # Remove wtd cache and workspaces folders
        cache_dir = str(get_cache_dir())
        workspaces_dir = str(get_workspaces_dir())
        for folder in [cache_dir, workspaces_dir]:
            if os.path.exists(folder):
                print(f"Removing directory: {folder}")
                subprocess.run(["rm", "-rf", folder], check=False)

        # Print summary
        if removed_containers or removed_images:
            print(f"Pruned {len(removed_containers)} containers and {len(removed_images)} images")
        else:
            print("No wtd resources found to prune")

        logging.info("Pruned all wtd-related containers, images, and folders")
        return 0
    except Exception as e:
        logging.error(f"Failed to prune all wtd resources: {e}")
        return 1


def cmd_ext(args) -> int:
    """Extension management command."""
    ext_manager = ExtensionManager(get_cache_dir())

    if args.ext_action == "list":
        extensions = ext_manager.list_extensions()
        print("Available extensions:")
        for ext in extensions:
            print(f"  {ext}")
        return 0

    # TODO: Implement add/remove functionality
    logging.error("Extension add/remove not yet implemented")
    return 1


def cmd_doctor(args) -> int:  # pylint: disable=unused-argument
    """Run environment diagnostics."""
    del args  # Unused parameter
    checks = [
        (
            "Docker",
            lambda: subprocess.run(["docker", "--version"], capture_output=True, check=True),
        ),
        (
            "Docker Compose",
            lambda: subprocess.run(
                ["docker", "compose", "version"], capture_output=True, check=True
            ),
        ),
        (
            "Docker Buildx",
            lambda: subprocess.run(
                ["docker", "buildx", "version"], capture_output=True, check=True
            ),
        ),
        ("Git", lambda: subprocess.run(["git", "--version"], capture_output=True, check=True)),
    ]

    all_good = True
    for name, check_func in checks:
        try:
            check_func()
            print(f"✓ {name}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {name}")
            all_good = False

    return 0 if all_good else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="wtd",
        usage="wtd [OPTIONS] [-e ext1 ext2 ...] <owner>/<repo>[@<branch>][#<subfolder>] [command...]",
        description="""A development environment launcher using Docker, Git worktrees, and Buildx/Bake.

Clones and manages repositories in isolated git worktrees, builds cached container environments using Docker Buildx + Bake, and launches fully configured shells or commands inside each branch-specific container workspace.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  wtd blooop/test_wtd@main
  wtd -e uv blooop/test_wtd@feature/foo
  wtd -e git uv blooop/test_wtd@main#src
  wtd blooop/test_wtd git status
  wtd -e pixi blooop/test_wtd@dev "bash -c 'git pull && make test'"

Commands:
  launch       Launch container for the given repo and branch (default behavior)
  list         Show active worktrees and running containers
  prune        Remove unused containers and cached images
  help         Show this help message

Arguments:
  -e, --extensions EXT [EXT ...]
                   Extensions to enable (e.g. git, uv, pixi, nvidia, x11)
  <owner>/<repo>[@<branch>][#<subfolder>]
                   GitHub repository specifier:
                   - owner/repo (default branch = main)
                   - @branch    (e.g. main, feature/foo)
                   - #subfolder (working directory after container start)
  [command ...]    Command to run inside the container

Environment:
  WTD_CACHE_DIR            Set custom cache directory (default: ~/.wtd/)
  WTD_BASE_IMAGE           Override base image used for environments
  WTD_CACHE_REGISTRY       Push/pull extension build cache to a registry

Notes:
  - Worktrees are stored under ~/.wtd/workspaces/<owner>/<repo>/worktree-<branch>
  - Extensions can be configured via .wtd.yml in the repo
  - Extension images are hashed and reused across repos/branches automatically
  - Supports Docker socket sharing (DOOD) and Docker-in-Docker (DinD) setups
""",
    )

    # Add extensions as a global option that comes before repo_spec
    parser.add_argument(
        "--extensions",
        "-e",
        action="append",
        help="Extensions to enable (e.g. git, uv, pixi, nvidia, x11). Can be used multiple times.",
    )

    # Add special command flags
    parser.add_argument(
        "--list", action="store_true", help="Show active worktrees and running containers"
    )
    parser.add_argument(
        "--prune",
        nargs="?",
        const="all",
        help="Remove unused containers and cached images (optionally for specific repo)",
    )
    parser.add_argument("--ext-list", action="store_true", help="List available extensions")
    parser.add_argument("--doctor", action="store_true", help="Run diagnostics")

    # Main positional arguments for the default launch behavior
    parser.add_argument(
        "repo_spec", nargs="?", help="Repository specification: owner/repo[@branch][#subfolder]"
    )
    parser.add_argument("command", nargs="*", help="Command to execute in the container")

    # Build and runtime options
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install shell auto-completion script (bash/zsh/fish)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild of container and extensions, even if cached",
    )
    parser.add_argument(
        "--nocache",
        action="store_true",
        help="Disable use of Buildx cache (useful for clean debugging)",
    )
    parser.add_argument(
        "--no-gui", action="store_true", help="Disable X11 socket mounting and GUI support"
    )
    parser.add_argument(
        "--no-gpu", action="store_true", help="Disable GPU passthrough and NVIDIA runtime"
    )
    parser.add_argument(
        "--builder",
        default="wtd_builder",
        help="Use a custom Buildx builder name (default: wtd_builder)",
    )
    parser.add_argument(
        "--platforms", help="Target platforms for Buildx (e.g. linux/amd64,linux/arm64)"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warn", "error"],
        default="info",
        help="Set log verbosity: debug, info, warn, error (default: info)",
    )

    # Handle --install flag specially
    if "--install" in sys.argv:
        return cmd_install(argparse.Namespace())

    # Parse known args first to avoid conflicts with container command flags
    parsed_args, unknown_args = parser.parse_known_args()

    # If we have unknown args and a repo_spec, treat unknown args as part of the command
    if unknown_args and parsed_args.repo_spec:
        # Combine existing command with unknown args
        if parsed_args.command:
            parsed_args.command.extend(unknown_args)
        else:
            parsed_args.command = unknown_args

    # Set up logging
    log_level = getattr(logging, parsed_args.log_level.upper())
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Handle special command flags first
    if parsed_args.list:
        return cmd_list(parsed_args)

    if parsed_args.prune is not None:
        # Create a namespace with repo_spec for prune command
        prune_args = argparse.Namespace()
        prune_args.repo_spec = parsed_args.prune if parsed_args.prune != "all" else None
        return cmd_prune(prune_args)

    if parsed_args.ext_list:
        return cmd_ext(argparse.Namespace(ext_action="list", ext_name=None))

    if parsed_args.doctor:
        return cmd_doctor(parsed_args)

    # Default behavior - launch environment
    if not parsed_args.repo_spec:
        # Try interactive selection if no repo_spec provided
        selected_repo = interactive_repo_selection()
        if not selected_repo:
            parser.print_help()
            return 1
        parsed_args.repo_spec = selected_repo

    # Convert to launch command format
    launch_args = argparse.Namespace()
    launch_args.repo_spec = parsed_args.repo_spec
    launch_args.command = parsed_args.command
    # Flatten extensions list since they come from action="append"
    launch_args.extensions = parsed_args.extensions or []
    launch_args.rebuild = parsed_args.rebuild
    launch_args.nocache = parsed_args.nocache
    launch_args.no_gui = parsed_args.no_gui
    launch_args.no_gpu = parsed_args.no_gpu
    launch_args.builder = parsed_args.builder
    launch_args.platforms = parsed_args.platforms

    return cmd_launch(launch_args)


if __name__ == "__main__":
    sys.exit(main())
