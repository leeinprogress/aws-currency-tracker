from app.core.security import (
    get_password_hash,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


class TestPasswordHashing:
    def test_hash_password_round_trip(self):
        plain = "SuperSecret123!"
        hashed = get_password_hash(plain)
        assert verify_password(plain, hashed) is True

    def test_hash_password_alias_round_trip(self):
        plain = "AnotherPassword99"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_wrong_password_rejected(self):
        plain = "CorrectPassword1"
        hashed = get_password_hash(plain)
        assert verify_password("WrongPassword1", hashed) is False

    def test_empty_password_rejected(self):
        plain = "SomePassword42"
        hashed = get_password_hash(plain)
        assert verify_password("", hashed) is False

    def test_hash_is_not_plaintext(self):
        plain = "NotStoredAsPlaintext"
        hashed = get_password_hash(plain)
        assert plain not in hashed

    def test_same_password_produces_different_hashes(self):
        plain = "SamePasswordTwice"
        hash1 = get_password_hash(plain)
        hash2 = get_password_hash(plain)
        # bcrypt uses random salt — hashes must differ
        assert hash1 != hash2
        # but both must still verify
        assert verify_password(plain, hash1) is True
        assert verify_password(plain, hash2) is True

    def test_password_exceeding_72_bytes(self):
        # bcrypt silently truncates at 72 bytes; our wrapper handles this
        plain = "a" * 80
        hashed = get_password_hash(plain)
        assert verify_password("a" * 80, hashed) is True


class TestJWTTokens:
    def test_access_token_encode_decode(self):
        payload = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-123"
        assert decoded["email"] == "test@example.com"

    def test_invalid_access_token_returns_none(self):
        assert decode_access_token("not.a.real.token") is None

    def test_refresh_token_encode_decode(self):
        payload = {"sub": "user-456"}
        token = create_refresh_token(payload)
        decoded = decode_refresh_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-456"
        assert decoded["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        payload = {"sub": "user-789"}
        token = create_access_token(payload)
        # access token has no "type": "refresh" claim
        assert decode_refresh_token(token) is None

    def test_invalid_refresh_token_returns_none(self):
        assert decode_refresh_token("garbage.token.here") is None
