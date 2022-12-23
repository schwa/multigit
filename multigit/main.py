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


def quote(path: Path):

    return shlex.quote(str(path.resolve()))


### TODO: Config "repositories" should become "projects"
### TODO: Could no-push be better fixed by configuring the repo to not push to origin?


class Multigit:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path := config_path:
            self.config_path = config_path
        else:
            config_home = Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            )
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
        filter: str = None,
    ):
        projects = self.all_projects
        if not filter:
            return projects

        atoms = [atom.split(":") for atom in filter.split(",")]
        for atom in atoms:
            match atom:
                case ["name", _] | ["n", _]:
                    projects = (p for p in projects if atom[1] == p.path.name)
                case ["not-name", _] | ["not-n", _]:
                    projects = (p for p in projects if atom[1] != p.path.name)
                case ["dirty"] | ["d"]:
                    projects = (p for p in projects if p.repo.is_dirty())
                case ["no-dirty"] | ["no-d"]:
                    projects = (p for p in projects if not p.repo.is_dirty())
                case ["untracked"] | ["u"]:
                    projects = (p for p in projects if len(p.repo.untracked_files) > 0)
                case ["no-untracked"] | ["no-u"]:
                    projects = (p for p in projects if len(p.repo.untracked_files) == 0)
                case ["stashes"] | ["s"]:
                    projects = (p for p in projects if len(p.stashes) > 0)
                case ["no-stashes"] | ["no-s"]:
                    projects = (p for p in projects if len(p.stashes) == 0)
                case ["remotes"] | ["r"]:
                    projects = (p for p in projects if len(p.repo.remotes) > 0)
                case ["no-remotes"] | ["no-r"]:
                    projects = (p for p in projects if len(p.repo.remotes) == 0)
                case ["branch", _] | ["b", _]:
                    projects = (
                        p for p in projects if p.repo.active_branch.name == atom[1]
                    )
                case ["not-branch", _] | ["not-b", _]:
                    projects = (
                        p for p in projects if p.repo.active_branch.name != atom[1]
                    )
                case _:
                    raise typer.BadParameter(f"Unknown filter: {atom}")
        return projects

    def edit(self, path):
        editor = self.config.get("editor", os.environ.get("EDITOR", "nano"))
        command = f"{editor} {quote(path)}"
        print(command)
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

app = typer.Typer(help="Manage multiple git repositories.")


# Base commands


@app.command()
def register(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    paths: List[Path] = typer.Argument(
        ..., help="Paths to git repositories to register"
    ),
):
    """Register a git repository."""
    multigit = Multigit(config_path=config)

    for path in paths:
        try:
            path = path.resolve()
            if not (path / ".git").exists():
                raise typer.BadParameter("Not a git repository")
            multigit.config["repositories"][str(path)] = {"path": str(path)}
            multigit.save()
            rich_print(f"Registered {path}")
        except typer.BadParameter as e:
            rich_print(f"[bold red]Error:[/bold red] {e} ({path})")
        except:
            raise


@app.command()
def unregister(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    path: Path = typer.Argument(..., help="Path to git repository to unregister"),
):
    """Unregister a git repository."""
    multigit = Multigit(config_path=config)

    path = path.resolve()
    if str(path) not in multigit.config["repositories"]:
        raise typer.BadParameter(f"{path} not registered")
    del multigit.config["repositories"][str(path)]
    multigit.save()


@app.command()
def config(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    path: bool = typer.Option(False, "--path", "-p", help="Print config file path"),
    show: bool = typer.Option(False, "--show", "-s", help="Print config file"),
    edit: bool = typer.Option(False, "--edit", "-e", help="Edit config file"),
    clean: bool = typer.Option(False, "--clean", "-c", help="Clean config file"),
):
    """Show, edit or clean the config file."""
    multigit = Multigit(config_path=config)

    if path:
        print(multigit.config_path)
    elif show:
        print(toml.dumps(multigit.config))
    elif edit:
        multigit.edit(multigit.config_path)
    elif clean:
        for project in multigit.all_projects:
            if not project.path.exists():
                rich_print(f"Directory '{project.path}' missing, removing from config")
                del multigit.config["repositories"][str(project.path)]
        multigit.save()


# git commands


@app.command()
def status(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Show the git status of all repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        dirty = project.repo.is_dirty()
        untracked_files = len(project.repo.untracked_files) > 0
        if not (dirty or untracked_files):
            continue
        rich_print(f"[cyan]{project.path}[/cyan]", end=None)
        if dirty or untracked_files:
            rich_print(": [bold yellow]dirty[/bold yellow]")
            command = ["git", "status"]
            if extra_args:
                command.extend(extra_args)
            subprocess.check_call(command, cwd=project.path)
        else:
            rich_print(": [bold green]clean[/bold green]")


@app.command()
def add(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Add changes in repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        command = ["git", "add"]
        if extra_args:
            command.extend(extra_args)
        subprocess.check_call(command, cwd=project.path)


@app.command()
def commit(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Commit changes in repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        print(project.repo.has_unstaged_changes())
        command = ["git", "commit"]
        if extra_args:
            command.extend(extra_args)
        subprocess.check_call(command, cwd=project.path)


@app.command()
def pull(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Pull changes in repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        repo = project.repo
        if repo.remotes:
            rich_print(f"[cyan]{project.path}[/cyan]")
            command = ["git", "pull"]
            if extra_args:
                command.extend(extra_args)
            subprocess.check_call(command, cwd=project.path)


@app.command()
def push(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Push changes in repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        if project.no_push:
            continue
        repo = project.repo
        if repo.remotes:
            rich_print(f"[cyan]{project.path}[/cyan]")
            try:
                command = ["git", "push"]
                if extra_args:
                    command.extend(extra_args)
                subprocess.check_call(command, cwd=project.path)
            except:
                rich_print("[bold red]Push failed[/bold red]")


@app.command()
def gc(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
    extra_args: Optional[List[str]] = typer.Argument(
        None, help="Extra arguments to pass to git"
    ),
):
    """Run git gc in repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        rich_print(f"[cyan]{project.path}[/cyan]")
        command = ["git", "gc"]
        if extra_args:
            command.extend(extra_args)
        subprocess.check_call(command, cwd=project.path)


# Utility commands


@app.command()
def ui(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """Open the configured git ui program for selected repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        repo = project.repo
        multigit.gitui(project.path)


@app.command()
def reveal(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """Reveal selected repositories in the Finder."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        repo = project.repo
        subprocess.check_call(["open", "-R", project.path])


@app.command(name="exec")
def shell_exec(
    args: List[str],
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """Execute a shell command in selected repositories."""
    multigit = Multigit(config_path=config)

    command = ["sh", "-l", "-i", "-c", shlex.join(args)]
    projects = multigit.filtered_projects(filter)
    for project in projects:
        rich_print(f"[cyan]{project.path}[/cyan]")
        subprocess.check_call(command, cwd=project.path)


@app.command(name="edit")
def project_edit(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """Open selected repositories in the configured editor."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        multigit.edit(project.path)


@app.command(name="list")
def list_projects(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """List selected repositories."""
    multigit = Multigit(config_path=config)

    projects = multigit.filtered_projects(filter)
    for project in projects:
        print(project.path)


@app.command()
def info(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    filter: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Filter projects"
    ),
):
    """Show information about selected repositories."""
    multigit = Multigit(config_path=config)

    table = Table()
    table.add_column("Path")
    table.add_column("Branches")
    table.add_column("Remotes")
    table.add_column("Status")
    table.add_column("Stashes")
    table.add_column("Notes")

    projects = multigit.filtered_projects(filter)
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
