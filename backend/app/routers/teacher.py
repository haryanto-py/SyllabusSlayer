"""Teacher-facing routes (RBAC: teacher).

Stub for now; M1/M3 add documents (upload/parse), campaigns (generate/review/assign),
and analytics endpoints here. The router-level dependency enforces the teacher role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, require_teacher

router = APIRouter(
    prefix="/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_teacher)],
)


@router.get("/me")
def whoami(user: CurrentUser = Depends(require_teacher)) -> dict:
    return {"role": user.role, "sub": user.sub, "email": user.email}
