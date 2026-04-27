"""fix missing columns in calls table (amd_result, amd_recovered, hangup_cause, ringing_at)

Revision ID: f1a2b3c4d5e7
Revises: d1a2b3c4d5e6
Create Date: 2026-04-27 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e7'
down_revision = 'd1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Use IF NOT EXISTS so this is safe to run even if some columns already exist
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS amd_result VARCHAR(50)")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS amd_recovered BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS hangup_cause VARCHAR(100)")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS ringing_at TIMESTAMP")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS answered_by VARCHAR(50)")


def downgrade():
    pass
