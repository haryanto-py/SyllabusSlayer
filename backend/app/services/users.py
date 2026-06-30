"""Map an authenticated identity (Supabase JWT or dev shim) to a User row."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.security import CurrentUser
from app.models.tables import User, UserRole


def get_or_create_user(session: Session, current: CurrentUser) -> User:
    user = session.exec(select(User).where(User.auth_provider_id == current.sub)).first()
    if user:
        return user
    valid_roles = {r.value for r in UserRole}
    role = UserRole(current.role) if current.role in valid_roles else UserRole.student
    user = User(
        email=current.email or f"{current.sub}@local",
        role=role,
        display_name=(current.email or current.sub).split("@")[0],
        auth_provider_id=current.sub,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
