"""FastAPI web application for MakeMKV Auto."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from makemkv_auto.config import load_config
from makemkv_auto.logger import get_logger
from makemkv_auto.web.state import ServiceState, StateManager

logger = get_logger(__name__)

# Get the directory where this file is located
WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR.parent / "static"

app = FastAPI(
    title="MakeMKV Auto",
    description="Web UI for automated MakeMKV disc ripper",
    version="1.0.0",
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# State manager
state_manager = StateManager()

# Load config for web settings
try:
    config = load_config()
except Exception:
    config = None


@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    """Add cache control headers for auto-refresh."""
    response = await call_next(request)
    # Prevent caching of dynamic content
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    state = state_manager.state
    refresh_interval = config.web.auto_refresh if config else 5
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "state": state,
            "refresh_interval": refresh_interval,
        },
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, lines: int = 100, level: Optional[str] = None):
    """Log viewer page."""
    refresh_interval = config.web.auto_refresh if config else 5
    
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "lines": lines,
            "level": level,
            "refresh_interval": refresh_interval,
        },
    )


@app.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    """System information page."""
    state = state_manager.state
    
    # Get disk usage
    disk_info = {}
    try:
        import shutil
        if config and config.paths.base.exists():
            usage = shutil.disk_usage(config.paths.base)
            disk_info = {
                "total_gb": usage.total / (1024**3),
                "used_gb": usage.used / (1024**3),
                "free_gb": usage.free / (1024**3),
                "percent_used": (usage.used / usage.total) * 100,
                "path": str(config.paths.base),
            }
    except Exception as e:
        logger.error(f"Failed to get disk usage: {e}")
        disk_info = {"error": str(e)}
    
    # Get MakeMKV version
    makemkv_version = "Unknown"
    try:
        result = subprocess.run(
            ["makemkvcon", "-r", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "MakeMKV" in line:
                makemkv_version = line.strip()
                break
    except Exception:
        pass
    
    # Get service status
    service_status = "Unknown"
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "makemkv-auto-monitor"],
            capture_output=True,
            text=True,
        )
        service_status = result.stdout.strip()
    except Exception:
        pass
    
    return templates.TemplateResponse(
        "system.html",
        {
            "request": request,
            "state": state,
            "disk_info": disk_info,
            "makemkv_version": makemkv_version,
            "service_status": service_status,
            "config": config,
        },
    )


# API Endpoints

@app.get("/api/status")
async def api_status():
    """Get current service status as JSON."""
    state = state_manager.state
    return JSONResponse(content=state.to_dict())


@app.get("/api/state")
async def api_state():
    """Get current service state as JSON (alias for /api/status)."""
    state = state_manager.state
    return JSONResponse(content=state.to_dict())


@app.get("/api/logs")
async def api_logs(lines: int = 100, level: Optional[str] = None):
    """Get recent log entries."""
    log_lines = []
    
    try:
        # Determine log file path
        if config and config.paths.logs:
            log_file = config.paths.logs / "makemkv-auto.log"
        else:
            log_file = Path("/var/log/makemkv-auto/makemkv-auto.log")
        
        # Fallback to user log directory
        if not log_file.exists():
            log_file = Path.home() / ".local" / "share" / "makemkv-auto" / "logs" / "makemkv-auto.log"
        
        if log_file.exists():
            # Read last N lines
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                log_lines = all_lines[-lines:]
            
            # Filter by level if specified
            if level:
                level_upper = level.upper()
                log_lines = [line for line in log_lines if level_upper in line.upper()]
        else:
            log_lines = ["Log file not found"]
    
    except Exception as e:
        log_lines = [f"Error reading logs: {e}"]
    
    return JSONResponse(content={"logs": log_lines})


@app.post("/api/eject")
async def api_eject():
    """Eject the disc."""
    try:
        device = state_manager.state.device or "/dev/sr0"
        result = subprocess.run(
            ["eject", device],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            return JSONResponse(content={"success": True, "message": "Disc ejected"})
        else:
            return JSONResponse(
                content={"success": False, "message": result.stderr or "Failed to eject"},
                status_code=500,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="eject command not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def api_refresh():
    """Trigger a manual status refresh."""
    # Force reload state from file
    state = state_manager.state
    return JSONResponse(content=state.to_dict())


@app.get("/api/config")
async def api_config():
    """Get safe configuration values."""
    if not config:
        return JSONResponse(content={"error": "Config not loaded"})
    
    # Return only safe, non-sensitive config
    safe_config = {
        "paths": {
            "base": str(config.paths.base),
            "movies": str(config.paths.movies) if config.paths.movies else None,
            "tv_shows": str(config.paths.tv_shows) if config.paths.tv_shows else None,
        },
        "devices": {
            "primary": config.devices.primary,
        },
        "detection": {
            "auto_eject": config.detection.auto_eject,
            "overwrite_existing": config.detection.overwrite_existing,
        },
        "web": {
            "enabled": config.web.enabled if hasattr(config, "web") else True,
            "port": config.web.port if hasattr(config, "web") else 8765,
            "auto_refresh": config.web.auto_refresh if hasattr(config, "web") else 5,
        },
    }
    
    return JSONResponse(content=safe_config)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy", "state": state_manager.state.status.value})


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    if request.headers.get("accept", "").startswith("application/json"):
        return JSONResponse(content={"error": "Not found"}, status_code=404)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error_code": 404, "error_message": "Page not found"},
        status_code=404,
    )
