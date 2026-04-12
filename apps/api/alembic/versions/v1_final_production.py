"""feat: production v1 schema

Revision ID: v1_final_production
Revises: 
Create Date: 2026-04-12 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'v1_final_production'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Clients & Portfolios
    op.create_table('clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clients_firm_id', 'clients', ['firm_id'], unique=False)

    op.create_table('portfolios',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('report_deadline', sa.Date(), nullable=True),
        sa.Column('report_r2_key', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_portfolios_client_id', 'portfolios', ['client_id'], unique=False)
    op.create_index('ix_portfolios_firm_id', 'portfolios', ['firm_id'], unique=False)

    op.create_table('portfolio_patents',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('patent_id', sa.UUID(), nullable=False),
        sa.Column('is_excluded', sa.Boolean(), nullable=False),
        sa.Column('exclusion_reason', sa.String(length=500), nullable=True),
        sa.Column('custom_commentary', sa.Text(), nullable=True),
        sa.Column('last_dd_score', sa.Integer(), nullable=True),
        sa.Column('last_dd_finding', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['patent_id'], ['patents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('portfolio_id', 'patent_id')
    )

    # 2. Analysis Engine
    op.create_table('analysis_workflows',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('patent_id', sa.UUID(), nullable=False),
        sa.Column('analysis_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('report_r2_key', sa.String(length=500), nullable=True),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_attorney_work_product', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patent_id'], ['patents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analysis_workflows_firm_id', 'analysis_workflows', ['firm_id'], unique=False)

    op.create_table('product_descriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('description_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['analysis_workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('claim_analysis_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=False),
        sa.Column('claim_id', sa.UUID(), nullable=False),
        sa.Column('claim_number', sa.Integer(), nullable=False),
        sa.Column('ai_finding', sa.Text(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('evidence_quotes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['patent_claims.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['analysis_workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Patent & Cache Schema Updates
    op.add_column('patents', sa.Column('client_id', sa.UUID(), nullable=True))
    op.add_column('patents', sa.Column('full_description', sa.Text(), nullable=True))
    op.create_index('ix_patents_client_id', 'patents', ['client_id'], unique=False)
    op.create_foreign_key('fk_patents_client', 'patents', 'clients', ['client_id'], ['id'], ondelete='SET NULL')

    op.add_column('public_patent_cache', sa.Column('full_description', sa.Text(), nullable=True))
    op.add_column('public_patent_cache', sa.Column('claims_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('public_patent_cache', sa.Column('priority_date', sa.Date(), nullable=True))
    op.add_column('public_patent_cache', sa.Column('publication_date', sa.Date(), nullable=True))

def downgrade() -> None:
    op.drop_table('claim_analysis_results')
    op.drop_table('product_descriptions')
    op.drop_table('analysis_workflows')
    op.drop_table('portfolio_patents')
    op.drop_table('portfolios')
    op.drop_table('clients')
    op.drop_column('patents', 'full_description')
    op.drop_column('patents', 'client_id')
    op.drop_column('public_patent_cache', 'publication_date')
    op.drop_column('public_patent_cache', 'priority_date')
    op.drop_column('public_patent_cache', 'claims_json')
    op.drop_column('public_patent_cache', 'full_description')
