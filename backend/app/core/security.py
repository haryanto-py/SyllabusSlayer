"""Auth: verify Supabase-issued JWTs and expose role-based dependencies.

The Next.js apps authenticate with Supabase and send the access token as
``Authorization: Bearer <jwt>``. Verification supports the modern asymmetric flow
(JWKS endpoint, ES256/RS256) and the legacy HS256 shared secret. The app role
(teacher/student) is read from the token's ``user_metadata.role`` (set at signup).

When NO bearer token is present AND env=dev, a stub identity is returned so the API
is runnable offline — the ``X-Dev-Role`` / ``X-Dev-User`` headers pick the role and a
distinct identity. This dev shim never applies in prod and never overrides a real token.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)
_jwk_client: jwt.PyJWKClient | None = None


@dataclass
class CurrentUser:
    sub: str  # Supabase user id
    email: str | None
    role: str  # "teacher" | "student"


def _jwk() -> jwt.PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = jwt.PyJWKClient(settings.supabase_jwks_url)
    return _jwk_client


def _verify_token(token: str) -> CurrentUser:
    try:
        if settings.supabase_jwks_url:  # modern asymmetric keys
            signing_key = _jwk().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, signing_key, algorithms=["ES256", "RS256"], audience="authenticated"
            )
        elif settings.supabase_jwt_secret:  # legacy HS256
            claims = jwt.decode(
                token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
            )
        else:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "auth not configured")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc

    # NOTE: the top-level "role" claim is the Postgres role ("authenticated"); the app
    # role lives in user_metadata (set via signUp options.data.role).
    meta_role = claims.get("user_metadata", {}).get("role") or claims.get(
        "app_metadata", {}
    ).get("role")
    role = meta_role if meta_role in ("teacher", "student") else "student"
    return CurrentUser(sub=claims.get("sub", ""), email=claims.get("email"), role=role)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    dev_role: str | None = Header(default=None, alias="X-Dev-Role"),
    dev_user: str | None = Header(default=None, alias="X-Dev-User"),
) -> CurrentUser:
    if creds is not None:
        return _verify_token(creds.credentials)
    if settings.env == "dev":
        role = dev_role if dev_role in ("teacher", "student") else "teacher"
        sub = dev_user or f"dev-{role}"
        return CurrentUser(sub=sub, email=f"{sub}@local", role=role)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")


def require_teacher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teacher role required")
    return user


def require_student(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student role required")
    return user
