"""Shell autocompletion support for wtd."""

import os


def install_shell_completion() -> int:
    """Install shell completion scripts for the current shell."""
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
