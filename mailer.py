"""Password-reset email delivery via stdlib smtplib (Gmail SMTP, STARTTLS).

Pure delivery module: no database access, no framework imports. The one
exported entry point, :func:`send_reset_email`, is synchronous and is
offloaded with ``asyncio.to_thread`` on the request path so SMTP I/O never
blocks the event loop.

Operator configuration (env vars, never committed — see constants.py):
  WEIGHT_LOSS_SMTP_HOST  default smtp.gmail.com
  WEIGHT_LOSS_SMTP_PORT  default 587 (STARTTLS)
  WEIGHT_LOSS_SMTP_USER  e.g. a Gmail address
  WEIGHT_LOSS_SMTP_PASS  a Gmail App Password (NOT the account password;
                         enable 2FA and create one at myaccount.google.com)
  WEIGHT_LOSS_SMTP_FROM  defaults to SMTP_USER
  WEIGHT_LOSS_PUBLIC_URL base URL embedded in the reset link

When SMTP_USER/PASS are unset the route falls back to logging the reset
link (dev mode) instead of failing; this module then reports False and
never raises.
"""

import smtplib
from email.message import EmailMessage

from constants import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    get_logger,
)

logger = get_logger("mailer")

RESET_SUBJECT = "Weight Loss Tracker — password reset"
RESET_BODY_TEMPLATE = (
    "A password reset was requested for your Weight Loss Tracker account.\n"
    "\n"
    "Open this link to choose a new password:\n"
    "{reset_url}\n"
    "\n"
    "The link expires in 30 minutes. If you didn't request a reset, you can\n"
    "ignore this email — your password stays unchanged.\n"
)


def smtp_configured() -> bool:
    """Whether SMTP credentials are available to send real email."""
    return bool(SMTP_USER and SMTP_PASS)


def build_reset_email(to_email: str, reset_url: str) -> EmailMessage:
    """Build the reset email message (pure, unit-testable)."""
    message = EmailMessage()
    message["Subject"] = RESET_SUBJECT
    message["From"] = SMTP_FROM or SMTP_USER or "weight-loss-tracker@localhost"
    message["To"] = to_email
    message.set_content(RESET_BODY_TEMPLATE.format(reset_url=reset_url))
    return message


def send_reset_email(to_email: str, reset_url: str) -> bool:
    """Send one password-reset email. Returns True on success, False when SMTP
    is unconfigured or delivery fails — never raises, so a mail outage cannot
    take down the forgot-password flow (the caller logs the dev fallback)."""
    if not smtp_configured():
        logger.warning(
            "SMTP not configured; reset link for %s not emailed", to_email
        )
        return False
    try:
        message = build_reset_email(to_email, reset_url)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(message)
        logger.info("sent password-reset email to %s", to_email)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        # Per-send boundary: auth failures, refused connections, and timeouts
        # are logged and reported as False; they must not kill the endpoint.
        logger.warning(
            "failed to send password-reset email to %s: %s", to_email, exc
        )
        return False
