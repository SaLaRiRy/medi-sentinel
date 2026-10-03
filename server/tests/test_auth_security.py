"""TICKET-012: the token/password seam (`core.security`).

The reference implementation signs HS256 tokens with a 1440-minute lifetime and
compares passwords by plain string equality (FUNCTIONAL_SPEC 5.8). This seam is
where those two rules live, so both are asserted here without HTTP or a database.
"""

from core.config import Settings
from core.security import create_access_token, decode_access_token, verify_password


def test_verify_password_is_plain_string_equality():
    assert verify_password("secret", "secret") is True
    assert verify_password("secret", "Secret") is False
    assert verify_password("secret", "") is False


def test_token_round_trips_the_claims_it_was_given():
    token = create_access_token({"sub": "alice", "user_id": 7, "role": "user"})

    claims = decode_access_token(token)

    assert claims is not None
    assert claims["sub"] == "alice"
    assert claims["user_id"] == 7
    assert claims["role"] == "user"
    assert "exp" in claims


def test_token_carries_the_configured_expiry():
    settings = Settings(jwt_expire_minutes=1440)
    token = create_access_token({"sub": "alice"}, settings=settings)

    claims = decode_access_token(token, settings=settings)

    assert claims is not None
    assert claims["exp"] - claims["iat"] == 1440 * 60


def test_expired_token_decodes_to_none():
    settings = Settings(jwt_expire_minutes=-1)
    token = create_access_token({"sub": "alice"}, settings=settings)

    assert decode_access_token(token, settings=settings) is None


def test_token_signed_with_another_secret_decodes_to_none():
    token = create_access_token({"sub": "alice"}, settings=Settings(jwt_secret_key="a"))

    assert decode_access_token(token, settings=Settings(jwt_secret_key="b")) is None


def test_tampered_token_decodes_to_none():
    token = create_access_token({"sub": "alice", "role": "user"})
    header, payload, signature = token.split(".")
    forged_payload = (
        payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB")
    )

    assert decode_access_token(f"{header}.{forged_payload}.{signature}") is None


def test_garbage_token_decodes_to_none():
    assert decode_access_token("not-a-token") is None
    assert decode_access_token("") is None
