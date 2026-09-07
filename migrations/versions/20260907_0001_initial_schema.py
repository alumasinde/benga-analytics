"""Create the initial BengaAnalytics schema."""
from alembic import op
from database.base import metadata
import database.models.schema

revision = '20260907_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)
