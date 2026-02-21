"""Disc tracking database for duplicate detection."""

import json
from pathlib import Path
from typing import Optional

from makemkv_auto.logger import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "makemkv-auto" / "disc_db.json"


class DiscDatabase:
    """Simple JSON-based database for tracking ripped discs."""
    
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._data: dict = {}
        self._load()
    
    def _load(self) -> None:
        """Load database from disk."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    self._data = json.load(f)
                logger.debug(f"Loaded disc database with {len(self._data)} entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load disc database: {e}")
                self._data = {}
        else:
            self._data = {}
    
    def _save(self) -> None:
        """Save database to disk."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w') as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save disc database: {e}")
    
    def add_disc(self, disc_id: str, disc_name: str, output_path: str) -> None:
        """Add a disc to the database."""
        if not disc_id:
            logger.warning(f"Cannot add disc without ID: {disc_name}")
            return
        
        self._data[disc_id] = {
            "name": disc_name,
            "output_path": output_path,
        }
        self._save()
        logger.info(f"Added disc to database: {disc_name} (ID: {disc_id[:20]}...)")
    
    def get_disc(self, disc_id: str) -> Optional[dict]:
        """Get disc info by ID."""
        return self._data.get(disc_id)
    
    def has_disc(self, disc_id: str) -> bool:
        """Check if disc is in database."""
        return disc_id in self._data
    
    def remove_disc(self, disc_id: str) -> bool:
        """Remove a disc from the database."""
        if disc_id in self._data:
            del self._data[disc_id]
            self._save()
            return True
        return False
