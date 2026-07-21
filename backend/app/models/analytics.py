"""Modelos de histórico/tendência, entregas de notificação e watchlists."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SecurityScoreHistory(SQLModel, table=True):
    __tablename__ = "security_score_history"
    __table_args__ = (Index("uq_score_hist_day", "snapshot_date", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_date: date = Field(index=True)
    score: int
    grade: str
    factors: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    computed_from: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class PostureHistory(SQLModel, table=True):
    __tablename__ = "posture_history"
    __table_args__ = (Index("uq_posture_hist_day", "snapshot_date", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_date: date = Field(index=True)
    counts: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class NotificationDelivery(SQLModel, table=True):
    __tablename__ = "notification_deliveries"
    __table_args__ = (Index("ix_notif_created", "created_at"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    correlation_id: str = Field(index=True)
    channel: str                      # email | teams | slack | discord | winrm
    target: Optional[str] = None      # usuário/host/canal
    subject: Optional[str] = None
    status: str = Field(default="pending")   # pending | sent | failed
    error: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    justification: Optional[str] = None
    ticket_reference: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class ChatWebhook(SQLModel, table=True):
    """Webhook de chat registrado (Google Chat, e futuros)."""

    __tablename__ = "chat_webhooks"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    provider: str = Field(default="google_chat")  # google_chat | teams | slack | discord
    url: str                                       # webhook URL (não exibida na íntegra)
    enabled: bool = Field(default=True)
    health_alerts: bool = Field(default=True)      # recebe alertas automáticos de saúde
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class Watchlist(SQLModel, table=True):
    __tablename__ = "watchlists"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    owner: str
    created_at: datetime = Field(default_factory=_utcnow)


class WatchlistItem(SQLModel, table=True):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        Index("uq_watch_item", "watchlist_id", "entity_type", "entity_ref", unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    watchlist_id: int = Field(foreign_key="watchlists.id", index=True)
    entity_type: str          # user | group | computer
    entity_ref: str           # sAMAccountName / SID
    note: Optional[str] = None
    added_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
