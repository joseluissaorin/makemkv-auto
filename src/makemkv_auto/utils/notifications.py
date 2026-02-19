"""Desktop notifications."""

import shutil
import subprocess
from typing import Optional

try:
    import notify2
    NOTIFY2_AVAILABLE = True
except ImportError:
    NOTIFY2_AVAILABLE = False

from makemkv_auto.logger import get_logger

logger = get_logger(__name__)


def notify(
    message: str,
    title: str = "MakeMKV Auto",
    urgency: str = "normal",
    timeout: int = 5000,
) -> None:
    """Send a desktop notification.
    
    Args:
        message: Notification message
        title: Notification title
        urgency: Urgency level (low, normal, critical)
        timeout: Timeout in milliseconds
    """
    # Try notify2 first (if available)
    if NOTIFY2_AVAILABLE:
        try:
            notify2.init("makemkv-auto")
            notification = notify2.Notification(title, message)
            
            urgency_levels = {
                "low": notify2.URGENCY_LOW,
                "normal": notify2.URGENCY_NORMAL,
                "critical": notify2.URGENCY_CRITICAL,
            }
            notification.set_urgency(urgency_levels.get(urgency, notify2.URGENCY_NORMAL))
            notification.set_timeout(timeout)
            notification.show()
            return
        except Exception as e:
            logger.debug(f"notify2 failed: {e}")
    
    # Fallback to notify-send
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                [
                    "notify-send",
                    "--urgency", urgency,
                    "--expire-time", str(timeout),
                    title,
                    message,
                ],
                capture_output=True,
                check=False,
            )
            return
        except Exception as e:
            logger.debug(f"notify-send failed: {e}")
    
    # Log if no notification method available
    logger.info(f"Notification: {title} - {message}")
