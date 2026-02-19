"""Rip command."""

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from makemkv_auto.ripper import DiscAnalyzer, Ripper
from makemkv_auto.exceptions import NoDiscError, RipError
from makemkv_auto.utils.notifications import notify

console = Console()


def rip_command(
    ctx: typer.Context,
    device: Optional[str] = typer.Option(
        None,
        "--device",
        "-d",
        help="Optical device path",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (overrides config)",
    ),
    movie: bool = typer.Option(
        False,
        "--movie",
        "-m",
        help="Force movie mode",
    ),
    tv_show: bool = typer.Option(
        False,
        "--tv-show",
        "-t",
        help="Force TV show mode",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Preview what would happen without ripping",
    ),
    min_length: Optional[int] = typer.Option(
        None,
        "--min-length",
        help="Minimum title length in seconds",
    ),
    eject: Optional[bool] = typer.Option(
        None,
        "--eject/--no-eject",
        help="Eject disc after ripping",
    ),
) -> None:
    """Rip the disc in the drive."""
    config = ctx.obj["config"]
    
    # Override config with CLI args
    if device:
        config.devices.primary = device
    if min_length:
        config.output.min_length = min_length
    if eject is not None:
        config.detection.auto_eject = eject
    
    # Validate force flags
    if movie and tv_show:
        console.print("[red]Error: Cannot use both --movie and --tv-show[/red]")
        raise typer.Exit(1)
    
    analyzer = DiscAnalyzer(config)
    ripper = Ripper(config)
    
    try:
        # Analyze disc
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing disc...", total=None)
            info = analyzer.get_disc_info()
            progress.remove_task(task)
        
        # Override content type if specified
        if movie:
            info.content_type = ContentType.MOVIE
            info.confidence = "forced"
        elif tv_show:
            info.content_type = ContentType.TV_SHOW
            info.confidence = "forced"
        
        # Determine output path
        if output:
            output_path = output
        else:
            if info.content_type.value == "tvshow":
                output_path = config.paths.tv_shows / info.sanitized_name
            else:
                output_path = config.paths.movies / info.sanitized_name
        
        console.print(f"[bold]Disc:[/bold] {info.name}")
        console.print(f"[bold]Type:[/bold] {info.content_type.value} (confidence: {info.confidence})")
        console.print(f"[bold]Output:[/bold] {output_path}")
        console.print()
        
        if dry_run:
            console.print("[yellow]Dry run - not actually ripping[/yellow]")
            console.print(f"Would rip {len(info.titles)} titles to {output_path}")
            return
        
        # Check if already ripped
        if output_path.exists() and any(output_path.iterdir()) and not config.detection.overwrite_existing:
            console.print(f"[yellow]Already ripped: {output_path}[/yellow]")
            console.print("Use --overwrite-existing to re-rip")
            
            if config.detection.auto_eject:
                subprocess.run(["eject", config.devices.primary])
            
            raise typer.Exit(0)
        
        # Rip
        console.print("[bold]Starting rip...[/bold]")
        try:
            ripper.rip_disc(info, output_path)
        except RipError as e:
            console.print(f"[red]Rip failed: {e}[/red]")
            notify(f"Rip failed: {info.name}", urgency="critical")
            raise typer.Exit(1)
        
        console.print(f"[green]✓ Rip completed: {output_path}[/green]")
        notify(f"Rip completed: {info.name}")
        
        # Eject
        if config.detection.auto_eject:
            subprocess.run(["eject", config.devices.primary])
            console.print("[green]Disc ejected[/green]")
    
    except NoDiscError:
        console.print("[yellow]No disc detected in drive[/yellow]")
        raise typer.Exit(1)


# Need to import ContentType
from makemkv_auto.ripper import ContentType
