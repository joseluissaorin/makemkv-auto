"""Install command for MakeMKV."""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from makemkv_auto.constants import MAKEMKV_DEFAULT_VERSION, MAKEMKV_DOWNLOAD_URL
from makemkv_auto.installer import MakeMKVInstaller

console = Console()


def install_command(
    ctx: typer.Context,
    version: str = typer.Option(
        MAKEMKV_DEFAULT_VERSION,
        "--version",
        "-v",
        help="MakeMKV version to install",
    ),
    prefix: Path = typer.Option(
        Path("/usr/local"),
        "--prefix",
        "-p",
        help="Installation prefix",
    ),
    skip_deps: bool = typer.Option(
        False,
        "--skip-deps",
        help="Skip dependency installation",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reinstallation",
    ),
) -> None:
    """Install MakeMKV and dependencies."""
    
    # Check for root
    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        console.print("[red]This command requires root privileges. Use sudo.[/red]")
        raise typer.Exit(1)
    
    # Check if key check should be skipped
    skip_key_check = ctx.obj.get("skip_key_check", False)
    
    installer = MakeMKVInstaller(version=version, prefix=prefix)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Install dependencies
        if not skip_deps:
            task = progress.add_task("Installing dependencies...", total=None)
            try:
                installer.install_dependencies()
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to install dependencies: {e}[/red]")
                raise typer.Exit(1)
            progress.remove_task(task)
        
        # Check if already installed
        if not force and installer.is_installed():
            console.print(f"[yellow]MakeMKV {installer.version} is already installed[/yellow]")
            console.print("Use --force to reinstall")
            raise typer.Exit(0)
        
        # Download and build
        task = progress.add_task(f"Downloading MakeMKV {version}...", total=None)
        try:
            installer.download()
        except Exception as e:
            console.print(f"[red]Failed to download MakeMKV: {e}[/red]")
            raise typer.Exit(1)
        progress.remove_task(task)
        
        task = progress.add_task("Building MakeMKV OSS...", total=None)
        try:
            installer.build_oss()
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to build MakeMKV OSS: {e}[/red]")
            raise typer.Exit(1)
        progress.remove_task(task)
        
        task = progress.add_task("Building MakeMKV BIN...", total=None)
        try:
            installer.build_bin()
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to build MakeMKV BIN: {e}[/red]")
            raise typer.Exit(1)
        progress.remove_task(task)
    
    console.print(f"[green]MakeMKV {version} installed successfully![/green]")
    console.print(f"[green]Installed to: {prefix}[/green]")
    
    # Register beta key if available (unless skipped)
    if skip_key_check:
        console.print("[yellow]Skipping beta key registration (--skip-key-check)[/yellow]")
        console.print("[yellow]MakeMKV will show registration dialog on first use[/yellow]")
    else:
        from makemkv_auto.beta_key import BetaKeyManager
        
        key_manager = BetaKeyManager()
        try:
            key = key_manager.fetch_key()
            if key:
                key_manager.register_key(key)
                console.print("[green]Beta key registered successfully[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not register beta key: {e}[/yellow]")
            console.print("[yellow]Use --skip-key-check to skip this step[/yellow]")
