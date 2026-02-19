"""Disc info and eject commands."""

import subprocess
import typer
from rich.console import Console
from rich.table import Table

from makemkv_auto.ripper import DiscAnalyzer
from makemkv_auto.exceptions import NoDiscError

console = Console()


def info_command(
    ctx: typer.Context,
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Optical device path",
    ),
) -> None:
    """Show information about the disc in the drive."""
    config = ctx.obj["config"]
    
    if device:
        config.devices.primary = device
    
    analyzer = DiscAnalyzer(config)
    
    try:
        info = analyzer.get_disc_info()
    except NoDiscError:
        console.print("[yellow]No disc detected in drive[/yellow]")
        raise typer.Exit(1)
    
    # Display disc info
    console.print(f"[bold]Disc:[/bold] {info.name}")
    console.print(f"[bold]Type:[/bold] {info.content_type.value} (confidence: {info.confidence})")
    console.print()
    
    # Display titles
    table = Table(title="Titles")
    table.add_column("#", style="cyan")
    table.add_column("Duration", style="green")
    table.add_column("Size", style="blue")
    table.add_column("Type", style="magenta")
    
    for title in info.titles:
        hours = title.duration // 3600
        minutes = (title.duration % 3600) // 60
        seconds = title.duration % 60
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        size_gb = title.size_bytes / (1024**3)
        size_str = f"{size_gb:.2f} GB"
        
        table.add_row(
            str(title.index),
            duration_str,
            size_str,
            title.content_type,
        )
    
    console.print(table)


def eject_command(
    device: str = typer.Option(
        None,
        "--device",
        "-d",
        help="Optical device path",
    ),
) -> None:
    """Eject the disc from the drive."""
    if device is None:
        device = "/dev/sr0"
    
    try:
        subprocess.run(["eject", device], check=True)
        console.print(f"[green]Ejected {device}[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to eject {device}: {e}[/red]")
        raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]eject command not found. Install eject package.[/red]")
        raise typer.Exit(1)
