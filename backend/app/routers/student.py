"""Student-facing routes (RBAC: student).

Stub for now; M2 adds join-by-code, play sessions, and attempt submission here.
The router-level dependency enforces the student role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, require_student

router = APIRouter(
    prefix="/student",
    tags=["student"],
    dependencies=[Depends(require_student)],
)


@router.get("/me")
def whoami(user: CurrentUser = Depends(require_student)) -> dict:
    return {"role": user.role, "sub": user.sub, "email": user.email}
