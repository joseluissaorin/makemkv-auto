"""Configuration management commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax

from makemkv_auto.config import Config
from makemkv_auto.constants import DEFAULT_CONFIG_DIR, DEFAULT_USER_CONFIG_DIR

app = typer.Typer(help="Configuration management commands")
console = Console()


@app.command("init")
def init_command(
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Create system-wide configuration (requires sudo)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
) -> None:
    """Initialize a new configuration file."""
    if system:
        config_dir = DEFAULT_CONFIG_DIR
    else:
        config_dir = DEFAULT_USER_CONFIG_DIR
    
    config_path = config_dir / "config.yaml"
    
    if config_path.exists() and not force:
        console.print(f"[yellow]Configuration already exists at {config_path}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    # Create default config
    config = Config()
    config.to_yaml(config_path)
    
    console.print(f"[green]Created configuration at {config_path}[/green]")


@app.command("show")
def show_command(
    ctx: typer.Context,
) -> None:
    """Display current configuration."""
    from makemkv_auto.config import load_config
    
    config = ctx.obj["config"]
    
    # Convert to YAML for display
    import yaml
    config_dict = config.model_dump()
    
    # Convert Path objects to strings for display
    def convert_paths(obj):
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_paths(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_paths(item) for item in obj]
        return obj
    
    config_dict = convert_paths(config_dict)
    yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
    console.print(syntax)


@app.command("edit")
def edit_command(
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Edit system-wide configuration",
    ),
) -> None:
    """Open configuration file in $EDITOR."""
    import os
    import subprocess
    
    if system:
        config_path = DEFAULT_CONFIG_DIR / "config.yaml"
    else:
        config_path = DEFAULT_USER_CONFIG_DIR / "config.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Configuration not found at {config_path}[/red]")
        console.print("Run 'makemkv-auto config init' first")
        raise typer.Exit(1)
    
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(config_path)])


@app.command("set")
def set_command(
    key: str = typer.Argument(..., help="Configuration key (dot notation, e.g., 'paths.base')"),
    value: str = typer.Argument(..., help="Value to set"),
    system: bool = typer.Option(
        False,
        "--system",
        "-s",
        help="Edit system-wide configuration",
    ),
) -> None:
    """Set a configuration value."""
    if system:
        config_path = DEFAULT_CONFIG_DIR / "config.yaml"
    else:
        config_path = DEFAULT_USER_CONFIG_DIR / "config.yaml"
    
    if not config_path.exists():
        console.print(f"[red]Configuration not found at {config_path}[/red]")
        raise typer.Exit(1)
    
    # Load existing config
    config = Config.from_yaml(config_path)
    
    # Navigate to the key
    keys = key.split(".")
    obj = config
    for k in keys[:-1]:
        obj = getattr(obj, k)
    
    # Set the value
    final_key = keys[-1]
    current_value = getattr(obj, final_key)
    
    # Try to preserve type
    if isinstance(current_value, bool):
        new_value = value.lower() in ("true", "1", "yes", "on")
    elif isinstance(current_value, int):
        new_value = int(value)
    elif isinstance(current_value, Path):
        new_value = Path(value)
    else:
        new_value = value
    
    setattr(obj, final_key, new_value)
    
    # Save config
    config.to_yaml(config_path)
    console.print(f"[green]Set {key} = {new_value}[/green]")


@app.command("validate")
def validate_command(
    ctx: typer.Context,
) -> None:
    """Validate current configuration."""
    config = ctx.obj["config"]
    
    errors = []
    warnings = []
    
    # Check paths
    if not config.paths.base.exists():
        errors.append(f"Base path does not exist: {config.paths.base}")
    
    if config.paths.movies and not config.paths.movies.parent.exists():
        warnings.append(f"Movies parent path does not exist: {config.paths.movies.parent}")
    
    if config.paths.tv_shows and not config.paths.tv_shows.parent.exists():
        warnings.append(f"TV shows parent path does not exist: {config.paths.tv_shows.parent}")
    
    # Check device
    if not Path(config.devices.primary).exists():
        warnings.append(f"Primary device does not exist: {config.devices.primary}")
    
    # Display results
    if errors:
        console.print("[red]Errors:[/red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
    
    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")
    
    if not errors and not warnings:
        console.print("[green]✓ Configuration is valid[/green]")
    elif not errors:
        console.print("\n[yellow]Configuration has warnings but is usable[/yellow]")
    else:
        console.print("\n[red]Configuration has errors![/red]")
        raise typer.Exit(1)
