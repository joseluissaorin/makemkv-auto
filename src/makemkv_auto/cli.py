"""Main CLI entry point using Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from makemkv_auto import __version__
from makemkv_auto.config import Config, load_config
from makemkv_auto.constants import APP_NAME, DEFAULT_CONFIG_DIR
from makemkv_auto.logger import get_logger, setup_logging

# Import command modules
from makemkv_auto.commands import config as config_cmd
from makemkv_auto.commands import doctor as doctor_cmd
from makemkv_auto.commands import info as info_cmd
from makemkv_auto.commands import install as install_cmd
from makemkv_auto.commands import key as key_cmd
from makemkv_auto.commands import logs as logs_cmd
from makemkv_auto.commands import rip as rip_cmd
from makemkv_auto.commands import service as service_cmd
from makemkv_auto.commands import web as web_cmd

app = typer.Typer(
    name=APP_NAME,
    help="Automated MakeMKV disc ripper with intelligent TV/Movie detection",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

console = Console()
logger = get_logger(__name__)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"{APP_NAME} version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        readable=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    skip_key_check: bool = typer.Option(
        False,
        "--skip-key-check",
        "--no-key",
        help="Skip beta key validation (MakeMKV will show registration dialog)",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """MakeMKV Auto - Automated disc ripper with intelligent detection."""
    # Load configuration
    try:
        cfg = load_config(config)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    
    # Setup logging
    log_level = "DEBUG" if verbose else cfg.logging.level
    cfg.logging.level = log_level
    
    log_file = cfg.paths.logs / "makemkv-auto.log"
    setup_logging(cfg.logging, log_file)
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["skip_key_check"] = skip_key_check


# Add subcommands
app.add_typer(config_cmd.app, name="config", help="Configuration management")
app.add_typer(service_cmd.app, name="service", help="Service management")
app.add_typer(key_cmd.app, name="key", help="Beta key management")
app.add_typer(web_cmd.app, name="web", help="Web UI management")

app.command("rip")(rip_cmd.rip_command)
app.command("info")(info_cmd.info_command)
app.command("eject")(info_cmd.eject_command)
app.command("install")(install_cmd.install_command)
app.command("doctor")(doctor_cmd.doctor_command)
app.command("logs")(logs_cmd.logs_command)


@app.command("monitor")
def monitor_command(
    ctx: typer.Context,
    daemon: bool = typer.Option(
        False,
        "--daemon",
        "-d",
        help="Run as daemon",
    ),
) -> None:
    """Monitor for disc insertions (used by systemd service)."""
    from makemkv_auto.monitor import DiscMonitor
    
    config = ctx.obj["config"]
    monitor = DiscMonitor(config)
    
    if daemon:
        monitor.run_daemon()
    else:
        monitor.run()


@app.command("enable")
def enable_command(
    ctx: typer.Context,
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Enable user service instead of system service",
    ),
) -> None:
    """Enable and start the auto-rip service (shortcut for 'service enable && service start')."""
    from makemkv_auto.systemd.manager import SystemdManager
    
    if not user:
        # Check for root
        import subprocess
        if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
            console.print("[red]This command requires root privileges. Use sudo.[/red]")
            raise typer.Exit(1)
    
    manager = SystemdManager(user=user)
    
    try:
        # Install services if not already installed
        service_file = manager.system_dir / "makemkv-auto-monitor.service"
        if not service_file.exists():
            console.print("[yellow]Installing systemd services first...[/yellow]")
            manager.install_services()
        
        # Enable and start
        manager.enable()
        manager.start()
        console.print("[green]✓ Auto-rip service enabled and started![/green]")
        console.print("[dim]The service will automatically start on boot and monitor for discs[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to enable service: {e}[/red]")
        raise typer.Exit(1)


@app.command("disable")
def disable_command(
    ctx: typer.Context,
    user: bool = typer.Option(
        False,
        "--user",
        "-u",
        help="Disable user service instead of system service",
    ),
) -> None:
    """Disable and stop the auto-rip service (shortcut for 'service disable && service stop')."""
    from makemkv_auto.systemd.manager import SystemdManager
    
    if not user:
        # Check for root
        import subprocess
        if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
            console.print("[red]This command requires root privileges. Use sudo.[/red]")
            raise typer.Exit(1)
    
    manager = SystemdManager(user=user)
    
    try:
        manager.stop()
        manager.disable()
        console.print("[green]✓ Auto-rip service disabled and stopped[/green]")
    except Exception as e:
        console.print(f"[red]Failed to disable service: {e}[/red]")
        raise typer.Exit(1)


# Run the app
if __name__ == "__main__":
    app()
