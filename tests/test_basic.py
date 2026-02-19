"""Basic tests for MakeMKV Auto."""

import pytest
from pathlib import Path

from makemkv_auto.config import Config, PathsConfig, load_config
from makemkv_auto.web.state import ServiceState, StateManager, ServiceStatus


class TestConfig:
    """Test configuration management."""
    
    def test_default_paths(self):
        """Test that default paths are set correctly."""
        config = Config()
        assert config.paths.base == Path("/media/joseluis/DATOS_HDD/datos_samba")
        assert config.paths.movies == Path("/media/joseluis/DATOS_HDD/datos_samba/Películas")
        assert config.paths.tv_shows == Path("/media/joseluis/DATOS_HDD/datos_samba/Series")
    
    def test_custom_paths(self):
        """Test that custom paths override defaults."""
        paths = PathsConfig(
            base=Path("/custom/path"),
            movies=Path("/custom/movies"),
            tv_shows=Path("/custom/tv")
        )
        assert paths.movies == Path("/custom/movies")
        assert paths.tv_shows == Path("/custom/tv")


class TestState:
    """Test state management."""
    
    def test_default_state(self):
        """Test default state initialization."""
        state = ServiceState()
        assert state.status == ServiceStatus.IDLE
        assert state.disc_name is None
        assert state.progress_percent == 0.0
    
    def test_state_serialization(self):
        """Test state can be serialized and deserialized."""
        state = ServiceState(
            status=ServiceStatus.RIPPING,
            disc_name="Test Disc",
            progress_percent=50.0
        )
        
        # Convert to dict and back
        data = state.to_dict()
        restored = ServiceState.from_dict(data)
        
        assert restored.status == ServiceStatus.RIPPING
        assert restored.disc_name == "Test Disc"
        assert restored.progress_percent == 50.0
    
    def test_format_duration(self):
        """Test duration formatting."""
        state = ServiceState()
        # Should return "N/A" when no start time
        assert state.format_duration() == "N/A"
    
    def test_format_eta(self):
        """Test ETA formatting."""
        state = ServiceState()
        # Should return "Calculating..." when no ETA
        assert state.format_eta() == "Calculating..."
        
        # Test with seconds
        state.eta_seconds = 45
        assert state.format_eta() == "45s"
        
        # Test with minutes
        state.eta_seconds = 300
        assert state.format_eta() == "5m"
        
        # Test with hours
        state.eta_seconds = 7200
        assert state.format_eta() == "2h 0m"


class TestCLI:
    """Test CLI commands."""
    
    def test_imports(self):
        """Test that all CLI modules can be imported."""
        from makemkv_auto.cli import app
        from makemkv_auto.commands import (
            config, doctor, info, install, key, logs, rip, service, web
        )
        assert app is not None


class TestWeb:
    """Test web UI components."""
    
    def test_imports(self):
        """Test that web modules can be imported."""
        from makemkv_auto.web.app import app
        from makemkv_auto.web.state import StateManager
        assert app is not None
        assert StateManager is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
