""" v1_1_0

Revision ID: f83081dbea18
Revises: ac68493869d4
Create Date: 2023-04-21 07:09:37.656321

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f83081dbea18'
down_revision = 'ac68493869d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('server_session',
    sa.Column('guid', sa.String(length=1024), nullable=False),
    sa.Column('valid_until', sa.DateTime(), nullable=False),
    sa.Column('is_valid', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_server_session')),
    sa.UniqueConstraint('guid', name=op.f('uq_server_session_guid'))
    )
    op.create_table('attachment',
    sa.Column('file_name', sa.String(length=1024), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('dataset_id', sa.Integer(), nullable=True),
    sa.Column('storage_name', sa.String(length=1024), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('modified_date', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], name=op.f('fk_attachment_created_by_user')),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], name=op.f('fk_attachment_dataset_id_dataset')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attachment'))
    )
    op.add_column('dataset', sa.Column('activated_item_id', sa.Integer(), nullable=True))
    op.add_column('metadata_edition', sa.Column('approval_item_id', sa.Integer(), nullable=True))
    op.add_column('workflow_decision', sa.Column('comments', sa.Text(), nullable=True))
    op.add_column('workflow_decision', sa.Column('attachment_id', sa.Integer(), nullable=True))
    try:
        op.create_foreign_key(op.f('fk_dataset_activated_item_id_workflow_item'), 'dataset', 'workflow_item', ['activated_item_id'], ['id'])
        op.create_foreign_key(op.f('fk_metadata_edition_approval_item_id_workflow_item'), 'metadata_edition', 'workflow_item', ['approval_item_id'], ['id'])
        op.create_foreign_key(op.f('fk_workflow_decision_attachment_id_attachment'), 'workflow_decision', 'attachment', ['attachment_id'], ['id'])
    except NotImplementedError as ex:
        if "SQLite dialect" not in str(ex):
            raise ex
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    try:
        op.drop_constraint(op.f('fk_workflow_decision_attachment_id_attachment'), 'workflow_decision', type_='foreignkey')
        op.drop_constraint(op.f('fk_metadata_edition_approval_item_id_workflow_item'), 'metadata_edition', type_='foreignkey')
        op.drop_constraint(op.f('fk_dataset_activated_item_id_workflow_item'), 'dataset', type_='foreignkey')
    except NotImplementedError as ex:
        if "SQLite dialect" not in str(ex):
            raise ex
    op.drop_column('workflow_decision', 'attachment_id')
    op.drop_column('workflow_decision', 'comments')
    op.drop_column('metadata_edition', 'approval_item_id')
    op.drop_column('dataset', 'activated_item_id')
    op.drop_table('attachment')
    op.drop_table('server_session')
    # ### end Alembic commands ###
