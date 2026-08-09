from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class OnboardingStepRead(BaseModel):
    key: str
    completed: bool
    kind: str
    skipped: bool
    first_seen_at: datetime | None
    last_seen_at: datetime | None


class OnboardingProgressRead(BaseModel):
    id: uuid.UUID
    onboarding_type: str
    current_step: str | None
    started_at: datetime
    completed_at: datetime | None
    dismissed_at: datetime | None
    version: int
    percent_complete: int
    steps: list[OnboardingStepRead]
