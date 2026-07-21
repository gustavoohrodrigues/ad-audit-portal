"""Modelo de MFA (TOTP) por usuário da aplicação (chaveado por sAMAccountName)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserMFA(SQLModel, table=True):
    __tablename__ = "user_mfa"

    id: Optional[int] = Field(default=None, primary_key=True)
    sam_account_name: str = Field(index=True, unique=True)
    secret: str
    enabled: bool = Field(default=False)
    confirmed_at: Optional[datetime] = None
    backup_codes: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
