"""Initial Phase 7 Schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('hashed_password', sa.String(length=256), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index('idx_users_role', 'users', ['role'], unique=False)
    op.create_index('idx_users_username', 'users', ['username'], unique=False)

    # 2. wells
    op.create_table(
        'wells',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('well_name', sa.String(length=128), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=True),
        sa.Column('district', sa.String(length=64), nullable=True),
        sa.Column('field', sa.String(length=128), nullable=True),
        sa.Column('block', sa.String(length=128), nullable=True),
        sa.Column('basin', sa.String(length=128), nullable=True),
        sa.Column('operator', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=True),
        sa.Column('well_type', sa.String(length=64), nullable=True),
        sa.Column('trajectory_type', sa.String(length=64), nullable=True),
        sa.Column('total_depth', sa.Float(), nullable=True),
        sa.Column('spud_date', sa.String(length=32), nullable=True),
        sa.Column('completion_date', sa.String(length=32), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('is_canonical', sa.Boolean(), nullable=True),
        sa.Column('is_new_well', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('well_id')
    )
    op.create_index('idx_wells_basin', 'wells', ['basin'], unique=False)
    op.create_index('idx_wells_field', 'wells', ['field'], unique=False)
    op.create_index('idx_wells_operator', 'wells', ['operator'], unique=False)
    op.create_index('idx_wells_well_id', 'wells', ['well_id'], unique=False)
    op.create_index('idx_wells_well_name', 'wells', ['well_name'], unique=False)

    # 3. well_geology
    op.create_table(
        'well_geology',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('formation_name', sa.String(length=128), nullable=True),
        sa.Column('lithology', sa.String(length=128), nullable=True),
        sa.Column('depth_from', sa.Float(), nullable=True),
        sa.Column('depth_to', sa.Float(), nullable=True),
        sa.Column('thickness', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_geology_formation', 'well_geology', ['formation_name'], unique=False)
    op.create_index('idx_geology_well_depth', 'well_geology', ['well_id', 'depth_from', 'depth_to'], unique=False)
    op.create_index('idx_geology_well_id', 'well_geology', ['well_id'], unique=False)

    # 4. well_formations
    op.create_table(
        'well_formations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('formation_name', sa.String(length=128), nullable=False),
        sa.Column('top_depth_md', sa.Float(), nullable=True),
        sa.Column('bottom_depth_md', sa.Float(), nullable=True),
        sa.Column('age_era', sa.String(length=64), nullable=True),
        sa.Column('permeability_class', sa.String(length=64), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_formations_top_depth', 'well_formations', ['well_id', 'top_depth_md'], unique=False)
    op.create_index('idx_formations_well_id', 'well_formations', ['well_id'], unique=False)

    # 5. historical_events
    op.create_table(
        'historical_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_subtype', sa.String(length=64), nullable=True),
        sa.Column('depth_md', sa.Float(), nullable=True),
        sa.Column('depth_from', sa.Float(), nullable=True),
        sa.Column('depth_to', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_document_id', sa.String(length=64), nullable=True),
        sa.Column('event_date', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id')
    )
    op.create_index('idx_events_well_id', 'historical_events', ['well_id'], unique=False)

    # 6. daily_drilling_parameters
    op.create_table(
        'daily_drilling_parameters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('recorded_date', sa.String(length=32), nullable=True),
        sa.Column('depth_md', sa.Float(), nullable=True),
        sa.Column('progress_m', sa.Float(), nullable=True),
        sa.Column('wob_klbf', sa.Float(), nullable=True),
        sa.Column('rpm', sa.Float(), nullable=True),
        sa.Column('rop_m_hr', sa.Float(), nullable=True),
        sa.Column('torque_kftlb', sa.Float(), nullable=True),
        sa.Column('standpipe_pressure_psi', sa.Float(), nullable=True),
        sa.Column('flow_rate_gpm', sa.Float(), nullable=True),
        sa.Column('mud_weight_ppg', sa.Float(), nullable=True),
        sa.Column('operation_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_daily_well_depth', 'daily_drilling_parameters', ['well_id', 'depth_md'], unique=False)

    # 7. mud_logging
    op.create_table(
        'mud_logging',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('depth_md', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.String(length=32), nullable=True),
        sa.Column('total_gas_units', sa.Float(), nullable=True),
        sa.Column('c1_methane_ppm', sa.Float(), nullable=True),
        sa.Column('c2_ethane_ppm', sa.Float(), nullable=True),
        sa.Column('c3_propane_ppm', sa.Float(), nullable=True),
        sa.Column('ic4_isobutane_ppm', sa.Float(), nullable=True),
        sa.Column('nc4_normalbutane_ppm', sa.Float(), nullable=True),
        sa.Column('c5_pentane_ppm', sa.Float(), nullable=True),
        sa.Column('flow_show_pct', sa.Float(), nullable=True),
        sa.Column('pit_volume_m3', sa.Float(), nullable=True),
        sa.Column('lithology_observed', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_mudlog_well_depth', 'mud_logging', ['well_id', 'depth_md'], unique=False)

    # 8. well_completion_wcr
    op.create_table(
        'well_completion_wcr',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('document_id', sa.String(length=64), nullable=True),
        sa.Column('casing_size_inch', sa.Float(), nullable=True),
        sa.Column('casing_depth_m', sa.Float(), nullable=True),
        sa.Column('tubing_size_inch', sa.Float(), nullable=True),
        sa.Column('perforation_interval_top_m', sa.Float(), nullable=True),
        sa.Column('perforation_interval_bottom_m', sa.Float(), nullable=True),
        sa.Column('reservoir_name', sa.String(length=128), nullable=True),
        sa.Column('initial_production_oil_bopd', sa.Float(), nullable=True),
        sa.Column('initial_production_gas_mscfd', sa.Float(), nullable=True),
        sa.Column('initial_reservoir_pressure_psi', sa.Float(), nullable=True),
        sa.Column('completion_type', sa.String(length=64), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=True),
        sa.Column('raw_payload_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_wcr_well_id', 'well_completion_wcr', ['well_id'], unique=False)

    # 9. documents
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=256), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=True),
        sa.Column('document_type', sa.String(length=64), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=64), nullable=True),
        sa.Column('approved_by', sa.String(length=64), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )
    op.create_index('idx_docs_doc_id', 'documents', ['document_id'], unique=False)
    op.create_index('idx_docs_status', 'documents', ['approval_status'], unique=False)

    # 10. document_chunks
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chunk_id', sa.String(length=64), nullable=False),
        sa.Column('document_id', sa.String(length=64), nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_name', sa.String(length=128), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('formation', sa.String(length=128), nullable=True),
        sa.Column('depth_from', sa.Float(), nullable=True),
        sa.Column('depth_to', sa.Float(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=False),
        sa.Column('embedding_vector', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chunk_id')
    )
    op.create_index('idx_chunks_doc_id', 'document_chunks', ['document_id'], unique=False)

    # 11. risk_recommendations
    op.create_table(
        'risk_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('risk_id', sa.String(length=64), nullable=True),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('hazard_type', sa.String(length=64), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=32), nullable=False),
        sa.Column('predicted_event', sa.String(length=128), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('supporting_event_id', sa.String(length=64), nullable=True),
        sa.Column('model_version', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('risk_id')
    )
    op.create_index('idx_risks_well_id', 'risk_recommendations', ['well_id'], unique=False)

    # 12. telemetry_records
    op.create_table(
        'telemetry_records',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('depth_md', sa.Float(), nullable=False),
        sa.Column('rop', sa.Float(), nullable=True),
        sa.Column('wob', sa.Float(), nullable=True),
        sa.Column('rpm', sa.Float(), nullable=True),
        sa.Column('torque', sa.Float(), nullable=True),
        sa.Column('spp', sa.Float(), nullable=True),
        sa.Column('mud_flow_in', sa.Float(), nullable=True),
        sa.Column('mud_flow_out', sa.Float(), nullable=True),
        sa.Column('gas', sa.Float(), nullable=True),
        sa.Column('pump_pressure', sa.Float(), nullable=True),
        sa.Column('hookload', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('quality_status', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_telem_well_time', 'telemetry_records', ['well_id', 'timestamp'], unique=False)

    # 13. well_live_state
    op.create_table(
        'well_live_state',
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('latest_depth_md', sa.Float(), nullable=True),
        sa.Column('connection_status', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('data_quality', sa.String(length=32), nullable=True),
        sa.Column('last_seen_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latest_telemetry_json', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('well_id')
    )

    # 14. alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alert_id', sa.String(length=64), nullable=False),
        sa.Column('well_id', sa.String(length=32), nullable=False),
        sa.Column('depth_md', sa.Float(), nullable=False),
        sa.Column('alert_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('signal_source', sa.String(length=64), nullable=True),
        sa.Column('model_source', sa.String(length=64), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=64), nullable=True),
        sa.Column('closed_by', sa.String(length=64), nullable=True),
        sa.Column('acknowledgement_note', sa.Text(), nullable=True),
        sa.Column('closure_note', sa.Text(), nullable=True),
        sa.Column('evidence_ids', sa.JSON(), nullable=True),
        sa.Column('live_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['well_id'], ['wells.well_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alert_id')
    )
    op.create_index('idx_alerts_severity', 'alerts', ['severity'], unique=False)
    op.create_index('idx_alerts_well_status', 'alerts', ['well_id', 'status'], unique=False)

    # 15. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=True),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.String(length=64), nullable=True),
        sa.Column('well_id', sa.String(length=32), nullable=True),
        sa.Column('depth_md', sa.Float(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_action', 'audit_logs', ['action'], unique=False)
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'], unique=False)
    op.create_index('idx_audit_user', 'audit_logs', ['username'], unique=False)
    op.create_index('idx_audit_well_id', 'audit_logs', ['well_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('alerts')
    op.drop_table('well_live_state')
    op.drop_table('telemetry_records')
    op.drop_table('risk_recommendations')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('well_completion_wcr')
    op.drop_table('mud_logging')
    op.drop_table('daily_drilling_parameters')
    op.drop_table('historical_events')
    op.drop_table('well_formations')
    op.drop_table('well_geology')
    op.drop_table('wells')
    op.drop_table('users')
