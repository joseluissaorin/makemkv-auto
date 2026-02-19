"""Web UI management commands."""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from makemkv_auto.constants import APP_NAME

app = typer.Typer(help="Web UI management commands")
console = Console()

SERVICE_NAME = "makemkv-auto-web.service"


def check_root() -> None:
    """Check if running as root."""
    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        console.print("[red]This command requires root privileges. Use sudo.[/red]")
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
    """Start the web UI service."""
    if not user:
        check_root()
    
    try:
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd.extend(["start", SERVICE_NAME])
        
        subprocess.run(cmd, check=True)
        console.print("[green]Web UI started successfully[/green]")
        console.print("[dim]Access at http://localhost:8766[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to start web UI: {e}[/red]")
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
    """Stop the web UI service."""
    if not user:
        check_root()
    
    try:
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd.extend(["stop", SERVICE_NAME])
        
        subprocess.run(cmd, check=True)
        console.print("[green]Web UI stopped[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to stop web UI: {e}[/red]")
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
    """Restart the web UI service."""
    if not user:
        check_root()
    
    try:
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd.extend(["restart", SERVICE_NAME])
        
        subprocess.run(cmd, check=True)
        console.print("[green]Web UI restarted successfully[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to restart web UI: {e}[/red]")
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
    """Check web UI service status."""
    try:
        cmd = ["systemctl"]
        if user:
            cmd.append("--user")
        cmd.extend(["is-active", SERVICE_NAME])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            console.print("[green]✓ Web UI is running[/green]")
            console.print("[dim]Access at http://localhost:8766[/dim]")
        else:
            console.print("[yellow]✗ Web UI is not running[/yellow]")
            console.print("[dim]Start with: makemkv-auto web start[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to check status: {e}[/red]")


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
    """Show web UI service logs."""
    cmd = ["journalctl"]
    
    if user:
        cmd.append("--user")
    
    cmd.extend(["-u", SERVICE_NAME, "-n", str(lines)])
    
    if follow:
        cmd.append("-f")
    
    try:
        if follow:
            subprocess.run(cmd)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            console.print(result.stdout)
    except FileNotFoundError:
        console.print("[red]journalctl not found[/red]")
        raise typer.Exit(1)


@app.command("url")
def url_command() -> None:
    """Show the web UI URL."""
    console.print("[green]Web UI URL:[/green]")
    console.print("  Local: http://localhost:8766")
    
    # Try to get IP address
    try:
        import socket
        hostname = socket.gethostname()
        ip = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
        console.print(f"  Network: http://{ip}:8766")
    except Exception:
        pass
