"""empty message

Revision ID: fa16fb27765f
Revises: b68dade1fe82
Create Date: 2023-03-27 14:05:23.970803

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa16fb27765f'
down_revision = 'b68dade1fe82'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('config_registry',
    sa.Column('obj_type', sa.String(length=255), nullable=True),
    sa.Column('obj_name', sa.String(length=255), nullable=True),
    sa.Column('config', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_config_registry')),
    sa.UniqueConstraint('obj_type', 'obj_name', name='unique_registry_name_type')
    )
    op.create_index(op.f('ix_config_registry_obj_name'), 'config_registry', ['obj_name'], unique=False)
    op.create_index(op.f('ix_config_registry_obj_type'), 'config_registry', ['obj_type'], unique=False)
    # ### end Alembic commands ###

def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_config_registry_obj_type'), table_name='config_registry')
    op.drop_index(op.f('ix_config_registry_obj_name'), table_name='config_registry')
    op.drop_table('config_registry')
    # ### end Alembic commands ###