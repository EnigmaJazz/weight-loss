"""Tests for VAPID key persistence and the notification message pools."""

import base64
import random

import pytest

from constants import NOTIFICATION_MESSAGES, NOTIFICATION_TYPES
import notifications as notifications_module
from notifications import _vapid_from_payload, load_or_generate_vapid


def test_vapid_from_payload_roundtrips_public_key():
    # Regression: _vapid_to_payload persists the private key as a b64url str,
    # but py_vapid Vapid.from_raw expects bytes (it b64urldecodes then
    # hexlifies). Passing the str raises TypeError: can only concatenate str
    # (not "bytes") to str.
    vapid = notifications_module._generate_vapid()
    payload = notifications_module._vapid_to_payload(vapid)

    loaded = _vapid_from_payload(payload)

    assert loaded.public_key is not None
    assert loaded.private_key is not None
    assert vapid.public_key is not None
    assert loaded.private_key.private_numbers().private_value == (
        vapid.private_key.private_numbers().private_value
    )
    # Same keypair round-trips: loaded public point equals original public point.
    from cryptography.hazmat.primitives import serialization

    original_point = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    loaded_point = loaded.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    assert loaded_point == original_point


def test_vapid_to_payload_public_key_is_raw_point():
    # Web Push requires the raw 65-byte uncompressed EC point as the
    # applicationServerKey; a DER SubjectPublicKeyInfo (91 bytes) is rejected
    # by pushManager.subscribe with "The provided applicationServerKey is not
    # valid."
    vapid = notifications_module._generate_vapid()
    payload = notifications_module._vapid_to_payload(vapid)

    raw = base64.urlsafe_b64decode(payload["public_key"] + "==")
    assert len(raw) == 65
    assert raw[0] == 0x04  # uncompressed point marker


def test_load_or_generate_vapid_second_boot(tmp_path):
    # Regression: first boot generates + persists keys; a second boot with the
    # file present must load them (previously crashed with TypeError).
    vapid_path = str(tmp_path / "vapid_keys.json")
    _vapid, public_key = load_or_generate_vapid(vapid_path)
    assert public_key

    again_vapid, again_key = load_or_generate_vapid(vapid_path)
    assert again_key == public_key


def test_load_or_generate_vapid_migrates_legacy_der_key(tmp_path):
    # Old persisted payloads stored the public key as DER (91 bytes). Loading
    # must re-derive the raw 65-byte point so the exposed key is Web Push
    # compatible without regenerating the keypair.
    import json
    import os

    from cryptography.hazmat.primitives import serialization

    vapid = notifications_module._generate_vapid()
    assert vapid.public_key is not None
    legacy_payload = {
        "private_key": notifications_module._vapid_to_payload(vapid)[
            "private_key"
        ],
        "public_key": notifications_module.b64urlencode(
            vapid.public_key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ),
    }
    vapid_path = str(tmp_path / "vapid_keys.json")
    with open(vapid_path, "w", encoding="utf-8") as fh:
        json.dump(legacy_payload, fh)

    loaded, public_key = load_or_generate_vapid(vapid_path)

    raw = base64.urlsafe_b64decode(public_key + "==")
    assert len(raw) == 65
    assert raw[0] == 0x04
    # Same keypair: derived point equals the original point.
    original_point = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    assert raw == original_point


# ---- notification message pools (gamification step 1) -------------------


def test_message_pool_contract():
    # Every notification type must map to at least one (title, body) variant
    # of non-empty strings, and the FIRST variant must keep the original
    # single message so existing behavior stays backward-compatible.
    original = {
        "tip": (
            "Daily weight-loss tip",
            "Consistency beats intensity — log every day, even the bad ones.",
        ),
        "reminder": ("Weigh-in reminder", "Time to log your weight for today!"),
        "exercise": (
            "Exercise encouragement",
            "Time to move — a 10-minute walk counts. You've got this!",
        ),
    }
    for notif_type in NOTIFICATION_TYPES:
        variants = NOTIFICATION_MESSAGES[notif_type]
        assert len(variants) >= 1
        for title, body in variants:
            assert isinstance(title, str) and title
            assert isinstance(body, str) and body
        assert variants[0] == original[notif_type]


def test_message_pool_has_variety():
    # Guards against regression back to a single message per type: variety is
    # the whole point of the pool.
    for notif_type in NOTIFICATION_TYPES:
        bodies = {body for _, body in NOTIFICATION_MESSAGES[notif_type]}
        assert len(bodies) >= 3


def test_pick_message_returns_pool_member():
    for notif_type in NOTIFICATION_TYPES:
        pool = NOTIFICATION_MESSAGES[notif_type]
        for _ in range(200):
            assert notifications_module.pick_message(notif_type) in pool


def test_pick_message_deterministic_with_seeded_rng():
    # Same seed -> same pick for the same type across repeated calls; a
    # different seed -> a different pick for at least one type (proves the
    # variety is real, not a constant).
    for notif_type in NOTIFICATION_TYPES:
        first = notifications_module.pick_message(notif_type, random.Random(42))
        again = notifications_module.pick_message(notif_type, random.Random(42))
        assert first == again
    seeded_42 = {
        notif_type: notifications_module.pick_message(
            notif_type, random.Random(42)
        )
        for notif_type in NOTIFICATION_TYPES
    }
    seeded_44 = {
        notif_type: notifications_module.pick_message(
            notif_type, random.Random(44)
        )
        for notif_type in NOTIFICATION_TYPES
    }
    assert seeded_42 != seeded_44
