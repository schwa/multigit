# multigit

multigit is a tool to manage multiple git repositories at once.

Loosely inspired by frustrations caused by trying to use [myrepos](https://myrepos.branchable.com/).

## Installation

The easiest way to install this is with [pipx](https://pypa.github.io/pipx/) (`brew install pipx`):

```sh
pipx install git+https://github.com/schwa/multigit.git
```

(If there's any demand for this, I'll set up a homebrew package.)

## Basic Usage

```sh
mmgit --help
# Registering repositories
mmgit register <path to repository>
mmgit register <path to another repository>
# Unregistering repositories
mmgit register <path to yet another repository>
# Perform git status on all registered repositories
mmgit status
# Perform git status with extra git flags
mmgit status -- --short --branch
# Pull on all registered repositories
mmgit pull
# Push on all registered repositories
mmgit push
```

## Help

```text

 Usage: mmgit [OPTIONS] COMMAND [ARGS]...

 Manage multiple git repositories.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                                                                                                   │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.                                                                            │
│ --help                        Show this message and exit.                                                                                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ add                          Add changes in repositories.                                                                                                                                 │
│ commit                       Commit changes in repositories.                                                                                                                              │
│ config                       Show, edit or clean the config file.                                                                                                                         │
│ edit                         Open selected repositories in the configured editor.                                                                                                         │
│ exec                         Execute a shell command in selected repositories.                                                                                                            │
│ gc                           Run git gc in repositories.                                                                                                                                  │
│ info                         Show information about selected repositories.                                                                                                                │
│ list                         List selected repositories.                                                                                                                                  │
│ pull                         Pull changes in repositories.                                                                                                                                │
│ push                         Push changes in repositories.                                                                                                                                │
│ register                     Register a git repository.                                                                                                                                   │
│ reveal                       Reveal selected repositories in the Finder.                                                                                                                  │
│ status                       Show the git status of all repositories.                                                                                                                     │
│ ui                           Open the configured git ui program for selected repositories.                                                                                                │
│ unregister                   Unregister a git repository.                                                                                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## Filtering

By default, multigit will perform the command on all registered repositories. You can filter the repositories that are selected by using the `--filter` flag.

The parameter passed to `--filter` is a comma-separated list of filters. The following filters are available:

- `name:<name>`: Only select repositories that contain the given name (e.g `name:multigit`).
- `not-name:<name>`: Only select repositories that do not contain the given name (e.g `not-name:multigit`).

- `dirty`: Only select repositories that have uncommitted changes.
- `no-dirty`: Only select repositories that have no uncommitted changes.
- `untracked`: Only select repositories that have untracked files.
- `no-untracked`: Only select repositories that have no untracked files.
- `stashes`: Only select repositories that have stashed changes.
- `no-stashes`: Only select repositories that have no stashed changes.
- `remotes`: Only select repositories that have remotes.
- `no-remotes`: Only select repositories that have no remotes.
- `branch:<name>`: Only select repositories that contain branches with the given name (.e.g `branch:main`).

## Configuration

Configuration lives in `~/.config/multigit.toml` but can be specified with the `--config` flag or via the `XDG_CONFIG_HOME` environment variable.

```toml
# Set the default gitui tool to use
gitui = "gitup"
# Set the default editor tool to use.
editor = "code"

# Override behavior for specific commands
[commands]
[commands.status]
# Add extra flags to the git status command
args = ["--short"]
# Only perform status on dirty repositories
filter = "dirty"

# Registered repositories
[repositories."/Users/schwa/Shared/Projects/multigit"]
path = "/Users/schwa/Shared/Projects/multigit"
```

## Known Bugs

- [ ]: Can't interrupt git push/pull with Ctrl-C
