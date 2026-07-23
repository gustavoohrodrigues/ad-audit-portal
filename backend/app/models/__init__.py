"""Registra todos os modelos no metadata do SQLModel (import-side-effect)."""
from app.models.directory import ADComputer, ADGroup, ADUser, DomainController
from app.models.enums import (
    AlertStatus,
    EventType,
    InvestigationStatus,
    Role,
    Severity,
    SourceStatus,
)
from app.models.event import NormalizedEvent
from app.models.ops import (
    ADSyncCheckpoint,
    Alert,
    AnalystNote,
    CollectionCheckpoint,
    EventSource,
    InternalAuditLog,
    LockoutInvestigation,
    ReportExport,
    RetentionPolicy,
    RiskRule,
    TicketLink,
)
from app.models.analytics import (
    ChatWebhook,
    NotificationDelivery,
    PostureHistory,
    SecurityScoreHistory,
    Watchlist,
    WatchlistItem,
)
from app.models.security import SecurityScan, UserMFA
from app.models.findings import FindingIngestion, SecurityFinding

__all__ = [
    "ADComputer",
    "ADGroup",
    "ADUser",
    "DomainController",
    "NormalizedEvent",
    "Alert",
    "AnalystNote",
    "CollectionCheckpoint",
    "EventSource",
    "InternalAuditLog",
    "LockoutInvestigation",
    "ReportExport",
    "RetentionPolicy",
    "RiskRule",
    "TicketLink",
    "UserMFA",
    "NotificationDelivery",
    "PostureHistory",
    "SecurityScoreHistory",
    "Watchlist",
    "WatchlistItem",
    "ChatWebhook",
    "ADSyncCheckpoint",
    "AlertStatus",
    "EventType",
    "InvestigationStatus",
    "Role",
    "Severity",
    "SourceStatus",
]
