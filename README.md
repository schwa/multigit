# multigit

multigit is a tool to manage multiple git repositories at once.

Loosely inspired by frustrations caused by trying to use [myrepos](https://myrepos.branchable.com/).

## Installation

The easiest way to install this is with pipx (`brew install pipx`):

```sh
pipx install git+https://github.com/schwa/multigit.git
```

## Basic Usage

```sh
multigit --help
multigit register <path to repository>
multigit register <path to another repository>
multigit status
multigit pull
multigit push
```
