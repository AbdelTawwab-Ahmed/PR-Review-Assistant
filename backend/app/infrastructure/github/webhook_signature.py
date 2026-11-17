import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    """Constant-time check of GitHub's X-Hub-Signature-256. Fails closed without a secret."""
    if not secret or not header:
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected.encode(), header.encode())
