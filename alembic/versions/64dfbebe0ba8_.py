"""empty message

Revision ID: 64dfbebe0ba8
Revises: 409c438d456a
Create Date: 2023-07-13 14:51:52.233972

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64dfbebe0ba8'
down_revision = '409c438d456a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('language_preference', sa.String(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'language_preference')
    # ### end Alembic commands ###