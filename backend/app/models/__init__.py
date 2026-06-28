"""SQLModel tables. Importing this package registers all tables on the metadata."""

from app.models.tables import (
    Assignment,
    Campaign,
    CampaignStatus,
    Chunk,
    Class,
    Document,
    DocumentStatus,
    Enrollment,
    PlaySession,
    QuestionAttempt,
    SessionStatus,
    StudentProgress,
    User,
    UserRole,
)

__all__ = [
    "Assignment",
    "Campaign",
    "CampaignStatus",
    "Chunk",
    "Class",
    "Document",
    "DocumentStatus",
    "Enrollment",
    "PlaySession",
    "QuestionAttempt",
    "SessionStatus",
    "StudentProgress",
    "User",
    "UserRole",
]
