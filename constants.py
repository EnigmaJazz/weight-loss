"""Application constants, defaults, and the logger factory.

Module-level mutable state is forbidden elsewhere in this project; this module
is the sanctioned home for cached constants and the one-time logger setup.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

DB_PATH = os.environ.get("WEIGHT_LOSS_DB", str(BASE_DIR / "weight_loss.db"))
VAPID_KEYS_PATH = os.environ.get(
    "WEIGHT_LOSS_VAPID_KEYS", str(BASE_DIR / "vapid_keys.json")
)
STATIC_DIR = str(BASE_DIR / "static")
INDEX_HTML_PATH = str(BASE_DIR / "static" / "index.html")
SW_PATH = str(BASE_DIR / "static" / "sw.js")

APP_NAME = "Weight Loss Tracker"

VAPID_SUBJECT = "mailto:weight-tracker@localhost"

DEFAULT_SETTINGS: dict[str, object] = {
    "target_weight": None,
    "tip_time": "09:00",
    "reminder_time": "20:00",
    "exercise_time": "17:00",
    "start_weight_override": None,
    "height_cm": None,
}

NOTIFICATION_TYPES: tuple[str, ...] = ("tip", "reminder", "exercise")

NOTIFICATION_MESSAGES: dict[str, tuple[str, str]] = {
    "tip": (
        "Daily weight-loss tip",
        "Consistency beats intensity — log every day, even the bad ones.",
    ),
    "reminder": (
        "Weigh-in reminder",
        "Time to log your weight for today!",
    ),
    "exercise": (
        "Exercise encouragement",
        "Time to move — a 10-minute walk counts. You've got this!",
    ),
}

TEST_NOTIFICATION_TITLE = "Weight Loss Tracker"
TEST_NOTIFICATION_BODY = "Test notification — push works!"

SCHEDULER_INTERVAL_SECONDS = 60

_logger_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a project-scoped logger, configuring the root once."""
    global _logger_configured
    if not _logger_configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
        _logger_configured = True
    return logging.getLogger(f"weight_loss.{name}")
