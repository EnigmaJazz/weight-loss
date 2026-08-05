"""Tests for VAPID key persistence: a second boot must load keys, not crash."""

import pytest

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

    from cryptography.hazmat.primitives import serialization

    assert vapid.public_key is not None
    original_der = vapid.public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert loaded.public_key is not None
    loaded_der = loaded.public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert loaded_der == original_der


def test_load_or_generate_vapid_second_boot(tmp_path):
    # Regression: first boot generates + persists keys; a second boot with the
    # file present must load them (previously crashed with TypeError).
    vapid_path = str(tmp_path / "vapid_keys.json")
    _vapid, public_key = load_or_generate_vapid(vapid_path)
    assert public_key

    again_vapid, again_key = load_or_generate_vapid(vapid_path)
    assert again_key == public_key
