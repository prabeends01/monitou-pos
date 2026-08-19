import uuid

from pydantic import BaseModel

from app.models.user import UserRole


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
