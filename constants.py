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
    "target_bmi": None,  # BMI goal; resolved to kg on read
    "tip_time": "09:00",
    "reminder_time": "20:00",
    "reminder_weekday": 0,  # Monday=0 ... Sunday=6 (datetime.weekday())
    "exercise_time": "17:00",
    "start_weight_override": None,
    "height_cm": None,
    "weight_unit": "kg",  # per-user input preference: "kg" | "st-lb"
    "height_unit": "cm",  # per-user input preference: "cm" | "ft-in"
    "target_unit": "kg",  # per-user target input preference: "kg" | "st-lb"
    "weight_display": "lb",  # display preference: "lb" | "st-lb"
    "theme": "system",  # per-user theme: "system" | "light" | "dark"
    "onboarding_complete": False,  # wizard finished (flag lands Phase 3)
}

# Notification types and whether each fires daily or weekly (fixed weekday).
# tip/exercise: daily; reminder (weigh-in): weekly on reminder_weekday.
DAILY_NOTIFICATION_TYPES: tuple[str, ...] = ("tip", "exercise")
WEEKLY_NOTIFICATION_TYPES: tuple[str, ...] = ("reminder",)

NOTIFICATION_TYPES: tuple[str, ...] = ("tip", "reminder", "exercise")

# Exercise-type allowlist: drives both server validation (routes.py) and the
# SPA's <select> (kept in sync by the drift-guard test). Mirrors the
# NOTIFICATION_TYPES allowlist pattern.
EXERCISE_TYPES: tuple[str, ...] = ("walk", "run", "gym", "cycling", "swim", "other")

# Notification message pools: each type has multiple (title, body) variants,
# one picked randomly at send time so users see varied text. The FIRST variant
# per type is the original single message (backward-compatible).
NOTIFICATION_MESSAGES: dict[str, tuple[tuple[str, str], ...]] = {
    "tip": (
        (
            "Daily weight-loss tip",
            "Consistency beats intensity — log every day, even the bad ones.",
        ),
        (
            "Your daily nudge",
            "Small steps compound. One entry today beats a perfect streak tomorrow.",
        ),
        (
            "Daily tip",
            "You don't need a perfect day — just a logged one. Future you says thanks.",
        ),
        (
            "Keep the streak alive",
            "Your chart only grows when you log. Give it today's point!",
        ),
        (
            "Daily tip",
            "Every entry is data — and data is power. Weigh in, win the day.",
        ),
        (
            "Daily nudge",
            "One minute now, one data point forever. That's the whole game.",
        ),
    ),
    "reminder": (
        (
            "Weigh-in reminder",
            "Time to log your weight for today!",
        ),
        (
            "Scale time!",
            "Step on the scale — it's weigh-in day. Quick and done.",
        ),
        (
            "Weigh-in day",
            "Your weekly check-in is due. Numbers don't lie — and neither do you.",
        ),
        (
            "Scale check",
            "Time for your weekly weigh-in. Every week logged is a story you can see.",
        ),
        (
            "Weigh-in time",
            "Don't let the scale win the week unread. Log it!",
        ),
    ),
    "exercise": (
        (
            "Exercise encouragement",
            "Time to move — a 10-minute walk counts. You've got this!",
        ),
        (
            "Move time!",
            "10 minutes of movement is a win. Your future self is already stronger.",
        ),
        (
            "Exercise nudge",
            "Bonus points for moving today — any movement counts, no judgement.",
        ),
        (
            "Get moving",
            "Your body is built for this. 10 minutes now, energy all day.",
        ),
        (
            "Move it!",
            "Today's quest: move a little. Walk, stretch, dance — just don't sit still.",
        ),
        (
            "Exercise boost",
            "A quick session today keeps the streak green. You've got this!",
        ),
    ),
}

TEST_NOTIFICATION_TITLE = "Weight Loss Tracker"
TEST_NOTIFICATION_BODY = "Test notification — push works!"

# Celebration message pool for checkpoint-earn pushes (checkpoint-celebrations).
# Style-matched to NOTIFICATION_MESSAGES: second-person, celebratory, no emojis
# in titles. The {percent} placeholder is interpolated with the top newly-
# earned percent by pick_celebration at send time; it is deliberately a
# standalone constant (NOT inside NOTIFICATION_MESSAGES) so NOTIFICATION_TYPES
# and the manual /api/notify allowlist stay untouched.
CELEBRATION_MESSAGES: tuple[tuple[str, str], ...] = (
    (
        "Checkpoint unlocked!",
        "You just hit {percent}% of your goal. Every log got you here.",
    ),
    (
        "Milestone reached",
        "{percent}% down — that's real progress. Keep showing up.",
    ),
    (
        "{percent}% — nice!",
        "Another checkpoint in the bag. Future you is cheering.",
    ),
    (
        "Progress check",
        "You've hit {percent}% toward your target. Data wins again.",
    ),
    (
        "Checkpoint earned",
        "{percent}% of the way there. The streak's working — log the next one.",
    ),
    (
        "Level up!",
        "{percent}% reached. Small steps, big chart. Onward.",
    ),
)

# ---- daily quests (r1-quests-xp) ----

# Quest catalogue as (key, domain, title, description, xp_value, size) tuples.
# Order is normative: the four rotating keys first (catalogue order doubles
# as the rotation tie-break), then the mandatory daily mood check-in and the
# weekly weigh-in quest. ``size`` maps to the quests.difficulty column.
# Values are pinned by tests/test_quests.py.
QUEST_POOL: tuple[tuple[str, str, str, str, int, str], ...] = (
    (
        "exercise_10",
        "exercise",
        "Move for 10 minutes",
        "Log exercise totalling at least 10 minutes today.",
        40,
        "normal",
    ),
    (
        "log_meal",
        "nutrition",
        "Log a meal",
        "Record a meal and its calories today.",
        20,
        "small",
    ),
    (
        "streak_alive",
        "movement",
        "Keep the streak alive",
        "Log any weight, exercise, or meal entry today.",
        20,
        "small",
    ),
    (
        "habit_checkin",
        "routine",
        "Check in a habit",
        "Record a healthy habit for today.",
        20,
        "small",
    ),
    (
        "mood_checkin",
        "wellbeing",
        "Mood check-in",
        "Tell us how you're feeling today.",
        20,
        "small",
    ),
    (
        "log_weight",
        "weight",
        "Weigh in",
        "Log today's weight.",
        20,
        "small",
    ),
)

# ---- XP level curve (r1-quests-xp) ----

# Level curve (xp-progression spec): level 1 starts at 0 XP and advancing from
# level n costs LEVEL_XP_PER_LEVEL + (n-1)*LEVEL_XP_STEP, so level L starts at
# T(L) = 25*(L-1)*(L+2) XP (cumulative). Pinned by tests/test_xp.py.
LEVEL_XP_PER_LEVEL = 100
LEVEL_XP_STEP = 50

# Title bands as ascending (min_level, title) pairs: the last band whose
# minimum is not above the level wins (1-4 Sprout, 5-9 Explorer, 10-19
# Adventurer, 20-29 Champion, 30+ Legend). Pinned by tests/test_xp.py.
LEVEL_TITLES: tuple[tuple[int, str], ...] = (
    (1, "Sprout"),
    (5, "Explorer"),
    (10, "Adventurer"),
    (20, "Champion"),
    (30, "Legend"),
)

SCHEDULER_INTERVAL_SECONDS = 60

# ---- authentication (user-accounts-auth) ----

# scrypt password-hashing parameters (memory-hard, stdlib-only).
SCRIPT_N = 2**14
SCRIPT_R = 8
SCRIPT_P = 1
SCRIPT_DKLEN = 32  # derived key length in bytes

# Session token: random urlsafe secret, never persisted in plaintext.
SESSION_TOKEN_BYTES = 32

# Session cookie: 30-day TTL, matched by the DB row's expires_at.
SESSION_EXPIRY_SECONDS = 30 * 24 * 60 * 60
SESSION_COOKIE_NAME = "session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "lax"
# Secure is configurable via env: local development runs plain HTTP, where a
# Secure cookie would never be sent back. Set WEIGHT_LOSS_COOKIE_SECURE=true
# behind TLS.
SESSION_COOKIE_SECURE = (
    os.environ.get("WEIGHT_LOSS_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
)

# ---- email password reset (password-reset) ----

# One-time reset token: random urlsafe secret; only its SHA-256 hash is stored.
RESET_TOKEN_BYTES = 32
RESET_TOKEN_EXPIRY_SECONDS = 30 * 60  # the emailed link expires after 30 minutes


def _env_int(name: str, default: int) -> int:
    """Parse an integer env var, falling back to ``default`` on garbage — an
    operator typo must never crash the app at import time."""
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# SMTP delivery for password-reset emails (stdlib smtplib). Credentials come
# from the operator's environment, never from the repo:
#   WEIGHT_LOSS_SMTP_HOST  (default smtp.gmail.com)
#   WEIGHT_LOSS_SMTP_PORT  (default 587, STARTTLS)
#   WEIGHT_LOSS_SMTP_USER  (e.g. a Gmail address)
#   WEIGHT_LOSS_SMTP_PASS  (a Gmail App Password — NOT the account password)
#   WEIGHT_LOSS_SMTP_FROM  (defaults to SMTP_USER)
# When SMTP_USER/PASS are unset the app falls back to logging the reset link
# (dev mode) instead of failing.
SMTP_HOST = os.environ.get("WEIGHT_LOSS_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _env_int("WEIGHT_LOSS_SMTP_PORT", 587)
SMTP_USER = os.environ.get("WEIGHT_LOSS_SMTP_USER", "")
SMTP_PASS = os.environ.get("WEIGHT_LOSS_SMTP_PASS", "")
SMTP_FROM = os.environ.get("WEIGHT_LOSS_SMTP_FROM", "")

# Public base URL embedded in password-reset links (trailing slash stripped).
PUBLIC_URL = os.environ.get(
    "WEIGHT_LOSS_PUBLIC_URL", "http://localhost:8000"
).rstrip("/")


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
