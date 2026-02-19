"""Beta key management commands."""

import typer
from rich.console import Console

from makemkv_auto.beta_key import BetaKeyManager
from makemkv_auto.exceptions import BetaKeyError

app = typer.Typer(help="Beta key management commands")
console = Console()


@app.command("update")
def update_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force update even if key hasn't changed",
    ),
) -> None:
    """Fetch and update the beta key."""
    manager = BetaKeyManager()
    
    try:
        key = manager.fetch_key()
        
        if not key:
            console.print("[yellow]Could not fetch beta key from forum[/yellow]")
            console.print("[dim]MakeMKV will run in evaluation mode - you can still rip discs[/dim]")
            console.print("[dim]The registration dialog will appear when you use MakeMKV[/dim]")
            return  # Don't exit with error, just warn
        
        # Check if key has changed
        current_key = manager.get_stored_key()
        if key == current_key and not force:
            console.print("[green]Beta key is up to date[/green]")
            return
        
        # Store and register key
        manager.store_key(key)
        
        # Try to register, but don't fail if it doesn't work
        if manager.register_key(key):
            if current_key:
                console.print("[green]Beta key updated successfully[/green]")
            else:
                console.print("[green]Beta key installed successfully[/green]")
        else:
            console.print("[yellow]Beta key stored but could not be registered[/yellow]")
            console.print("[dim]MakeMKV may show the registration dialog[/dim]")
    
    except BetaKeyError as e:
        console.print(f"[yellow]Failed to update key: {e}[/yellow]")
        console.print("[dim]MakeMKV will run in evaluation mode - you can still rip discs[/dim]")


@app.command("show")
def show_command(
    mask: bool = typer.Option(
        True,
        "--mask/--no-mask",
        help="Mask the key for security",
    ),
) -> None:
    """Show the current beta key."""
    manager = BetaKeyManager()
    
    key = manager.get_stored_key()
    
    if not key:
        console.print("[yellow]No beta key stored[/yellow]")
        console.print("[dim]MakeMKV will run in evaluation mode - you can still rip discs[/dim]")
        console.print("[dim]Run 'makemkv-auto key update' to fetch a key when the forum is available[/dim]")
        return
    
    if mask:
        masked = key[:5] + "*" * (len(key) - 10) + key[-5:]
        console.print(f"[green]Current key: {masked}[/green]")
    else:
        console.print(f"[green]Current key: {key}[/green]")


@app.command("status")
def status_command() -> None:
    """Check beta key status."""
    manager = BetaKeyManager()
    
    key = manager.get_stored_key()
    
    if not key:
        console.print("[yellow]No beta key stored[/yellow]")
        console.print("[dim]MakeMKV will run in evaluation mode - you can still rip discs[/dim]")
        console.print("[dim]Run 'makemkv-auto key update' to fetch a key when the forum is available[/dim]")
        return
    
    # Check if MakeMKV is registered
    import subprocess
    
    try:
        result = subprocess.run(
            ["makemkvcon", "reg"],
            capture_output=True,
            text=True,
        )
        
        if "registered" in result.stdout.lower():
            console.print("[green]✓ Beta key is registered[/green]")
        else:
            console.print("[yellow]Beta key is stored but not registered[/yellow]")
            console.print("[dim]Run 'makemkv-auto key update' to re-register[/dim]")
    except FileNotFoundError:
        console.print("[yellow]MakeMKV not found. Install it first.[/yellow]")
        console.print("[dim]Run 'makemkv-auto install' to install MakeMKV[/dim]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Could not verify key status[/yellow]")
