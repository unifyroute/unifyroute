"""Full consolidated schema

Revision ID: 001_full_schema
Revises:
Create Date: 2026-03-09 00:00:00.000000

This is the single consolidated migration that creates the complete UnifyRoute
database schema from scratch.  It supersedes all previous incremental migrations:
  - 001_consolidated_schema (7 core tables)
  - e7e89709f21c (chat_sessions, chat_messages)
  - b84eb3d51464 (rate_limit_rpm on gateway_keys)
  - 0a5746722fe4 (routing_configs)
  - bdcc5219d5d3 (prompt_json, response_text on request_logs)
  - 50c0fa74a505 (chat_sessions/messages – no-op, already present above)
  - 212342e9d042 (status, error_message on credentials)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_full_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type():
    """Return dialect-appropriate UUID column type."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return sa.String(36)
    return sa.Uuid()


def upgrade() -> None:
    """Create the full UnifyRoute schema from scratch."""
    uuid_t = _uuid_type()

    # ── gateway_keys ──────────────────────────────────────────────────────────
    op.create_table(
        "gateway_keys",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("raw_token", sa.Text(), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gateway_keys_key_hash", "gateway_keys", ["key_hash"], unique=True)

    # ── providers ────────────────────────────────────────────────────────────
    op.create_table(
        "providers",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("oauth_meta", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("auth_type IN ('api_key', 'oauth2')", name="check_auth_type"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_providers_name", "providers", ["name"], unique=True)

    # ── credentials ──────────────────────────────────────────────────────────
    op.create_table(
        "credentials",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("provider_id", uuid_t, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=False),
        sa.Column("secret_enc", sa.LargeBinary(), nullable=False),
        sa.Column("iv", sa.LargeBinary(), nullable=True),
        sa.Column("oauth_meta", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),          # e.g. "ok", "error", "unverified"
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── provider_models ───────────────────────────────────────────────────────
    op.create_table(
        "provider_models",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("provider_id", uuid_t, nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("input_cost_per_1k", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("output_cost_per_1k", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False),
        sa.Column("supports_functions", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        # Allow empty string tier for "untiered" models
        sa.CheckConstraint("tier IN ('lite', 'base', 'thinking', '')", name="check_tier"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── quota_snapshots ───────────────────────────────────────────────────────
    op.create_table(
        "quota_snapshots",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("credential_id", uuid_t, nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("tokens_remaining", sa.BigInteger(), nullable=True),
        sa.Column("requests_remaining", sa.Integer(), nullable=True),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "polled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── request_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "request_logs",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("client_key_id", uuid_t, nullable=True),
        sa.Column("credential_id", uuid_t, nullable=True),
        sa.Column("model_alias", sa.Text(), nullable=False),
        sa.Column("actual_model", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("prompt_json", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_key_id"], ["gateway_keys.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── brain_configs ─────────────────────────────────────────────────────────
    op.create_table(
        "brain_configs",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("provider_id", uuid_t, nullable=False),
        sa.Column("credential_id", uuid_t, nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["credentials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── chat_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── chat_messages ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("session_id", uuid_t, nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── routing_configs ───────────────────────────────────────────────────────
    op.create_table(
        "routing_configs",
        sa.Column("id", uuid_t, nullable=False),
        sa.Column("yaml_content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all UnifyRoute tables."""
    op.drop_table("routing_configs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("brain_configs")
    op.drop_table("request_logs")
    op.drop_table("quota_snapshots")
    op.drop_table("provider_models")
    op.drop_table("credentials")
    op.drop_index("ix_providers_name", table_name="providers")
    op.drop_table("providers")
    op.drop_index("ix_gateway_keys_key_hash", table_name="gateway_keys")
    op.drop_table("gateway_keys")
