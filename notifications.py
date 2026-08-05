"""Web Push integration: VAPID key management and sending via pywebpush."""

import asyncio
import json
import os
from typing import Any, Iterable

import requests
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode
from pywebpush import WebPushException, webpush

from constants import VAPID_SUBJECT, get_logger
from models import PushSubscription

logger = get_logger("notifications")


def _generate_vapid() -> Vapid:
    vapid = Vapid()
    vapid.generate_keys()
    return vapid


def _vapid_to_payload(vapid: Vapid) -> dict[str, str]:
    if vapid.private_key is None or vapid.public_key is None:
        raise ValueError("VAPID keys must be generated before serialization")
    private_raw = (
        vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    )
    public_raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return {
        "private_key": b64urlencode(private_raw),
        "public_key": b64urlencode(public_raw),
    }


def _vapid_from_payload(payload: dict[str, str]) -> Vapid:
    # py_vapid Vapid.from_raw expects the raw private key as bytes; the
    # persisted payload stores it as a b64url str, so pass bytes or the
    # b64urldecode inside from_raw crashes with TypeError on second boot.
    return Vapid.from_raw(payload["private_key"].encode("ascii"))


def load_or_generate_vapid(vapid_path: str) -> tuple[Vapid, str]:
    """Load persisted VAPID keys or generate + persist them. Returns (vapid, public_key)."""
    if os.path.exists(vapid_path):
        with open(vapid_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        vapid = _vapid_from_payload(payload)
        logger.info("loaded VAPID keys from %s", vapid_path)
    else:
        vapid = _generate_vapid()
        payload = _vapid_to_payload(vapid)
        with open(vapid_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        logger.info("generated and persisted VAPID keys to %s", vapid_path)
    # Always expose the raw uncompressed EC point (65 bytes) for Web Push.
    # Older persisted payloads stored DER (91 bytes) which pushManager
    # rejects as an invalid applicationServerKey.
    if vapid.public_key is None:
        raise ValueError("VAPID public key is not available")
    public_key = b64urlencode(
        vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
    )
    return vapid, public_key


def _subscription_info(subscription: PushSubscription) -> dict[str, Any]:
    return {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }


def send_push(
    subscription: PushSubscription, title: str, body: str, vapid: Vapid
) -> bool:
    """Send one push notification. Returns True on success, False on failure."""
    try:
        webpush(
            subscription_info=_subscription_info(subscription),
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=vapid,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=3600,
        )
        return True
    except (WebPushException, requests.RequestException):
        logger.warning(
            "webpush failed for endpoint %s", subscription.endpoint, exc_info=True
        )
        return False


async def send_to_all(
    subscriptions: Iterable[PushSubscription],
    title: str,
    body: str,
    vapid: Vapid,
) -> int:
    """Send a notification to every subscription. Returns successful-send count."""
    subs = list(subscriptions)
    if not subs:
        return 0
    results = await asyncio.gather(
        *(asyncio.to_thread(send_push, sub, title, body, vapid) for sub in subs)
    )
    return sum(1 for ok in results if ok)
