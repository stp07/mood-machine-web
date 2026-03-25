"""Simple session-based authentication for Mood Machine Web."""
import hashlib
import secrets
import time
import logging

log = logging.getLogger("mood-machine")

# In-memory session store (sufficient for single-instance deployment)
# session_token -> {"username": str, "created_at": float}
_sessions: dict[str, dict] = {}

SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Hash a password with SHA-256. For initial config setup."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Check a password against its hash."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == hashed


def create_session(username: str) -> str:
    """Create a new session and return the token."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"username": username, "created_at": time.time()}
    log.info(f"Session created for user '{username}'")
    return token


def validate_session(token: str | None) -> str | None:
    """Validate a session token. Returns username if valid, None otherwise."""
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if time.time() - session["created_at"] > SESSION_MAX_AGE:
        _sessions.pop(token, None)
        return None
    return session["username"]


def destroy_session(token: str | None) -> None:
    """Remove a session."""
    if token:
        _sessions.pop(token, None)


def authenticate(username: str, password: str, config: dict) -> str | None:
    """
    Authenticate against config.yaml credentials.
    Returns session token on success, None on failure.
    """
    auth_config = config.get("auth", {})
    users = auth_config.get("users", [])

    for user in users:
        if user.get("username") == username:
            stored_hash = user.get("password_hash", "")
            if verify_password(password, stored_hash):
                return create_session(username)
            else:
                log.warning(f"Failed login attempt for user '{username}'")
                return None

    log.warning(f"Login attempt for unknown user '{username}'")
    return None
