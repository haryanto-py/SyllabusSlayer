"""Auth: verify Supabase-issued JWTs and expose role-based dependencies.

The Next.js client authenticates with Supabase Auth and sends the access token as
``Authorization: Bearer <jwt>``. We verify it here (HS256 with the project JWT
secret) and derive the role. In ``dev`` with no secret configured, verification is
skipped and a stub teacher identity is returned so the API is runnable offline.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    sub: str  # Supabase user id
    email: str | None
    role: str  # "teacher" | "student"


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    dev_role: str | None = Header(default=None, alias="X-Dev-Role"),
) -> CurrentUser:
    # Dev convenience: no secret configured -> stub identity (NEVER in prod). The
    # X-Dev-Role header lets the teacher/student apps act as their role until Supabase
    # auth lands in M3.
    if settings.env == "dev" and not settings.supabase_jwt_secret:
        role = dev_role if dev_role in ("teacher", "student") else "teacher"
        return CurrentUser(sub=f"dev-{role}", email=f"dev-{role}@local", role=role)

    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    try:
        claims = jwt.decode(
            creds.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:  # noqa: PERF203
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    # Supabase puts custom role in user_metadata / app_metadata depending on setup.
    role = (
        claims.get("user_role")
        or claims.get("app_metadata", {}).get("role")
        or claims.get("user_metadata", {}).get("role")
        or "student"
    )
    return CurrentUser(sub=claims.get("sub", ""), email=claims.get("email"), role=role)


def require_teacher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teacher role required")
    return user


def require_student(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student role required")
    return user
