"""Doctor command for health checks."""

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from makemkv_auto.config import Config

console = Console()


def check_command(cmd: str) -> tuple[bool, str | None]:
    """Check if a command is available."""
    path = shutil.which(cmd)
    if path:
        return True, path
    return False, None


def check_makemkv() -> dict:
    """Check MakeMKV installation."""
    found, path = check_command("makemkvcon")
    
    if not found:
        return {
            "installed": False,
            "version": None,
            "path": None,
        }
    
    try:
        result = subprocess.run(
            ["makemkvcon", "-r", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        # Parse version from output
        version = "Unknown"
        for line in result.stdout.split("\n"):
            if "MakeMKV" in line:
                version = line.strip()
                break
        
        return {
            "installed": True,
            "version": version,
            "path": path,
        }
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return {
            "installed": True,
            "version": "Unknown",
            "path": path,
        }


def check_device(device: str) -> dict:
    """Check optical device."""
    device_path = Path(device)
    
    return {
        "exists": device_path.exists(),
        "readable": device_path.exists() and device_path.stat().st_mode & 0o444 != 0,
    }


def doctor_command(
    ctx: typer.Context,
) -> None:
    """Check installation health and configuration."""
    config = ctx.obj["config"]
    
    console.print(Panel.fit("[bold blue]MakeMKV Auto Health Check[/bold blue]"))
    console.print()
    
    # Create results table
    table = Table(title="Health Check Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    
    issues = []
    
    # Check MakeMKV
    makemkv_info = check_makemkv()
    if makemkv_info["installed"]:
        table.add_row(
            "MakeMKV",
            "[green]✓ Installed[/green]",
            f"{makemkv_info['path']} ({makemkv_info['version']})",
        )
    else:
        table.add_row(
            "MakeMKV",
            "[red]✗ Not installed[/red]",
            "Run 'makemkv-auto install'",
        )
        issues.append("MakeMKV is not installed")
    
    # Check device
    device_info = check_device(config.devices.primary)
    if device_info["exists"]:
        status = "[green]✓ Found[/green]" if device_info["readable"] else "[yellow]⚠ Not readable[/yellow]"
        details = config.devices.primary
        if not device_info["readable"]:
            details += " (permission issue)"
            issues.append(f"Device {config.devices.primary} is not readable")
        table.add_row("Optical Drive", status, details)
    else:
        table.add_row(
            "Optical Drive",
            "[red]✗ Not found[/red]",
            config.devices.primary,
        )
        issues.append(f"Optical device {config.devices.primary} not found")
    
    # Check dependencies
    deps = ["eject", "curl", "wget"]
    for dep in deps:
        found, path = check_command(dep)
        if found:
            table.add_row(dep, "[green]✓ Found[/green]", path)
        else:
            table.add_row(dep, "[red]✗ Not found[/red]", "Install package")
            issues.append(f"Missing dependency: {dep}")
    
    # Check paths
    paths_to_check = [
        ("Base Path", config.paths.base),
        ("Movies Path", config.paths.movies),
        ("TV Shows Path", config.paths.tv_shows),
    ]
    
    for name, path in paths_to_check:
        if path is None:
            continue
            
        if path.exists():
            table.add_row(name, "[green]✓ Exists[/green]", str(path))
        else:
            table.add_row(name, "[yellow]⚠ Not found[/yellow]", str(path))
            issues.append(f"{name} does not exist: {path}")
    
    # Check systemd
    systemd_found, _ = check_command("systemctl")
    if systemd_found:
        table.add_row("Systemd", "[green]✓ Available[/green]", "")
    else:
        table.add_row("Systemd", "[yellow]⚠ Not found[/yellow]", "Service management unavailable")
    
    console.print(table)
    console.print()
    
    # Summary
    if not issues:
        console.print(Panel("[bold green]✓ All checks passed![/bold green]"))
    else:
        console.print(Panel.fit(
            f"[bold yellow]⚠ Found {len(issues)} issue(s):[/bold yellow]\n" +
            "\n".join(f"  • {issue}" for issue in issues)
        ))
        raise typer.Exit(1)
