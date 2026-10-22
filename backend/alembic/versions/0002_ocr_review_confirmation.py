
"""Require faculty confirmation before evaluating OCR text."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = {
        row["name"]
        for row in sa.inspect(conn).get_columns("submissions")
    }

    if "ocr_review_confirmed" not in columns:
        op.add_column(
            "submissions",
            sa.Column(
                "ocr_review_confirmed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

def downgrade() -> None:
    op.drop_column("submissions", "ocr_review_confirmed")
