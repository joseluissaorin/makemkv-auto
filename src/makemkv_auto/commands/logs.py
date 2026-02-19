"""Logs command."""

from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax

console = Console()


def logs_command(
    ctx: typer.Context,
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
    service: bool = typer.Option(
        False,
        "--service",
        "-s",
        help="Show service logs instead of application logs",
    ),
) -> None:
    """View application logs."""
    config = ctx.obj["config"]
    
    if service:
        # Show systemd service logs
        import subprocess
        
        cmd = ["journalctl", "-u", "makemkv-auto-monitor.service", "-n", str(lines)]
        if follow:
            cmd.append("-f")
        
        try:
            subprocess.run(cmd)
        except FileNotFoundError:
            console.print("[red]journalctl not found[/red]")
            raise typer.Exit(1)
    else:
        # Show application logs
        log_file = config.paths.logs / "makemkv-auto.log"
        
        if not log_file.exists():
            console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
            raise typer.Exit(1)
        
        if follow:
            import subprocess
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            # Read last N lines
            try:
                with open(log_file, "r") as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:]
                    
                    log_content = "".join(last_lines)
                    syntax = Syntax(log_content, "log", line_numbers=False)
                    console.print(syntax)
            except Exception as e:
                console.print(f"[red]Failed to read log file: {e}[/red]")
                raise typer.Exit(1)
