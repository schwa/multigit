import typer
from pathlib import Path
import toml  # https://pypi.org/project/toml/ https://realpython.com/python-toml/
import subprocess
from git import Repo  # https://gitpython.readthedocs.io/en/stable/tutorial.html
from rich import print  # https://rich.readthedocs.io/en/stable/
from typing import List
import shlex
from rich.console import Console
from rich.table import Table
from rich.text import Text

# https://github.com/junegunn/fzf


def longestCommonPrefix(s):
    if not s:
        return ""
    prefix = s[0]
    for word in s:
        if len(prefix) > len(word):
            prefix, word = word, prefix

        while len(prefix) > 0:
            if word[: len(prefix)] == prefix:
                break
            else:
                prefix = prefix[:-1]
    return prefix


app = typer.Typer()

### TODO: Config "repositories" should become "projects"
### TODO: Could no-push be better fixed by configuring the repo to not push to origin?


class Project:
    def __init__(self, record: dict):
        self.path = Path(record["path"])
        self.no_push = record.get("no-push", False)

    @property
    def repo(self):
        return Repo(self.path)


config_path = Path.home() / ".config/multigit/config.toml"
config_path.parent.mkdir(parents=True, exist_ok=True)
if config_path.exists():
    config = toml.load(config_path)
    if "repositories" not in config:
        config["repositories"] = {}
else:
    config = {"repositories": {}}

projects = sorted(
    [Project(record) for record in config["repositories"].values()],
    key=lambda r: r.path,
)

################################################################################################


@app.command()
def register(path: Path = typer.Argument(..., exists=True)):
    path = path.resolve()
    if not (path / ".git").exists():
        raise typer.BadParameter("Not a git repository")
    config["repositories"][str(path)] = {"path": str(path)}
    toml.dump(config, config_path.open("w"))


@app.command()
def unregister(path: Path = typer.Argument(..., exists=True)):
    path = path.resolve()
    if str(path) not in config["repositories"]:
        raise typer.BadParameter(f"{path} not registered")
    del config["repositories"][str(path)]
    toml.dump(config, config_path.open("w"))


@app.command()
def status(
    short: bool = typer.Option(False, "--short", "-s"),
    skip_clean: bool = typer.Option(False, "--skip-clean", "-k"),
    limit: List[str] = typer.Option(None, "--limit", "-l"),
):
    for project in projects:
        if limit and not any(project.path.match(l) for l in limit):
            #            print("Skipping", path, "because it doesn't match any of", limit)
            continue

        dirty = project.repo.is_dirty()
        untracked_files = len(project.repo.untracked_files) > 0
        if not (dirty and untracked_files) and skip_clean:
            continue
        print(f"[cyan]{project.path}[/cyan]", end=None)
        if dirty or untracked_files:
            print(": [bold yellow]dirty[/bold yellow]")
            if not short:
                subprocess.check_call(["git", "status"], cwd=project.path)
        else:
            print(": [bold green]clean[/bold green]")


@app.command()
def commit(all: bool = typer.Option(False, "--all", "-a")):
    for project in projects:
        command = ["git", "commit"]
        if all:
            command.append("--all")
        subprocess.check_call(command, cwd=project.path)


@app.command()
def pull():
    for project in projects:
        repo = project.repo
        if repo.remotes:
            print(f"[cyan]{project.path}[/cyan]")
            subprocess.check_call(["git", "pull"], cwd=project.path)


@app.command()
def push():
    for project in projects:
        if project.no_push:
            continue
        repo = project.repo
        if repo.remotes:
            print(f"[cyan]{project.path}[/cyan]")
            try:
                subprocess.check_call(["git", "push"], cwd=project.path)
            except:
                print("[bold red]Push failed[/bold red]")


@app.command()
def ui(dirty_only: bool = typer.Option(False, "--dirty", "-d")):
    for project in projects:
        repo = project.repo
        dirty = repo.is_dirty()
        if dirty_only and not dirty:
            continue
        subprocess.check_call(["gitup"], cwd=project.path)


@app.command()
def reveal(dirty_only: bool = typer.Option(False, "--dirty", "-d")):
    for project in projects:
        repo = project.repo
        dirty = repo.is_dirty()
        if dirty_only and not dirty:
            continue
        subprocess.check_call(["open", "-R", project.path])


@app.command()
def info():
    table = Table()
    table.add_column("Path")
    table.add_column("Branches")
    table.add_column("Remotes")
    table.add_column("Status")
    table.add_column("Stashes")
    table.add_column("Notes")

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


@app.command()
def exec(args: List[str]):
    command = ["sh", "-l", "-i", "-c", shlex.join(args)]
    for project in projects:
        print(f"[cyan]{project.path}[/cyan]")
        subprocess.check_call(command, cwd=project.path)


@app.command()
def list():
    for project in projects:
        print(f"[cyan]{project.path}[/cyan]")


@app.command()
def gc():
    for project in projects:

        print(f"[cyan]{project.path}[/cyan]")
        subprocess.check_call(["git", "gc"], cwd=project.path)


################################################################################################

if __name__ == "__main__":
    app()
