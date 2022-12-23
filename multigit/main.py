from git import Repo  # https://gitpython.readthedocs.io/en/stable/tutorial.html
from pathlib import Path
from rich import print as rich_print  # https://rich.readthedocs.io/en/stable/
from rich.console import Console
from rich.table import Table
from typing import List, Optional
import functools
import os
import shlex
import subprocess
import toml  # https://pypi.org/project/toml/ https://realpython.com/python-toml/
import typer  # https://typer.tiangolo.com

# https://github.com/junegunn/fzf


def quote(obj):
    return shlex.quote(str(obj))


### TODO: Config "repositories" should become "projects"
### TODO: Could no-push be better fixed by configuring the repo to not push to origin?


class Multigit:
    def __init__(self, config_path: Path = None):
        if config_path := config_path:
            self.config_path = config_path
        else:
            config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
            self.config_path = config_home / "multigit/config.toml"
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config = {"repositories": {}}
        else:
            self.config = toml.load(self.config_path)
            if "repositories" not in self.config:
                self.config["repositories"] = {}

    def save(self):
        toml.dump(self.config, self.config_path.open("w"))

    @property
    @functools.cache
    def all_projects(self):
        return sorted(
            [Project(record) for record in self.config["repositories"].values()],
            key=lambda r: r.path,
        )

    def filtered_projects(
        self,
        limit: List[str] = None,
        dirty: Optional[bool] = None,
        stashes: Optional[bool] = None,
        untracked: Optional[bool] = None,
        active_branch_name: Optional[str] = None,
        not_active_branch_name: Optional[str] = None,
        remotes: Optional[bool] = None,
    ):
        projects = self.all_projects
        if limit:
            projects = (
                p
                for p in projects
                if any(l.lower() in str(p.path).lower() for l in limit)
            )
        if dirty := dirty:
            projects = (p for p in projects if p.repo.is_dirty() == dirty)
        if stashes := stashes:
            projects = (p for p in projects if (p.stashes > 0) == dirty)
        if untracked := untracked:
            projects = (
                p for p in projects if (len(p.repo.untracked_files) > 0) == untracked
            )
        if active_branch_name := active_branch_name:
            projects = (
                p for p in projects if p.repo.active_branch.name == active_branch_name
            )
        if not_active_branch_name := not_active_branch_name:
            projects = (
                p
                for p in projects
                if p.repo.active_branch.name != not_active_branch_name
            )
        if remotes := remotes:
            projects = (p for p in projects if (len(p.repo.remotes) > 0) == remotes)
        return projects

    def edit(self, path):
        editor = self.config.get("editor", os.environ.get("EDITOR", "nano"))
        command = f"{editor} {quote(path)}"
        command = shlex.split(command)
        subprocess.check_call(command)

    def gitui(self, path):
        editor = self.config.get("gitui", os.environ.get("GITUI", None))
        if not editor:
            raise typer.UsageError(
                "No gitui configured. Set 'gitui' in config.toml or GITUI environment variable."
            )
        command = f"{editor} {quote(path)}"
        command = shlex.split(command)
        subprocess.check_call(command)


class Project:
    def __init__(self, record: dict):
        self.path = Path(record["path"])
        self.no_push = record.get("no-push", False)

    @property
    @functools.cache
    def repo(self):
        return Repo(self.path)

    @property
    @functools.cache
    def stashes(self):
        return len(self.repo.git.stash("list").splitlines())


################################################################################################

multigit = Multigit()
app = typer.Typer(help="Manage multiple git repositories.")


# Base commands


@app.command()
def register(path: Path = typer.Argument(..., exists=True)):
    """Register a git repository."""
    path = path.resolve()
    if not (path / ".git").exists():
        raise typer.BadParameter("Not a git repository")
    multigit.config["repositories"][str(path)] = {"path": str(path)}
    multigit.save()


@app.command()
def unregister(path: Path = typer.Argument(..., exists=True)):
    """Unregister a git repository."""
    path = path.resolve()
    if str(path) not in multigit.config["repositories"]:
        raise typer.BadParameter(f"{path} not registered")
    del multigit.config["repositories"][str(path)]
    multigit.save()


@app.command()
def config_edit():
    """Edit the multigit config file."""
    multigit.edit(multigit.config_path)


@app.command()
def self_check(
    limit: List[str] = typer.Option(None, "--limit", "-l"),
):
    """Check that all registered repositories exist."""
    for project in multigit.all_projects:
        if limit and not any(project.path.match(l) for l in limit):
            #            print("Skipping", path, "because it doesn't match any of", limit)
            continue
        if limit:
            rich_print(f"[cyan]{project.path}[/cyan]")
        if not project.path.exists():
            rich_print(f"Directory '{project.path}' missing, removing from config")
            del multigit.config["repositories"][str(project.path)]
    multigit.save()


# git commands


@app.command()
def status(
    short: bool = typer.Option(False, "--short", "-s"),
    skip_clean: bool = typer.Option(False, "--skip-clean", "-k"),
    limit: List[str] = typer.Option(None, "--limit", "-l"),
):
    """Show the git status of all repositories."""
    for project in multigit.all_projects:
        if limit and not any(project.path.match(l) for l in limit):
            #            print("Skipping", path, "because it doesn't match any of", limit)
            continue

        dirty = project.repo.is_dirty()
        untracked_files = len(project.repo.untracked_files) > 0
        if not (dirty and untracked_files) and skip_clean:
            continue
        rich_print(f"[cyan]{project.path}[/cyan]", end=None)
        if dirty or untracked_files:
            rich_print(": [bold yellow]dirty[/bold yellow]")
            if not short:
                subprocess.check_call(["git", "status"], cwd=project.path)
        else:
            rich_print(": [bold green]clean[/bold green]")


@app.command()
def add(all: bool = typer.Option(False, "--all", "-a")):
    """Add changes in repositories."""
    for project in multigit.all_projects:
        if project.repo.is_dirty() or project.repo.untracked_files:
            continue
        command = ["git", "add"]
        if all:
            command.append("--all")
        subprocess.check_call(command, cwd=project.path)


@app.command()
def commit(all: bool = typer.Option(False, "--all", "-a")):
    """Commit changes in repositories."""
    for project in multigit.all_projects:
        if project.repo.is_dirty() or project.repo.untracked_files:
            continue
        command = ["git", "commit"]
        if all:
            command.append("--all")
        subprocess.check_call(command, cwd=project.path)


@app.command()
def pull():
    """Pull changes in repositories.""" ""
    for project in multigit.all_projects:
        repo = project.repo
        if repo.remotes:
            rich_print(f"[cyan]{project.path}[/cyan]")
            subprocess.check_call(["git", "pull"], cwd=project.path)


@app.command()
def push():
    """Push changes in repositories."""
    for project in multigit.all_projects:
        if project.no_push:
            continue
        repo = project.repo
        if repo.remotes:
            rich_print(f"[cyan]{project.path}[/cyan]")
            try:
                subprocess.check_call(["git", "push"], cwd=project.path)
            except:
                rich_print("[bold red]Push failed[/bold red]")


@app.command()
def gc():
    """Run git gc in repositories."""
    for project in multigit.all_projects:
        rich_print(f"[cyan]{project.path}[/cyan]")
        subprocess.check_call(["git", "gc"], cwd=project.path)


# Utility commands


@app.command()
def ui(
    limit: List[str] = typer.Option(None, "--limit", "-l"),
    dirty: Optional[bool] = typer.Option(None, "--dirty/--no-dirty"),
    stashes: Optional[bool] = typer.Option(None, "--stash/--no-stash"),
    untracked: Optional[bool] = typer.Option(None, "--untracked/--no-untracked"),
    active_branch_name: Optional[str] = typer.Option(None, "--active-branch", "-b"),
    not_active_branch_name: Optional[str] = typer.Option(None, "--not-active-branch"),
):
    """Open the configured git ui program for selected repositories."""
    projects = multigit.filtered_projects(
        limit=limit,
        dirty=dirty,
        stashes=stashes,
        untracked=untracked,
        active_branch_name=active_branch_name,
        not_active_branch_name=not_active_branch_name,
    )
    for project in projects:
        repo = project.repo
        multigit.gitui(project.path)


@app.command()
def reveal(dirty_only: bool = typer.Option(False, "--dirty", "-d")):
    """Reveal selected repositories in the Finder."""
    for project in multigit.all_projects:
        repo = project.repo
        dirty = repo.is_dirty()
        if dirty_only and not dirty:
            continue
        subprocess.check_call(["open", "-R", project.path])


@app.command(name="exec")
def shell_exec(args: List[str]):
    """Execute a shell command in selected repositories."""
    command = ["sh", "-l", "-i", "-c", shlex.join(args)]
    for project in multigit.all_projects:
        rich_print(f"[cyan]{project.path}[/cyan]")
        subprocess.check_call(command, cwd=project.path)


@app.command(name="edit")
def project_edit(
    limit: List[str] = typer.Option(None, "--limit", "-l"),
    dirty: Optional[bool] = typer.Option(None, "--dirty/--no-dirty"),
    stashes: Optional[bool] = typer.Option(None, "--stash/--no-stash"),
    untracked: Optional[bool] = typer.Option(None, "--untracked/--no-untracked"),
    active_branch_name: Optional[str] = typer.Option(None, "--active-branch", "-b"),
    not_active_branch_name: Optional[str] = typer.Option(None, "--not-active-branch"),
):
    """Open selected repositories in the configured editor."""
    projects = multigit.filtered_projects(
        limit=limit,
        dirty=dirty,
        stashes=stashes,
        untracked=untracked,
        active_branch_name=active_branch_name,
        not_active_branch_name=not_active_branch_name,
    )
    for project in projects:
        multigit.edit(project.path)


@app.command(name="list")
def list_projects(
    dirty: Optional[bool] = typer.Option(None, "--dirty/--no-dirty"),
    stashes: Optional[bool] = typer.Option(None, "--stash/--no-stash"),
    untracked: Optional[bool] = typer.Option(None, "--untracked/--no-untracked"),
    active_branch_name: Optional[str] = typer.Option(None, "--active-branch", "-b"),
    not_active_branch_name: Optional[str] = typer.Option(None, "--not-active-branch"),
):
    """List selected repositories."""
    projects = multigit.filtered_projects(
        dirty=dirty,
        stashes=stashes,
        untracked=untracked,
        active_branch_name=active_branch_name,
        not_active_branch_name=not_active_branch_name,
    )
    for project in projects:
        print(project.path)


@app.command()
def info(
    limit: List[str] = None,
    dirty: Optional[bool] = typer.Option(None, "--dirty/--no-dirty"),
    stashes: Optional[bool] = typer.Option(None, "--stash/--no-stash"),
    untracked: Optional[bool] = typer.Option(None, "--untracked/--no-untracked"),
    active_branch_name: Optional[str] = typer.Option(None, "--active-branch", "-b"),
    not_active_branch_name: Optional[str] = typer.Option(None, "--not-active-branch"),
):
    """Show information about selected repositories."""
    table = Table()
    table.add_column("Path")
    table.add_column("Branches")
    table.add_column("Remotes")
    table.add_column("Status")
    table.add_column("Stashes")
    table.add_column("Notes")

    projects = multigit.filtered_projects(
        limit=limit,
        dirty=dirty,
        stashes=stashes,
        untracked=untracked,
        active_branch_name=active_branch_name,
        not_active_branch_name=not_active_branch_name,
    )
    for project in projects:
        branches = [
            b.name for b in project.repo.branches if b != project.repo.active_branch
        ]

        repo = project.repo
        active_branch_name = repo.active_branch.name
        other_branches = [b.name for b in repo.branches if b.name != active_branch_name]

        branches = ", ".join(
            [f"[yellow bold]{active_branch_name}[/yellow bold]"] + other_branches
        )

        remotes = ", ".join([r.name for r in repo.remotes])

        status = [
            "[bold red]dirty[/bold red]" if repo.is_dirty() else None,
        ]
        if repo.untracked_files:
            status.append(f"[bold red]{len(repo.untracked_files)} untracked[/bold red]")

        status = "".join([s for s in status if s])

        stashes = len(repo.git.stash("list").splitlines())

        cells = [
            # str(project.path).replace(str(Path.home()), "~"),
            project.path.name,
            branches,
            remotes,
            status,
            stashes > 0 and f"[bold red]{stashes} stashes[/bold red]" or "",
            project.no_push and "[yellow]no push[/yellow]" or "",
        ]
        table.add_row(*cells)

    console = Console()
    console.print(table)


################################################################################################

if __name__ == "__main__":
    app()
