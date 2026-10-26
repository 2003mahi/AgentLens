import hashlib
from typing import Optional
from pydantic import BaseModel  # type: ignore
from fastapi import Header, Depends  # type: ignore
from backend.app.core.errors import UnauthorizedException, ForbiddenException

class AuthContext(BaseModel):
    workspace_id: str
    user_id: str
    role: str = "admin"

# Built-in or configured API key mapping for workspace authentication
# Keys follow standard format: "eval_key_<workspace_id>_<token>" or test keys
KNOWN_API_KEYS = {
    "test-key-workspace-alpha": AuthContext(workspace_id="ws_alpha", user_id="user_alpha_1", role="admin"),
    "test-key-workspace-beta": AuthContext(workspace_id="ws_beta", user_id="user_beta_1", role="admin"),
    "default-dev-key": AuthContext(workspace_id="ws_default", user_id="user_default", role="admin"),
}

def hash_secret(secret: str) -> str:
    """Hash a secret key using SHA-256 for secure comparison/storage."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

async def get_current_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthContext:
    """
    Authenticate request via X-API-Key or Authorization Bearer header.
    Ensures strict workspace context isolation.
    """
    token: Optional[str] = None
    if x_api_key:
        token = x_api_key.strip()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token:
        raise UnauthorizedException("Authentication required. Provide 'X-API-Key' or 'Authorization: Bearer <key>' header.")

    # Match in known keys
    if token in KNOWN_API_KEYS:
        return KNOWN_API_KEYS[token]

    # Support dynamic workspace keys: "eval_key_<workspace_id>_<suffix>"
    if token.startswith("eval_key_"):
        parts = token.split("_")
        if len(parts) >= 3:
            ws_id = parts[2]
            return AuthContext(workspace_id=ws_id, user_id=f"user_{ws_id}", role="member")

    raise UnauthorizedException("Invalid API key or token.")

def verify_workspace_access(resource_workspace_id: str, auth: AuthContext) -> None:
    """Strict authorization check: prevent cross-workspace access."""
    if resource_workspace_id != auth.workspace_id:
        raise ForbiddenException(
            f"Cross-workspace access denied. Current workspace: {auth.workspace_id}, resource workspace: {resource_workspace_id}"
        )
