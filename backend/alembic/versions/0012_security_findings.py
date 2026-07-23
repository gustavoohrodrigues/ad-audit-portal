"""security_findings + finding_ingestions — camada normalizada de findings.

Revision ID: 0012_findings
Revises: 0011_security_scans
Create Date: 2026-07-23

Idempotente.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0012_findings"
down_revision = "0011_security_scans"
branch_labels = None
depends_on = None


def _has(name: str) -> bool:
    try:
        return name in inspect(op.get_bind()).get_table_names()
    except Exception:  # noqa: BLE001
        return False


def upgrade() -> None:
    if not _has("finding_ingestions"):
        op.create_table(
            "finding_ingestions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("ingestion_id", sa.String, nullable=False, unique=True),
            sa.Column("source_tool", sa.String, nullable=False),
            sa.Column("source_format", sa.String, nullable=False),
            sa.Column("asset_name", sa.String, nullable=True),
            sa.Column("environment", sa.String, nullable=False, server_default="unknown"),
            sa.Column("total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created", sa.Integer, nullable=False, server_default="0"),
            sa.Column("updated", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String, nullable=False, server_default="ok"),
            sa.Column("error", sa.String, nullable=True),
            sa.Column("created_by", sa.String, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_finding_ingestions_ingestion_id", "finding_ingestions", ["ingestion_id"])

    if not _has("security_findings"):
        op.create_table(
            "security_findings",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("fingerprint", sa.String, nullable=False),
            sa.Column("ingestion_id", sa.String, nullable=True),
            sa.Column("source_tool", sa.String, nullable=False, server_default="manual"),
            sa.Column("source_type", sa.String, nullable=True),
            sa.Column("category", sa.String, nullable=False, server_default="vulnerability"),
            sa.Column("subcategory", sa.String, nullable=True),
            sa.Column("asset_type", sa.String, nullable=False, server_default="host"),
            sa.Column("asset_id", sa.String, nullable=True),
            sa.Column("asset_name", sa.String, nullable=False, server_default="unknown"),
            sa.Column("environment", sa.String, nullable=False, server_default="unknown"),
            sa.Column("host_name", sa.String, nullable=True),
            sa.Column("service_name", sa.String, nullable=True),
            sa.Column("severity", sa.String, nullable=False, server_default="unknown"),
            sa.Column("confidence", sa.String, nullable=False, server_default="medium"),
            sa.Column("title", sa.String, nullable=False, server_default=""),
            sa.Column("description", sa.String, nullable=True),
            sa.Column("evidence", JSONB, nullable=False, server_default="{}"),
            sa.Column("remediation", sa.String, nullable=True),
            sa.Column("references", JSONB, nullable=False, server_default="[]"),
            sa.Column("cve", sa.String, nullable=True),
            sa.Column("cwe", sa.String, nullable=True),
            sa.Column("cvss", sa.Float, nullable=True),
            sa.Column("package_name", sa.String, nullable=True),
            sa.Column("installed_version", sa.String, nullable=True),
            sa.Column("fixed_version", sa.String, nullable=True),
            sa.Column("file_path", sa.String, nullable=True),
            sa.Column("config_path", sa.String, nullable=True),
            sa.Column("exploit_available", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("internet_exposed", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("privileged_context", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
            sa.Column("risk_band", sa.String, nullable=False, server_default="low"),
            sa.Column("occurrences", sa.Integer, nullable=False, server_default="1"),
            sa.Column("status", sa.String, nullable=False, server_default="open"),
            sa.Column("remediation_state", sa.String, nullable=False, server_default="none"),
            sa.Column("assignee", sa.String, nullable=True),
            sa.Column("suppressed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("suppression_reason", sa.String, nullable=True),
            sa.Column("suppressed_by", sa.String, nullable=True),
            sa.Column("tags", JSONB, nullable=False, server_default="[]"),
            sa.Column("correlation_id", sa.String, nullable=True),
            sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_finding_fp", "security_findings", ["fingerprint"])
        op.create_index("ix_finding_sev_status", "security_findings", ["severity", "status"])
        op.create_index("ix_finding_asset", "security_findings", ["asset_type", "asset_name"])
        op.create_index("ix_finding_cat", "security_findings", ["category"])
        op.create_index("ix_finding_lastseen", "security_findings", ["last_seen"])
        op.create_index("ix_security_findings_ingestion_id", "security_findings", ["ingestion_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS security_findings")
    op.execute("DROP TABLE IF EXISTS finding_ingestions")
