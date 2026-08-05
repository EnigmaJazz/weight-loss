"""Unit tests for the pure auth helpers (auth.py) and identity storage
(database.py users/sessions) — no HTTP, no scheduler."""

import pytest

from auth import (
    generate_password_salt,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from constants import (
    SCRIPT_DKLEN,
    SESSION_EXPIRY_SECONDS,
    SESSION_TOKEN_BYTES,
)
from database import Database, DuplicateUsernameError, _utc_now


# ---- scrypt password hashing (task 1.1) --------------------------------


def test_scrypt_round_trip_verifies():
    salt = generate_password_salt()
    hashed = hash_password("correct horse battery staple", salt)
    assert verify_password("correct horse battery staple", salt, hashed) is True


def test_wrong_password_does_not_verify():
    salt = generate_password_salt()
    hashed = hash_password("correct password", salt)
    assert verify_password("wrong password", salt, hashed) is False


def test_hash_is_deterministic_for_same_salt_and_password():
    salt = generate_password_salt()
    assert hash_password("same password", salt) == hash_password(
        "same password", salt
    )


def test_same_password_with_different_salts_produces_different_hashes():
    salt_a = generate_password_salt()
    salt_b = generate_password_salt()
    assert salt_a != salt_b
    assert hash_password("same password", salt_a) != hash_password(
        "same password", salt_b
    )


def test_salts_are_unique_and_16_bytes_hex():
    salts = {generate_password_salt() for _ in range(64)}
    assert len(salts) == 64
    for salt in salts:
        assert len(salt) == 32  # 16 random bytes, hex-encoded
        int(salt, 16)  # raises if not hex


def test_hash_is_hex_of_dklen_bytes():
    salt = generate_password_salt()
    hashed = hash_password("password", salt)
    assert len(hashed) == SCRIPT_DKLEN * 2  # dklen bytes, hex-encoded
    int(hashed, 16)  # raises if not hex


# ---- session tokens (task 1.1) -----------------------------------------


def test_session_token_is_urlsafe_and_long_enough():
    token = generate_session_token()
    assert len(token) >= SESSION_TOKEN_BYTES
    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )
    assert set(token) <= allowed


def test_session_tokens_are_unique():
    tokens = {generate_session_token() for _ in range(64)}
    assert len(tokens) == 64


def test_hash_session_token_is_sha256_hex_and_never_the_raw_token():
    token = generate_session_token()
    digest = hash_session_token(token)
    assert len(digest) == 64
    int(digest, 16)  # raises if not hex
    assert digest != token  # the raw secret must never be persisted


def test_hash_session_token_is_deterministic():
    token = generate_session_token()
    assert hash_session_token(token) == hash_session_token(token)


# ---- identity storage: users + sessions (task 1.2) ---------------------


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "identity.db"))
    database.init_schema()
    yield database
    database.close()


def test_create_user_round_trip(db):
    user = db.create_user("alice", "hashvalue", "saltvalue")
    assert user.id >= 1
    assert user.username == "alice"
    assert user.password_hash == "hashvalue"
    assert user.salt == "saltvalue"
    assert user.created_at

    fetched = db.get_user_by_username("alice")
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.username == "alice"


def test_get_user_by_username_is_exact_match_lowercased(db):
    db.create_user("alice", "hash", "salt")
    assert db.get_user_by_username("alice") is not None
    assert db.get_user_by_username("ALICE") is None
    assert db.get_user_by_username("bob") is None


def test_create_user_duplicate_username_raises(db):
    db.create_user("alice", "hash", "salt")
    with pytest.raises(DuplicateUsernameError):
        db.create_user("alice", "otherhash", "othersalt")
    # the failed insert must not have created a second row
    rows = db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert rows == 1


def test_create_session_and_get_user_by_session(db):
    user = db.create_user("alice", "hash", "salt")
    token_hash = hash_session_token(generate_session_token())
    session = db.create_session(user.id, token_hash, "2999-01-01 00:00:00")
    assert session.user_id == user.id
    assert session.token_hash == token_hash
    assert session.expires_at == "2999-01-01 00:00:00"

    found = db.get_user_by_session(token_hash)
    assert found is not None
    assert found.id == user.id
    assert found.username == "alice"


def test_get_user_by_session_excludes_expired(db):
    user = db.create_user("alice", "hash", "salt")
    expired_hash = hash_session_token(generate_session_token())
    db.create_session(user.id, expired_hash, "2020-01-01 00:00:00")
    assert db.get_user_by_session(expired_hash) is None


def test_delete_session(db):
    user = db.create_user("alice", "hash", "salt")
    token_hash = hash_session_token(generate_session_token())
    db.create_session(user.id, token_hash, "2999-01-01 00:00:00")
    assert db.get_user_by_session(token_hash) is not None
    assert db.delete_session(token_hash) is True
    assert db.get_user_by_session(token_hash) is None
    assert db.delete_session(token_hash) is False


def test_create_session_sweeps_expired_rows(db):
    """Opportunistic cleanup: creating a session removes already-expired rows."""
    user = db.create_user("alice", "hash", "salt")
    # seed an expired row directly (bypassing the sweep in create_session)
    with db._tx() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (user.id, hash_session_token(generate_session_token()), _utc_now(), "2020-01-01 00:00:00"),
        )
    db.create_session(user.id, hash_session_token(generate_session_token()), "2999-01-01 00:00:00")
    remaining = db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert remaining == 1  # only the fresh session survives


def test_delete_expired_sessions(db):
    user = db.create_user("alice", "hash", "salt")
    # seed directly so create_session's opportunistic sweep can't interfere
    with db._tx() as conn:
        for expires in (
            "2999-01-01 00:00:00",
            "2020-01-01 00:00:00",
            "2021-06-01 00:00:00",
        ):
            conn.execute(
                "INSERT INTO sessions (user_id, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (user.id, hash_session_token(generate_session_token()), _utc_now(), expires),
            )
    removed = db.delete_expired_sessions("2021-01-01 00:00:00")
    assert removed == 1  # only the 2020 row is expired by that cutoff
    remaining = db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert remaining == 2


def test_user_delete_cascades_sessions(db):
    user = db.create_user("bob", "hash", "salt")
    db.create_session(user.id, hash_session_token(generate_session_token()), "2999-01-01 00:00:00")
    with db._tx() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user.id,))
    remaining = db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert remaining == 0


def test_session_expiry_constant_is_thirty_days():
    assert SESSION_EXPIRY_SECONDS == 30 * 24 * 60 * 60
