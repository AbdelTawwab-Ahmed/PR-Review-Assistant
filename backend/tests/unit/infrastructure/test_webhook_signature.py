from app.infrastructure.github.webhook_signature import compute_signature, verify_signature

SECRET = "s3cret"
BODY = b'{"action":"opened"}'


def test_valid_signature() -> None:
    assert verify_signature(SECRET, BODY, compute_signature(SECRET, BODY))


def test_wrong_secret() -> None:
    assert not verify_signature(SECRET, BODY, compute_signature("other", BODY))


def test_tampered_body() -> None:
    signature = compute_signature(SECRET, BODY)
    assert not verify_signature(SECRET, BODY + b" ", signature)


def test_missing_header() -> None:
    assert not verify_signature(SECRET, BODY, None)


def test_empty_secret_never_verifies() -> None:
    assert not verify_signature("", BODY, compute_signature("", BODY))


def test_header_without_prefix_is_rejected() -> None:
    digest = compute_signature(SECRET, BODY).removeprefix("sha256=")
    assert not verify_signature(SECRET, BODY, digest)


def test_non_ascii_header_does_not_crash() -> None:
    assert not verify_signature(SECRET, BODY, "sha256=é")
