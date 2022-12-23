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
# Pull on all registered repositories
mmgit pull
# Push on all registered repositories
mmgit push
```
