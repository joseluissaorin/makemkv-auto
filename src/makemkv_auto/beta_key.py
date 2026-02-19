"""Beta key management."""

import re
import subprocess
import time
from pathlib import Path

import requests

from makemkv_auto.constants import (
    DEFAULT_CONFIG_DIR,
    MAKEMKV_BETA_KEY_URL,
)
from makemkv_auto.exceptions import BetaKeyError
from makemkv_auto.logger import get_logger

logger = get_logger(__name__)


class BetaKeyManager:
    """Manages MakeMKV beta keys."""
    
    # Alternative URLs to try if main forum is unavailable
    ALT_URLS = [
        "https://www.makemkv.com/forum2/viewtopic.php?f=5&t=1053",
        "https://www.makemkv.com/forum/viewtopic.php?f=5&t=1053",
    ]
    
    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.key_file = config_dir / "beta_key.txt"
    
    def fetch_key(self) -> str | None:
        """Fetch the latest beta key from the forum with retries."""
        logger.info("Fetching beta key from forum...")
        
        # Try each URL with retries
        urls = [MAKEMKV_BETA_KEY_URL] + [url for url in self.ALT_URLS if url != MAKEMKV_BETA_KEY_URL]
        
        for url in urls:
            key = self._try_fetch_with_retry(url)
            if key:
                return key
        
        logger.error("Could not fetch beta key from any source")
        return None
    
    def _try_fetch_with_retry(self, url: str, max_retries: int = 3) -> str | None:
        """Try to fetch key from URL with exponential backoff."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=30,
                    headers=headers,
                )
                
                # Handle rate limiting
                if response.status_code == 503:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                        logger.warning(f"Server busy (503), retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                
                response.raise_for_status()
                
                html = response.text
                key = self._extract_key_from_html(html)
                if key:
                    return key
                    
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch from {url}: {e}")
        
        return None
    
    def _extract_key_from_html(self, html: str) -> str | None:
        """Extract beta key from HTML content."""
        # Pattern 1: Direct key format T-xxxxxxxx...
        key_pattern = r'T-[A-Za-z0-9@!#$%^&*()_+=\-\[\]{}|;:,.<>?]{50,}'
        match = re.search(key_pattern, html)
        
        if match:
            key = match.group(0)
            logger.info("Beta key found")
            return key
        
        # Pattern 2: Key in code tags
        code_pattern = r'<code>(T-[A-Za-z0-9@!#$%^&*()_+=\-\[\]{}|;:,.<>?]+)</code>'
        match = re.search(code_pattern, html)
        
        if match:
            key = match.group(1)
            logger.info("Beta key found in code tags")
            return key
        
        return None
    
    def get_stored_key(self) -> str | None:
        """Get the currently stored beta key."""
        if not self.key_file.exists():
            return None
        
        try:
            return self.key_file.read_text().strip()
        except IOError as e:
            logger.error(f"Failed to read key file: {e}")
            return None
    
    def store_key(self, key: str) -> None:
        """Store beta key to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.key_file.write_text(key)
            self.key_file.chmod(0o600)  # Restrict permissions
            logger.info("Beta key stored")
        except IOError as e:
            raise BetaKeyError(f"Failed to store key: {e}")
    
    def register_key(self, key: str) -> bool:
        """Register beta key with MakeMKV."""
        logger.info("Registering beta key...")
        
        try:
            result = subprocess.run(
                ["makemkvcon", "reg", key],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                logger.info("Beta key registered successfully")
                return True
            else:
                logger.error(f"Failed to register key: {result.stderr}")
                return False
                
        except FileNotFoundError:
            logger.error("makemkvcon not found")
            raise BetaKeyError("MakeMKV not installed")
        except subprocess.TimeoutExpired:
            logger.error("Timeout registering key")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to register key: {e}")
            return False
    
    def update_key(self) -> bool:
        """Fetch and update beta key if changed."""
        new_key = self.fetch_key()
        
        if not new_key:
            logger.error("Could not fetch beta key")
            return False
        
        current_key = self.get_stored_key()
        
        if new_key == current_key:
            logger.info("Beta key is already up to date")
            return True
        
        # Store and register new key
        self.store_key(new_key)
        
        if self.register_key(new_key):
            logger.info("Beta key updated successfully")
            return True
        else:
            logger.error("Failed to register new key")
            return False
