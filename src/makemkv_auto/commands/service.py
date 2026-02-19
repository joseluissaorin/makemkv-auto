"""Service management commands."""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from makemkv_auto.constants import SYSTEMD_SERVICE_NAME, SYSTEMD_TIMER_NAME
from makemkv_auto.systemd.manager import SystemdManager

app = typer.Typer(help="Service management commands")
console = Console()


def check_root() -> None:
    """Check if running as root."""
    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        console.print("[red]This command requires root privileges. Use sudo.[/red]")
        raise typer.Exit(1)


@app.command("install")
def install_command(
    ctx: typer.Context,
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Install user service instead of system service",
    ),
) -> None:
    """Install systemd service files."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.install_services()
        console.print("[green]Systemd services installed[/green]")
        console.print(f"[green]Monitor service: {SYSTEMD_SERVICE_NAME}[/green]")
        console.print(f"[green]Key update timer: {SYSTEMD_TIMER_NAME}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to install services: {e}[/red]")
        raise typer.Exit(1)


@app.command("uninstall")
def uninstall_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Uninstall user service instead of system service",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force uninstall even if running",
    ),
) -> None:
    """Remove systemd service files."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.uninstall_services(force=force)
        console.print("[green]Systemd services uninstalled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to uninstall services: {e}[/red]")
        raise typer.Exit(1)


@app.command("enable")
def enable_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Enable user service instead of system service",
    ),
) -> None:
    """Enable service to start on boot."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.enable()
        console.print("[green]Service enabled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to enable service: {e}[/red]")
        raise typer.Exit(1)


@app.command("disable")
def disable_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Disable user service instead of system service",
    ),
) -> None:
    """Disable service from starting on boot."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.disable()
        console.print("[green]Service disabled[/green]")
    except Exception as e:
        console.print(f"[red]Failed to disable service: {e}[/red]")
        raise typer.Exit(1)


@app.command("start")
def start_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Start user service instead of system service",
    ),
) -> None:
    """Start the service."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.start()
        console.print("[green]Service started[/green]")
    except Exception as e:
        console.print(f"[red]Failed to start service: {e}[/red]")
        raise typer.Exit(1)


@app.command("stop")
def stop_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Stop user service instead of system service",
    ),
) -> None:
    """Stop the service."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.stop()
        console.print("[green]Service stopped[/green]")
    except Exception as e:
        console.print(f"[red]Failed to stop service: {e}[/red]")
        raise typer.Exit(1)


@app.command("restart")
def restart_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Restart user service instead of system service",
    ),
) -> None:
    """Restart the service."""
    if not user:
        check_root()
    
    manager = SystemdManager(user=user)
    
    try:
        manager.restart()
        console.print("[green]Service restarted[/green]")
    except Exception as e:
        console.print(f"[red]Failed to restart service: {e}[/red]")
        raise typer.Exit(1)


@app.command("status")
def status_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Check user service instead of system service",
    ),
) -> None:
    """Show service status."""
    manager = SystemdManager(user=user)
    
    try:
        status = manager.status()
        
        if status["installed"]:
            console.print(f"[green]Service installed[/green]")
            console.print(f"  State: {status['state']}")
            console.print(f"  Enabled: {status['enabled']}")
            console.print(f"  PID: {status.get('pid', 'N/A')}")
        else:
            console.print("[yellow]Service not installed[/yellow]")
            console.print("Run 'makemkv-auto service install' first")
    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        raise typer.Exit(1)


@app.command("logs")
def logs_command(
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Show user service logs",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow log output",
    ),
    lines: int = typer.Option(
        50,
        "--lines",
        "-n",
        help="Number of lines to show",
    ),
) -> None:
    """Show service logs."""
    manager = SystemdManager(user=user)
    
    try:
        logs = manager.logs(follow=follow, lines=lines)
        if not follow:
            console.print(logs)
    except Exception as e:
        console.print(f"[red]Failed to get logs: {e}[/red]")
        raise typer.Exit(1)
