"""Frozen deterministic installation DDL for revision 20260713_120000.

Generated once from the approved 20260713_120000 model state.  This file is a
static snapshot: runtime code must never import ORM metadata to regenerate it.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic.operations import Operations

FROZEN_REVISION = "20260713_120000"
SCHEMA_SNAPSHOT_VERSION = 1


def create_frozen_schema(operations: Operations) -> None:
    operations.create_table('assertion_execution_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('test_case_id', sa.String(length=64), nullable=False),
    sa.Column('intent_type', sa.String(length=80), nullable=False),
    sa.Column('scenario', sa.String(length=20), nullable=False),
    sa.Column('behavior_code', sa.String(length=120), nullable=False),
    sa.Column('behavior_version', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('compiled_assertions', sa.JSON(), nullable=False),
    sa.Column('execution_result', sa.JSON(), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_assertion_execution_logs')
    )
    operations.create_index(operations.f('ix_assertion_execution_logs_executed_at'), 'assertion_execution_logs', ['executed_at'], unique=False)
    operations.create_index(operations.f('ix_assertion_execution_logs_test_case_id'), 'assertion_execution_logs', ['test_case_id'], unique=False)
    operations.create_table('behavior_registry',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('behavior_code', sa.String(length=120), nullable=False),
    sa.Column('intent_type', sa.String(length=80), nullable=False),
    sa.Column('scenario', sa.String(length=20), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('domain', sa.String(length=40), nullable=False),
    sa.Column('context_filter', sa.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=255), nullable=False),
    sa.Column('capabilities', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_behavior_registry')
    )
    operations.create_index(operations.f('ix_behavior_registry_behavior_code'), 'behavior_registry', ['behavior_code'], unique=False)
    operations.create_index(operations.f('ix_behavior_registry_created_at'), 'behavior_registry', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_behavior_registry_intent_type'), 'behavior_registry', ['intent_type'], unique=False)
    operations.create_index(operations.f('ix_behavior_registry_page_code'), 'behavior_registry', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_behavior_registry_status'), 'behavior_registry', ['status'], unique=False)
    operations.create_table('orchestration_tasks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('task_name', sa.String(length=255), nullable=False),
    sa.Column('input_source_type', sa.String(length=80), nullable=False),
    sa.Column('input_source_payload', sa.JSON(), nullable=False),
    sa.Column('agent_config', sa.JSON(), nullable=False),
    sa.Column('asset_binding', sa.JSON(), nullable=False),
    sa.Column('execution_config', sa.JSON(), nullable=False),
    sa.Column('preview_snapshot', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_orchestration_tasks')
    )
    operations.create_index(operations.f('ix_orchestration_tasks_created_at'), 'orchestration_tasks', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_orchestration_tasks_created_by'), 'orchestration_tasks', ['created_by'], unique=False)
    operations.create_index(operations.f('ix_orchestration_tasks_input_source_type'), 'orchestration_tasks', ['input_source_type'], unique=False)
    operations.create_index(operations.f('ix_orchestration_tasks_status'), 'orchestration_tasks', ['status'], unique=False)
    operations.create_index(operations.f('ix_orchestration_tasks_task_name'), 'orchestration_tasks', ['task_name'], unique=False)
    operations.create_table('page_object_candidate_elements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('candidate_key', sa.String(length=120), nullable=False),
    sa.Column('group_key', sa.String(length=160), nullable=False),
    sa.Column('raw_locator_type', sa.String(length=30), nullable=False),
    sa.Column('raw_locator_value', sa.Text(), nullable=False),
    sa.Column('raw_role', sa.String(length=60), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('dom_signature', sa.String(length=160), nullable=False),
    sa.Column('route', sa.String(length=256), nullable=False),
    sa.Column('step_hit_count', sa.Integer(), nullable=False),
    sa.Column('quality_score', sa.Integer(), nullable=False),
    sa.Column('quality_tier', sa.String(length=20), nullable=False),
    sa.Column('risk_tags_json', sa.JSON(), nullable=False),
    sa.Column('recommended_action', sa.String(length=20), nullable=False),
    sa.Column('candidate_status', sa.String(length=20), nullable=False),
    sa.Column('ingest_block_reason', sa.Text(), nullable=False),
    sa.Column('proposed_element_code', sa.String(length=80), nullable=False),
    sa.Column('proposed_element_name', sa.String(length=120), nullable=False),
    sa.Column('business_type_guess', sa.String(length=40), nullable=False),
    sa.Column('probe_status', sa.String(length=20), nullable=False),
    sa.Column('probe_match_count', sa.Integer(), nullable=False),
    sa.Column('probe_visible', sa.Boolean(), nullable=False),
    sa.Column('probe_interactable', sa.Boolean(), nullable=False),
    sa.Column('merged_to_element_code', sa.String(length=80), nullable=False),
    sa.Column('promoted_element_code', sa.String(length=80), nullable=False),
    sa.Column('reviewed_by', sa.String(length=60), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_page_object_candidate_elements'),
    sa.UniqueConstraint('session_id', 'candidate_key', name='uq_page_object_candidate_elements_identity')
    )
    operations.create_index(operations.f('ix_page_object_candidate_elements_candidate_key'), 'page_object_candidate_elements', ['candidate_key'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_client'), 'page_object_candidate_elements', ['client'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_created_at'), 'page_object_candidate_elements', ['created_at'], unique=False)
    operations.create_index('ix_page_object_candidate_elements_group_key', 'page_object_candidate_elements', ['group_key'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_page_code'), 'page_object_candidate_elements', ['page_code'], unique=False)
    operations.create_index('ix_page_object_candidate_elements_page_status', 'page_object_candidate_elements', ['project_code', 'client', 'page_code', 'candidate_status'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_project_code'), 'page_object_candidate_elements', ['project_code'], unique=False)
    operations.create_index('ix_page_object_candidate_elements_quality_score', 'page_object_candidate_elements', ['quality_score'], unique=False)
    operations.create_index('ix_page_object_candidate_elements_recommended_action', 'page_object_candidate_elements', ['recommended_action'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_reviewed_at'), 'page_object_candidate_elements', ['reviewed_at'], unique=False)
    operations.create_index('ix_page_object_candidate_elements_session_id', 'page_object_candidate_elements', ['session_id'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_elements_updated_at'), 'page_object_candidate_elements', ['updated_at'], unique=False)
    operations.create_table('page_object_candidate_groups',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('group_key', sa.String(length=160), nullable=False),
    sa.Column('proposed_element_code', sa.String(length=80), nullable=False),
    sa.Column('proposed_element_name', sa.String(length=120), nullable=False),
    sa.Column('business_type_guess', sa.String(length=40), nullable=False),
    sa.Column('business_domain_guess', sa.String(length=40), nullable=False),
    sa.Column('quality_tier', sa.String(length=20), nullable=False),
    sa.Column('max_score', sa.Integer(), nullable=False),
    sa.Column('avg_score', sa.Integer(), nullable=False),
    sa.Column('session_count', sa.Integer(), nullable=False),
    sa.Column('candidate_count', sa.Integer(), nullable=False),
    sa.Column('recommended_action', sa.String(length=20), nullable=False),
    sa.Column('promotion_status', sa.String(length=20), nullable=False),
    sa.Column('route_scope', sa.String(length=256), nullable=False),
    sa.Column('top_locator_source', sa.String(length=20), nullable=False),
    sa.Column('top_locator_type', sa.String(length=30), nullable=False),
    sa.Column('top_locator_value', sa.Text(), nullable=False),
    sa.Column('top_role', sa.String(length=60), nullable=False),
    sa.Column('risk_tags_json', sa.JSON(), nullable=False),
    sa.Column('sample_texts_json', sa.JSON(), nullable=False),
    sa.Column('matched_existing_element_code', sa.String(length=80), nullable=False),
    sa.Column('reviewed_by', sa.String(length=60), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=False),
    sa.Column('latest_session_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_page_object_candidate_groups'),
    sa.UniqueConstraint('project_code', 'client', 'page_code', 'group_key', name='uq_page_object_candidate_groups_identity')
    )
    operations.create_index(operations.f('ix_page_object_candidate_groups_client'), 'page_object_candidate_groups', ['client'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_created_at'), 'page_object_candidate_groups', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_group_key'), 'page_object_candidate_groups', ['group_key'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_latest_session_id'), 'page_object_candidate_groups', ['latest_session_id'], unique=False)
    operations.create_index('ix_page_object_candidate_groups_matched_element', 'page_object_candidate_groups', ['matched_existing_element_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_matched_existing_element_code'), 'page_object_candidate_groups', ['matched_existing_element_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_page_code'), 'page_object_candidate_groups', ['page_code'], unique=False)
    operations.create_index('ix_page_object_candidate_groups_page_quality', 'page_object_candidate_groups', ['project_code', 'client', 'page_code', 'quality_tier'], unique=False)
    operations.create_index('ix_page_object_candidate_groups_page_status', 'page_object_candidate_groups', ['project_code', 'client', 'page_code', 'promotion_status'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_project_code'), 'page_object_candidate_groups', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_promotion_status'), 'page_object_candidate_groups', ['promotion_status'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_quality_tier'), 'page_object_candidate_groups', ['quality_tier'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_reviewed_at'), 'page_object_candidate_groups', ['reviewed_at'], unique=False)
    operations.create_index(operations.f('ix_page_object_candidate_groups_updated_at'), 'page_object_candidate_groups', ['updated_at'], unique=False)
    operations.create_table('page_object_governance_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_key', sa.String(length=160), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('operator', sa.String(length=60), nullable=False),
    sa.Column('before_payload', sa.JSON(), nullable=False),
    sa.Column('after_payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_page_object_governance_logs')
    )
    operations.create_index('ix_page_object_governance_logs_action', 'page_object_governance_logs', ['action'], unique=False)
    operations.create_index(operations.f('ix_page_object_governance_logs_client'), 'page_object_governance_logs', ['client'], unique=False)
    operations.create_index(operations.f('ix_page_object_governance_logs_created_at'), 'page_object_governance_logs', ['created_at'], unique=False)
    operations.create_index('ix_page_object_governance_logs_entity', 'page_object_governance_logs', ['entity_type', 'entity_key'], unique=False)
    operations.create_index(operations.f('ix_page_object_governance_logs_operator'), 'page_object_governance_logs', ['operator'], unique=False)
    operations.create_index('ix_page_object_governance_logs_page', 'page_object_governance_logs', ['project_code', 'client', 'page_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_governance_logs_page_code'), 'page_object_governance_logs', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_governance_logs_project_code'), 'page_object_governance_logs', ['project_code'], unique=False)
    operations.create_table('page_object_recorder_sessions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('page_name', sa.String(length=120), nullable=False),
    sa.Column('url', sa.String(length=512), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('process_pid', sa.Integer(), nullable=True),
    sa.Column('script_path', sa.String(length=1024), nullable=False),
    sa.Column('started_by', sa.String(length=60), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name='pk_page_object_recorder_sessions')
    )
    operations.create_index(operations.f('ix_page_object_recorder_sessions_client'), 'page_object_recorder_sessions', ['client'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_heartbeat_at'), 'page_object_recorder_sessions', ['heartbeat_at'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_page_code'), 'page_object_recorder_sessions', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_process_pid'), 'page_object_recorder_sessions', ['process_pid'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_project_code'), 'page_object_recorder_sessions', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_session_id'), 'page_object_recorder_sessions', ['session_id'], unique=True)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_started_at'), 'page_object_recorder_sessions', ['started_at'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_status'), 'page_object_recorder_sessions', ['status'], unique=False)
    operations.create_index(operations.f('ix_page_object_recorder_sessions_stopped_at'), 'page_object_recorder_sessions', ['stopped_at'], unique=False)
    operations.create_table('page_objects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('page_name', sa.String(length=120), nullable=False),
    sa.Column('page_url', sa.String(length=256), nullable=False),
    sa.Column('precondition_state', sa.Text(), nullable=False),
    sa.Column('route_pattern', sa.String(length=256), nullable=False),
    sa.Column('anchor_config_json', sa.JSON(), nullable=False),
    sa.Column('governance_status', sa.String(length=20), nullable=False),
    sa.Column('testability_score', sa.Integer(), nullable=False),
    sa.Column('key_element_count', sa.Integer(), nullable=False),
    sa.Column('approved_element_count', sa.Integer(), nullable=False),
    sa.Column('candidate_pending_count', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('element_count', sa.Integer(), nullable=False),
    sa.Column('health_status', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_page_objects'),
    sa.UniqueConstraint('project_code', 'client', 'page_code', name='uq_page_objects_identity')
    )
    operations.create_index(operations.f('ix_page_objects_client'), 'page_objects', ['client'], unique=False)
    operations.create_index(operations.f('ix_page_objects_created_at'), 'page_objects', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_objects_governance_status'), 'page_objects', ['governance_status'], unique=False)
    operations.create_index(operations.f('ix_page_objects_health_status'), 'page_objects', ['health_status'], unique=False)
    operations.create_index(operations.f('ix_page_objects_module_id'), 'page_objects', ['module_id'], unique=False)
    operations.create_index(operations.f('ix_page_objects_page_code'), 'page_objects', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_page_objects_project_code'), 'page_objects', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_page_objects_status'), 'page_objects', ['status'], unique=False)
    operations.create_index(operations.f('ix_page_objects_updated_at'), 'page_objects', ['updated_at'], unique=False)
    operations.create_table('prompt_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('scene_type', sa.String(length=40), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('user_prompt_template', sa.Text(), nullable=False),
    sa.Column('variables', sa.JSON(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_enabled', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=True),
    sa.Column('updated_by', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_prompt_templates')
    )
    operations.create_index(operations.f('ix_prompt_templates_code'), 'prompt_templates', ['code'], unique=True)
    operations.create_index(operations.f('ix_prompt_templates_scene_type'), 'prompt_templates', ['scene_type'], unique=False)
    operations.create_table('quality_eval_datasets',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('task_type', sa.String(length=50), nullable=False, comment='test_case_generation | script_generation | assertion_generation | data_generation'),
    sa.Column('eval_dimensions', sa.JSON(), nullable=False),
    sa.Column('item_count', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_quality_eval_datasets')
    )
    operations.create_index(operations.f('ix_quality_eval_datasets_dataset_id'), 'quality_eval_datasets', ['dataset_id'], unique=True)
    operations.create_index(operations.f('ix_quality_eval_datasets_project_code'), 'quality_eval_datasets', ['project_code'], unique=False)
    operations.create_table('requirement_documents',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=64), nullable=False),
    sa.Column('filename', sa.String(length=512), nullable=False),
    sa.Column('source_type', sa.String(length=20), nullable=False),
    sa.Column('object_key', sa.String(length=1024), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('parse_status', sa.String(length=20), nullable=False),
    sa.Column('parse_error', sa.Text(), nullable=True),
    sa.Column('parsed_blocks', sa.JSON(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_requirement_documents')
    )
    operations.create_index(operations.f('ix_requirement_documents_created_at'), 'requirement_documents', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_requirement_documents_parse_status'), 'requirement_documents', ['parse_status'], unique=False)
    operations.create_index(operations.f('ix_requirement_documents_project_code'), 'requirement_documents', ['project_code'], unique=False)
    operations.create_table('requirements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('requirement_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('requirement_code', sa.String(length=120), nullable=False),
    sa.Column('external_requirement_key', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('current_version_pk', sa.Integer(), nullable=True),
    sa.Column('row_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('updated_by', sa.String(length=120), nullable=False),
    sa.CheckConstraint("status IN ('draft', 'active', 'closed', 'archived')", name='ck_requirements_status'),
    sa.CheckConstraint('row_version >= 1', name='ck_requirements_row_version_positive'),
    sa.PrimaryKeyConstraint('id', name='pk_requirements'),
    sa.UniqueConstraint('project_code', 'requirement_code', name='uq_requirements_project_code_requirement_code'),
    sa.UniqueConstraint('requirement_id', name='uq_requirements_requirement_id')
    )
    operations.create_index('ix_requirements_deleted_at', 'requirements', ['deleted_at'], unique=False)
    operations.create_index('ix_requirements_project_code', 'requirements', ['project_code'], unique=False)
    operations.create_index('ix_requirements_project_code_external_requirement_key', 'requirements', ['project_code', 'external_requirement_key'], unique=False)
    operations.create_index('ix_requirements_status', 'requirements', ['status'], unique=False)
    operations.create_table('test_assets',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('test_asset_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('asset_code', sa.String(length=120), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('conversion_status', sa.String(length=20), nullable=False),
    sa.Column('current_version_pk', sa.Integer(), nullable=True),
    sa.Column('row_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('updated_by', sa.String(length=120), nullable=False),
    sa.CheckConstraint("conversion_status IN ('not_started', 'processing', 'blocked', 'succeeded', 'stale')", name='ck_test_assets_conversion_status'),
    sa.CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name='ck_test_assets_review_status'),
    sa.CheckConstraint('row_version >= 1', name='ck_test_assets_row_version_positive'),
    sa.PrimaryKeyConstraint('id', name='pk_test_assets'),
    sa.UniqueConstraint('project_code', 'asset_code', name='uq_test_assets_project_code_asset_code'),
    sa.UniqueConstraint('test_asset_id', name='uq_test_assets_test_asset_id')
    )
    operations.create_index('ix_test_assets_conversion_status', 'test_assets', ['conversion_status'], unique=False)
    operations.create_index('ix_test_assets_deleted_at', 'test_assets', ['deleted_at'], unique=False)
    operations.create_index('ix_test_assets_project_code', 'test_assets', ['project_code'], unique=False)
    operations.create_index('ix_test_assets_review_status', 'test_assets', ['review_status'], unique=False)
    operations.create_table('test_case_tree_nodes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('product_line', sa.String(length=120), nullable=False),
    sa.Column('module', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_case_tree_nodes'),
    sa.UniqueConstraint('project_code', 'product_line', 'module', name='uq_test_case_tree_node')
    )
    operations.create_index(operations.f('ix_test_case_tree_nodes_module'), 'test_case_tree_nodes', ['module'], unique=False)
    operations.create_index(operations.f('ix_test_case_tree_nodes_product_line'), 'test_case_tree_nodes', ['product_line'], unique=False)
    operations.create_index(operations.f('ix_test_case_tree_nodes_project_code'), 'test_case_tree_nodes', ['project_code'], unique=False)
    operations.create_table('test_cases',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('client', sa.String(length=10), nullable=False),
    sa.Column('page_code', sa.String(length=20), nullable=False),
    sa.Column('page_name', sa.String(length=100), nullable=False),
    sa.Column('module_code', sa.String(length=20), nullable=False),
    sa.Column('module_name', sa.String(length=100), nullable=False),
    sa.Column('case_type', sa.String(length=10), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('product_line', sa.String(length=120), nullable=False),
    sa.Column('module', sa.String(length=120), nullable=False),
    sa.Column('chain_stage', sa.String(length=120), nullable=False),
    sa.Column('sut_service', sa.String(length=120), nullable=False),
    sa.Column('related_services', sa.JSON(), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('test_type', sa.String(length=50), nullable=False),
    sa.Column('scenario_types', sa.JSON(), nullable=False),
    sa.Column('trigger_entry', sa.String(length=40), nullable=False),
    sa.Column('fault_injection_type', sa.String(length=80), nullable=False),
    sa.Column('fault_injection_target', sa.String(length=255), nullable=False),
    sa.Column('fault_injection_params', sa.Text(), nullable=False),
    sa.Column('setup_sql', sa.Text(), nullable=False),
    sa.Column('precondition_state', sa.Text(), nullable=False),
    sa.Column('test_steps', sa.JSON(), nullable=False),
    sa.Column('test_steps_text', sa.Text(), nullable=False),
    sa.Column('concurrency_model', sa.String(length=120), nullable=False),
    sa.Column('retry_policy', sa.Text(), nullable=False),
    sa.Column('expected_result', sa.Text(), nullable=False),
    sa.Column('assert_sql', sa.Text(), nullable=False),
    sa.Column('event_assertion', sa.Text(), nullable=False),
    sa.Column('metric_assertion', sa.Text(), nullable=False),
    sa.Column('cleanup_script', sa.Text(), nullable=False),
    sa.Column('artifact_links', sa.JSON(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('markers', sa.JSON(), nullable=False),
    sa.Column('creator', sa.String(length=120), nullable=False),
    sa.Column('assignee', sa.String(length=120), nullable=False),
    sa.Column('pytest_path', sa.String(length=500), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('automation_status', sa.String(length=20), nullable=False),
    sa.Column('created_source', sa.String(length=40), nullable=False),
    sa.Column('source_ref', sa.String(length=255), nullable=False),
    sa.Column('script_code', sa.Text(), nullable=False),
    sa.Column('data_config', sa.JSON(), nullable=False),
    sa.Column('last_execution_result', sa.String(length=40), nullable=False),
    sa.Column('last_report_url', sa.Text(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_cases')
    )
    operations.create_index(operations.f('ix_test_cases_assignee'), 'test_cases', ['assignee'], unique=False)
    operations.create_index(operations.f('ix_test_cases_automation_status'), 'test_cases', ['automation_status'], unique=False)
    operations.create_index(operations.f('ix_test_cases_case_id'), 'test_cases', ['case_id'], unique=True)
    operations.create_index(operations.f('ix_test_cases_case_type'), 'test_cases', ['case_type'], unique=False)
    operations.create_index(operations.f('ix_test_cases_chain_stage'), 'test_cases', ['chain_stage'], unique=False)
    operations.create_index(operations.f('ix_test_cases_client'), 'test_cases', ['client'], unique=False)
    operations.create_index(operations.f('ix_test_cases_created_source'), 'test_cases', ['created_source'], unique=False)
    operations.create_index(operations.f('ix_test_cases_creator'), 'test_cases', ['creator'], unique=False)
    operations.create_index(operations.f('ix_test_cases_last_execution_result'), 'test_cases', ['last_execution_result'], unique=False)
    operations.create_index(operations.f('ix_test_cases_module'), 'test_cases', ['module'], unique=False)
    operations.create_index(operations.f('ix_test_cases_module_code'), 'test_cases', ['module_code'], unique=False)
    operations.create_index(operations.f('ix_test_cases_name'), 'test_cases', ['name'], unique=False)
    operations.create_index(operations.f('ix_test_cases_page_code'), 'test_cases', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_test_cases_priority'), 'test_cases', ['priority'], unique=False)
    operations.create_index(operations.f('ix_test_cases_product_line'), 'test_cases', ['product_line'], unique=False)
    operations.create_index(operations.f('ix_test_cases_project_code'), 'test_cases', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_test_cases_pytest_path'), 'test_cases', ['pytest_path'], unique=False)
    operations.create_index(operations.f('ix_test_cases_source'), 'test_cases', ['source'], unique=False)
    operations.create_index(operations.f('ix_test_cases_status'), 'test_cases', ['status'], unique=False)
    operations.create_index(operations.f('ix_test_cases_sut_service'), 'test_cases', ['sut_service'], unique=False)
    operations.create_index(operations.f('ix_test_cases_test_type'), 'test_cases', ['test_type'], unique=False)
    operations.create_table('test_data_pool_audit_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pool_name', sa.String(length=120), nullable=False),
    sa.Column('item_key', sa.String(length=160), nullable=False),
    sa.Column('operation', sa.String(length=40), nullable=False),
    sa.Column('changed_by', sa.String(length=120), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('before_value', sa.Text(), nullable=False),
    sa.Column('after_value', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_data_pool_audit_logs')
    )
    operations.create_index(operations.f('ix_test_data_pool_audit_logs_created_at'), 'test_data_pool_audit_logs', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_test_data_pool_audit_logs_item_key'), 'test_data_pool_audit_logs', ['item_key'], unique=False)
    operations.create_index(operations.f('ix_test_data_pool_audit_logs_operation'), 'test_data_pool_audit_logs', ['operation'], unique=False)
    operations.create_index(operations.f('ix_test_data_pool_audit_logs_pool_name'), 'test_data_pool_audit_logs', ['pool_name'], unique=False)
    operations.create_table('test_data_pools',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pool_name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('updated_by', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_data_pools')
    )
    operations.create_index(operations.f('ix_test_data_pools_pool_name'), 'test_data_pools', ['pool_name'], unique=True)
    operations.create_index(operations.f('ix_test_data_pools_status'), 'test_data_pools', ['status'], unique=False)
    operations.create_table('test_points',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('point_id', sa.String(length=80), nullable=False),
    sa.Column('point_name', sa.String(length=255), nullable=False),
    sa.Column('scene_type', sa.String(length=40), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('test_data_type', sa.String(length=40), nullable=False),
    sa.Column('involved_elements', sa.JSON(), nullable=False),
    sa.Column('expect_result', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('raw_payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_points'),
    sa.UniqueConstraint('project_code', 'page_code', 'point_id', name='uq_test_points_identity')
    )
    operations.create_index(operations.f('ix_test_points_created_at'), 'test_points', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_test_points_page_code'), 'test_points', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_test_points_point_id'), 'test_points', ['point_id'], unique=False)
    operations.create_index(operations.f('ix_test_points_priority'), 'test_points', ['priority'], unique=False)
    operations.create_index(operations.f('ix_test_points_project_code'), 'test_points', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_test_points_scene_type'), 'test_points', ['scene_type'], unique=False)
    operations.create_index(operations.f('ix_test_points_source'), 'test_points', ['source'], unique=False)
    operations.create_index(operations.f('ix_test_points_status'), 'test_points', ['status'], unique=False)
    operations.create_index(operations.f('ix_test_points_updated_at'), 'test_points', ['updated_at'], unique=False)
    operations.create_table('test_projects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('project_name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('source_roots_json', sa.JSON(), nullable=False),
    sa.Column('source_terms_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_test_projects')
    )
    operations.create_index(operations.f('ix_test_projects_project_code'), 'test_projects', ['project_code'], unique=True)
    operations.create_index(operations.f('ix_test_projects_project_name'), 'test_projects', ['project_name'], unique=False)
    operations.create_index(operations.f('ix_test_projects_status'), 'test_projects', ['status'], unique=False)
    operations.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=120), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=40), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_users')
    )
    operations.create_index(operations.f('ix_users_username'), 'users', ['username'], unique=True)
    operations.create_table('workbench_defect_links',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(length=120), nullable=False),
    sa.Column('defect_id', sa.String(length=120), nullable=False),
    sa.Column('linked_at', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_defect_links'),
    sa.UniqueConstraint('case_id', 'defect_id', name='uq_workbench_defect_links_case_defect')
    )
    operations.create_index(operations.f('ix_workbench_defect_links_case_id'), 'workbench_defect_links', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_defect_links_created_at'), 'workbench_defect_links', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_defect_links_defect_id'), 'workbench_defect_links', ['defect_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_defect_links_linked_at'), 'workbench_defect_links', ['linked_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_defect_links_updated_at'), 'workbench_defect_links', ['updated_at'], unique=False)
    operations.create_table('workbench_execution_gate_decisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project', sa.String(length=120), nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('page', sa.String(length=120), nullable=False),
    sa.Column('decision', sa.String(length=60), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_execution_gate_decisions'),
    sa.UniqueConstraint('project', 'run_id', 'page', name='uq_workbench_execution_gate_decisions_identity')
    )
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_created_at'), 'workbench_execution_gate_decisions', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_decision'), 'workbench_execution_gate_decisions', ['decision'], unique=False)
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_page'), 'workbench_execution_gate_decisions', ['page'], unique=False)
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_project'), 'workbench_execution_gate_decisions', ['project'], unique=False)
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_run_id'), 'workbench_execution_gate_decisions', ['run_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_execution_gate_decisions_updated_at'), 'workbench_execution_gate_decisions', ['updated_at'], unique=False)
    operations.create_table('workbench_failure_source_calibrations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('sample_id', sa.String(length=120), nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('case_id', sa.String(length=120), nullable=False),
    sa.Column('page', sa.String(length=120), nullable=False),
    sa.Column('human_decision', sa.String(length=80), nullable=False),
    sa.Column('predicted_failure_source', sa.String(length=120), nullable=False),
    sa.Column('confirmed_failure_source', sa.String(length=120), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_failure_source_calibrations'),
    sa.UniqueConstraint('sample_id', name='uq_workbench_failure_source_calibrations_sample_id')
    )
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_case_id'), 'workbench_failure_source_calibrations', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_confirmed_failure_source'), 'workbench_failure_source_calibrations', ['confirmed_failure_source'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_created_at'), 'workbench_failure_source_calibrations', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_human_decision'), 'workbench_failure_source_calibrations', ['human_decision'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_page'), 'workbench_failure_source_calibrations', ['page'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_predicted_failure_source'), 'workbench_failure_source_calibrations', ['predicted_failure_source'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_run_id'), 'workbench_failure_source_calibrations', ['run_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_sample_id'), 'workbench_failure_source_calibrations', ['sample_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_failure_source_calibrations_updated_at'), 'workbench_failure_source_calibrations', ['updated_at'], unique=False)
    operations.create_table('workbench_history_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('action', sa.String(length=120), nullable=False),
    sa.Column('page', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=60), nullable=False),
    sa.Column('actor_display', sa.String(length=120), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('detail_summary', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_history_events')
    )
    operations.create_index(operations.f('ix_workbench_history_events_action'), 'workbench_history_events', ['action'], unique=False)
    operations.create_index(operations.f('ix_workbench_history_events_actor_display'), 'workbench_history_events', ['actor_display'], unique=False)
    operations.create_index(operations.f('ix_workbench_history_events_created_at'), 'workbench_history_events', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_history_events_page'), 'workbench_history_events', ['page'], unique=False)
    operations.create_index(operations.f('ix_workbench_history_events_run_id'), 'workbench_history_events', ['run_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_history_events_status'), 'workbench_history_events', ['status'], unique=False)
    operations.create_table('workbench_review_decisions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('project', sa.String(length=120), nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('page', sa.String(length=120), nullable=False),
    sa.Column('review_type', sa.String(length=60), nullable=False),
    sa.Column('status', sa.String(length=60), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_review_decisions'),
    sa.UniqueConstraint('project', 'run_id', 'page', 'review_type', name='uq_workbench_review_decisions_identity')
    )
    operations.create_index(operations.f('ix_workbench_review_decisions_created_at'), 'workbench_review_decisions', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_page'), 'workbench_review_decisions', ['page'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_project'), 'workbench_review_decisions', ['project'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_review_type'), 'workbench_review_decisions', ['review_type'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_run_id'), 'workbench_review_decisions', ['run_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_status'), 'workbench_review_decisions', ['status'], unique=False)
    operations.create_index(operations.f('ix_workbench_review_decisions_updated_at'), 'workbench_review_decisions', ['updated_at'], unique=False)
    operations.create_table('workbench_runtime_runs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('project', sa.String(length=120), nullable=False),
    sa.Column('page', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=60), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name='pk_workbench_runtime_runs'),
    sa.UniqueConstraint('run_id', name='uq_workbench_runtime_runs_run_id')
    )
    operations.create_index(operations.f('ix_workbench_runtime_runs_created_at'), 'workbench_runtime_runs', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_workbench_runtime_runs_page'), 'workbench_runtime_runs', ['page'], unique=False)
    operations.create_index(operations.f('ix_workbench_runtime_runs_project'), 'workbench_runtime_runs', ['project'], unique=False)
    operations.create_index(operations.f('ix_workbench_runtime_runs_run_id'), 'workbench_runtime_runs', ['run_id'], unique=False)
    operations.create_index(operations.f('ix_workbench_runtime_runs_status'), 'workbench_runtime_runs', ['status'], unique=False)
    operations.create_index(operations.f('ix_workbench_runtime_runs_updated_at'), 'workbench_runtime_runs', ['updated_at'], unique=False)
    operations.create_table('assertion_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('behavior_id', sa.Integer(), nullable=False),
    sa.Column('capability', sa.String(length=80), nullable=False),
    sa.Column('execution_layer', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target', sa.String(length=255), nullable=False),
    sa.Column('operator', sa.String(length=40), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('variable_schema', sa.JSON(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['behavior_id'], ['behavior_registry.id'], name='fk_assertion_templates_behavior_id_behavior_registry', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_assertion_templates')
    )
    operations.create_index(operations.f('ix_assertion_templates_behavior_id'), 'assertion_templates', ['behavior_id'], unique=False)
    operations.create_table('page_elements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('page_object_id', sa.Integer(), nullable=False),
    sa.Column('element_code', sa.String(length=80), nullable=False),
    sa.Column('element_name', sa.String(length=120), nullable=False),
    sa.Column('locator_type', sa.String(length=30), nullable=False),
    sa.Column('locator_value', sa.Text(), nullable=False),
    sa.Column('backup_locator', sa.String(length=512), nullable=False),
    sa.Column('business_type', sa.String(length=40), nullable=False),
    sa.Column('business_domain', sa.String(length=40), nullable=False),
    sa.Column('aliases_json', sa.JSON(), nullable=False),
    sa.Column('semantic_tags_json', sa.JSON(), nullable=False),
    sa.Column('locator_source', sa.String(length=20), nullable=False),
    sa.Column('match_strategy', sa.String(length=20), nullable=False),
    sa.Column('stability_level', sa.String(length=20), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('origin_candidate_key', sa.String(length=120), nullable=False),
    sa.Column('route_scope', sa.String(length=256), nullable=False),
    sa.Column('anchor_required', sa.Boolean(), nullable=False),
    sa.Column('is_key_element', sa.Boolean(), nullable=False),
    sa.Column('testid_value', sa.String(length=120), nullable=False),
    sa.Column('qa_value', sa.String(length=120), nullable=False),
    sa.Column('governance_note', sa.Text(), nullable=False),
    sa.Column('health_status', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=60), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('owner', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_object_id'], ['page_objects.id'], name='fk_page_elements_page_object_id_page_objects', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_page_elements'),
    sa.UniqueConstraint('page_object_id', 'element_code', name='uq_page_elements_identity')
    )
    operations.create_index(operations.f('ix_page_elements_created_at'), 'page_elements', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_elements_element_code'), 'page_elements', ['element_code'], unique=False)
    operations.create_index(operations.f('ix_page_elements_health_status'), 'page_elements', ['health_status'], unique=False)
    operations.create_index('ix_page_elements_page_object_business_type', 'page_elements', ['page_object_id', 'business_type'], unique=False)
    operations.create_index(operations.f('ix_page_elements_page_object_id'), 'page_elements', ['page_object_id'], unique=False)
    operations.create_index('ix_page_elements_page_object_locator_source', 'page_elements', ['page_object_id', 'locator_source'], unique=False)
    operations.create_index('ix_page_elements_page_object_review_status', 'page_elements', ['page_object_id', 'review_status'], unique=False)
    operations.create_index('ix_page_elements_page_object_stability_level', 'page_elements', ['page_object_id', 'stability_level'], unique=False)
    operations.create_index('ix_page_elements_page_object_testid_value', 'page_elements', ['page_object_id', 'testid_value'], unique=False)
    operations.create_index(operations.f('ix_page_elements_status'), 'page_elements', ['status'], unique=False)
    operations.create_index(operations.f('ix_page_elements_updated_at'), 'page_elements', ['updated_at'], unique=False)
    operations.create_index(operations.f('ix_page_elements_version'), 'page_elements', ['version'], unique=False)
    operations.create_table('quality_eval_items',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('requirement_text', sa.Text(), nullable=False),
    sa.Column('context_json', sa.JSON(), nullable=False),
    sa.Column('expected_coverage', sa.JSON(), nullable=False),
    sa.Column('expected_assertions', sa.JSON(), nullable=False),
    sa.Column('expected_page_codes', sa.JSON(), nullable=False),
    sa.Column('perturbed_requirement', sa.Text(), nullable=False),
    sa.Column('known_issues', sa.JSON(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('meta_data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['quality_eval_datasets.dataset_id'], name='fk_quality_eval_items_dataset_id_quality_eval_datasets'),
    sa.PrimaryKeyConstraint('id', name='pk_quality_eval_items')
    )
    operations.create_index(operations.f('ix_quality_eval_items_dataset_id'), 'quality_eval_items', ['dataset_id'], unique=False)
    operations.create_index(operations.f('ix_quality_eval_items_item_id'), 'quality_eval_items', ['item_id'], unique=True)
    operations.create_table('quality_eval_runs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('agent_version', sa.String(length=50), nullable=False),
    sa.Column('llm_model', sa.String(length=100), nullable=False),
    sa.Column('prompt_version', sa.String(length=50), nullable=False),
    sa.Column('gate_rule_version', sa.String(length=50), nullable=False),
    sa.Column('task_type', sa.String(length=50), nullable=False),
    sa.Column('eval_dimensions', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('total_items', sa.Integer(), nullable=False),
    sa.Column('completed_items', sa.Integer(), nullable=False),
    sa.Column('overall_score', sa.Float(), nullable=False),
    sa.Column('coverage_score', sa.Float(), nullable=False),
    sa.Column('assertion_score', sa.Float(), nullable=False),
    sa.Column('executability_score', sa.Float(), nullable=False),
    sa.Column('consistency_score', sa.Float(), nullable=False),
    sa.Column('robustness_score', sa.Float(), nullable=False),
    sa.Column('hallucination_risk', sa.Float(), nullable=False),
    sa.Column('summary_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['quality_eval_datasets.dataset_id'], name='fk_quality_eval_runs_dataset_id_quality_eval_datasets'),
    sa.PrimaryKeyConstraint('id', name='pk_quality_eval_runs')
    )
    operations.create_index(operations.f('ix_quality_eval_runs_dataset_id'), 'quality_eval_runs', ['dataset_id'], unique=False)
    operations.create_index(operations.f('ix_quality_eval_runs_project_code'), 'quality_eval_runs', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_quality_eval_runs_run_id'), 'quality_eval_runs', ['run_id'], unique=True)
    operations.create_index(operations.f('ix_quality_eval_runs_status'), 'quality_eval_runs', ['status'], unique=False)
    operations.create_table('requirement_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('requirement_version_id', sa.String(length=64), nullable=False),
    sa.Column('requirement_pk', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_checksum', sa.String(length=64), nullable=False),
    sa.Column('version_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.CheckConstraint("version_status IN ('draft', 'effective', 'superseded', 'removed')", name='ck_requirement_versions_version_status'),
    sa.CheckConstraint('version_no >= 1', name='ck_requirement_versions_version_no_positive'),
    sa.ForeignKeyConstraint(['requirement_pk'], ['requirements.id'], name='fk_requirement_versions_requirement_pk_requirements', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name='pk_requirement_versions'),
    sa.UniqueConstraint('requirement_pk', 'version_no', name='uq_requirement_versions_requirement_pk_version_no'),
    sa.UniqueConstraint('requirement_version_id', name='uq_requirement_versions_requirement_version_id')
    )
    operations.create_index('ix_requirement_versions_content_checksum', 'requirement_versions', ['content_checksum'], unique=False)
    operations.create_index('ix_requirement_versions_requirement_pk', 'requirement_versions', ['requirement_pk'], unique=False)
    operations.create_index('ix_requirement_versions_version_status', 'requirement_versions', ['version_status'], unique=False)
    operations.create_table('test_asset_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('test_asset_version_id', sa.String(length=64), nullable=False),
    sa.Column('test_asset_pk', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('precondition', sa.Text(), nullable=True),
    sa.Column('natural_steps', sa.JSON(), nullable=False),
    sa.Column('expected_result', sa.Text(), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('content_checksum', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.CheckConstraint('version_no >= 1', name='ck_test_asset_versions_version_no_positive'),
    sa.ForeignKeyConstraint(['test_asset_pk'], ['test_assets.id'], name='fk_test_asset_versions_test_asset_pk_test_assets', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name='pk_test_asset_versions'),
    sa.UniqueConstraint('test_asset_pk', 'version_no', name='uq_test_asset_versions_test_asset_pk_version_no'),
    sa.UniqueConstraint('test_asset_version_id', name='uq_test_asset_versions_test_asset_version_id')
    )
    operations.create_index('ix_test_asset_versions_content_checksum', 'test_asset_versions', ['content_checksum'], unique=False)
    operations.create_index('ix_test_asset_versions_test_asset_pk', 'test_asset_versions', ['test_asset_pk'], unique=False)
    operations.create_table('test_case_defects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.Integer(), nullable=False),
    sa.Column('defect_key', sa.String(length=120), nullable=False),
    sa.Column('defect_url', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['test_cases.id'], name='fk_test_case_defects_case_id_test_cases', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_test_case_defects')
    )
    operations.create_index(operations.f('ix_test_case_defects_case_id'), 'test_case_defects', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_test_case_defects_defect_key'), 'test_case_defects', ['defect_key'], unique=False)
    operations.create_table('test_case_executions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('report_url', sa.Text(), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['test_cases.id'], name='fk_test_case_executions_case_id_test_cases', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_test_case_executions')
    )
    operations.create_index(operations.f('ix_test_case_executions_case_id'), 'test_case_executions', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_test_case_executions_executed_at'), 'test_case_executions', ['executed_at'], unique=False)
    operations.create_index(operations.f('ix_test_case_executions_status'), 'test_case_executions', ['status'], unique=False)
    operations.create_table('test_case_steps',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.Integer(), nullable=False),
    sa.Column('case_business_id', sa.String(length=64), nullable=False),
    sa.Column('project_code', sa.String(length=20), nullable=False),
    sa.Column('page_code', sa.String(length=40), nullable=False),
    sa.Column('step_index', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target', sa.String(length=255), nullable=False),
    sa.Column('locator_type', sa.String(length=40), nullable=False),
    sa.Column('locator_value', sa.Text(), nullable=False),
    sa.Column('step_data', sa.Text(), nullable=False),
    sa.Column('expected_result', sa.Text(), nullable=False),
    sa.Column('raw_payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['test_cases.id'], name='fk_test_case_steps_case_id_test_cases', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_test_case_steps'),
    sa.UniqueConstraint('case_id', 'step_index', name='uq_test_case_steps_identity')
    )
    operations.create_index(operations.f('ix_test_case_steps_case_business_id'), 'test_case_steps', ['case_business_id'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_case_id'), 'test_case_steps', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_created_at'), 'test_case_steps', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_page_code'), 'test_case_steps', ['page_code'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_project_code'), 'test_case_steps', ['project_code'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_step_index'), 'test_case_steps', ['step_index'], unique=False)
    operations.create_index(operations.f('ix_test_case_steps_updated_at'), 'test_case_steps', ['updated_at'], unique=False)
    operations.create_table('test_case_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('script_code', sa.Text(), nullable=False),
    sa.Column('changed_by', sa.String(length=120), nullable=False),
    sa.Column('change_summary', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['test_cases.id'], name='fk_test_case_versions_case_id_test_cases', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_test_case_versions')
    )
    operations.create_index(operations.f('ix_test_case_versions_case_id'), 'test_case_versions', ['case_id'], unique=False)
    operations.create_index(operations.f('ix_test_case_versions_created_at'), 'test_case_versions', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_test_case_versions_version_no'), 'test_case_versions', ['version_no'], unique=False)
    operations.create_table('test_data_pool_items',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pool_id', sa.Integer(), nullable=False),
    sa.Column('item_key', sa.String(length=160), nullable=False),
    sa.Column('item_value', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.Column('updated_by', sa.String(length=120), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['pool_id'], ['test_data_pools.id'], name='fk_test_data_pool_items_pool_id_test_data_pools', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_test_data_pool_items'),
    sa.UniqueConstraint('pool_id', 'item_key', name='uq_test_data_pool_item_key')
    )
    operations.create_index(operations.f('ix_test_data_pool_items_item_key'), 'test_data_pool_items', ['item_key'], unique=False)
    operations.create_index(operations.f('ix_test_data_pool_items_pool_id'), 'test_data_pool_items', ['pool_id'], unique=False)
    operations.create_index(operations.f('ix_test_data_pool_items_status'), 'test_data_pool_items', ['status'], unique=False)
    operations.create_table('page_element_health_checks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('page_element_id', sa.Integer(), nullable=False),
    sa.Column('check_status', sa.String(length=20), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('checked_by', sa.String(length=60), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_element_id'], ['page_elements.id'], name='fk_page_element_health_checks_page_element_id_page_elements', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_page_element_health_checks')
    )
    operations.create_index(operations.f('ix_page_element_health_checks_check_status'), 'page_element_health_checks', ['check_status'], unique=False)
    operations.create_index(operations.f('ix_page_element_health_checks_checked_at'), 'page_element_health_checks', ['checked_at'], unique=False)
    operations.create_index(operations.f('ix_page_element_health_checks_page_element_id'), 'page_element_health_checks', ['page_element_id'], unique=False)
    operations.create_table('page_element_locators',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('page_element_id', sa.Integer(), nullable=False),
    sa.Column('locator_type', sa.String(length=30), nullable=False),
    sa.Column('locator_value', sa.String(length=512), nullable=False),
    sa.Column('role', sa.String(length=60), nullable=False),
    sa.Column('locator_source', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('health_status', sa.String(length=20), nullable=False),
    sa.Column('verification_status', sa.String(length=20), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_element_id'], ['page_elements.id'], name='fk_page_element_locators_page_element_id_page_elements', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_page_element_locators'),
    sa.UniqueConstraint('page_element_id', 'locator_type', 'locator_value', 'role', name='uq_page_element_locators_identity')
    )
    operations.create_index(operations.f('ix_page_element_locators_created_at'), 'page_element_locators', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_element_locators_health_status'), 'page_element_locators', ['health_status'], unique=False)
    operations.create_index(operations.f('ix_page_element_locators_last_verified_at'), 'page_element_locators', ['last_verified_at'], unique=False)
    operations.create_index(operations.f('ix_page_element_locators_page_element_id'), 'page_element_locators', ['page_element_id'], unique=False)
    operations.create_index(operations.f('ix_page_element_locators_updated_at'), 'page_element_locators', ['updated_at'], unique=False)
    operations.create_index(operations.f('ix_page_element_locators_verification_status'), 'page_element_locators', ['verification_status'], unique=False)
    operations.create_table('page_element_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('page_element_id', sa.Integer(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('locator_type', sa.String(length=30), nullable=False),
    sa.Column('locator_value', sa.Text(), nullable=False),
    sa.Column('role', sa.String(length=60), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('changed_by', sa.String(length=60), nullable=False),
    sa.Column('change_summary', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_element_id'], ['page_elements.id'], name='fk_page_element_versions_page_element_id_page_elements', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_page_element_versions'),
    sa.UniqueConstraint('page_element_id', 'version_no', name='uq_page_element_versions_identity')
    )
    operations.create_index(operations.f('ix_page_element_versions_created_at'), 'page_element_versions', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_element_versions_page_element_id'), 'page_element_versions', ['page_element_id'], unique=False)
    operations.create_index(operations.f('ix_page_element_versions_version_no'), 'page_element_versions', ['version_no'], unique=False)
    operations.create_table('page_object_refs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('page_element_id', sa.Integer(), nullable=False),
    sa.Column('reference_type', sa.String(length=30), nullable=False),
    sa.Column('reference_key', sa.String(length=120), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('created_by', sa.String(length=60), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['page_element_id'], ['page_elements.id'], name='fk_page_object_refs_page_element_id_page_elements', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_page_object_refs'),
    sa.UniqueConstraint('page_element_id', 'reference_type', 'reference_key', name='uq_page_object_refs_identity')
    )
    operations.create_index(operations.f('ix_page_object_refs_created_at'), 'page_object_refs', ['created_at'], unique=False)
    operations.create_index(operations.f('ix_page_object_refs_page_element_id'), 'page_object_refs', ['page_element_id'], unique=False)
    operations.create_index(operations.f('ix_page_object_refs_reference_key'), 'page_object_refs', ['reference_key'], unique=False)
    operations.create_index(operations.f('ix_page_object_refs_reference_type'), 'page_object_refs', ['reference_type'], unique=False)
    operations.create_table('quality_eval_results',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('result_id', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('generated_case_json', sa.JSON(), nullable=False),
    sa.Column('generated_script', sa.Text(), nullable=False),
    sa.Column('coverage_score', sa.Float(), nullable=False),
    sa.Column('coverage_detail', sa.JSON(), nullable=False),
    sa.Column('assertion_score', sa.Float(), nullable=False),
    sa.Column('assertion_detail', sa.JSON(), nullable=False),
    sa.Column('executability_score', sa.Float(), nullable=False),
    sa.Column('executability_detail', sa.JSON(), nullable=False),
    sa.Column('consistency_runs', sa.JSON(), nullable=False),
    sa.Column('consistency_score', sa.Float(), nullable=False),
    sa.Column('perturbed_output', sa.JSON(), nullable=False),
    sa.Column('robustness_score', sa.Float(), nullable=False),
    sa.Column('hallucination_flags', sa.JSON(), nullable=False),
    sa.Column('hallucination_score', sa.Float(), nullable=False),
    sa.Column('weighted_score', sa.Float(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['quality_eval_items.item_id'], name='fk_quality_eval_results_item_id_quality_eval_items'),
    sa.ForeignKeyConstraint(['run_id'], ['quality_eval_runs.run_id'], name='fk_quality_eval_results_run_id_quality_eval_runs'),
    sa.PrimaryKeyConstraint('id', name='pk_quality_eval_results')
    )
    operations.create_index(operations.f('ix_quality_eval_results_item_id'), 'quality_eval_results', ['item_id'], unique=False)
    operations.create_index(operations.f('ix_quality_eval_results_result_id'), 'quality_eval_results', ['result_id'], unique=True)
    operations.create_index(operations.f('ix_quality_eval_results_run_id'), 'quality_eval_results', ['run_id'], unique=False)
    operations.create_table('test_asset_sources',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('test_asset_source_id', sa.String(length=64), nullable=False),
    sa.Column('test_asset_pk', sa.Integer(), nullable=False),
    sa.Column('requirement_pk', sa.Integer(), nullable=False),
    sa.Column('requirement_version_pk', sa.Integer(), nullable=False),
    sa.Column('source_identity_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.String(length=120), nullable=False),
    sa.ForeignKeyConstraint(['requirement_pk'], ['requirements.id'], name='fk_test_asset_sources_requirement_pk_requirements', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requirement_version_pk'], ['requirement_versions.id'], name='fk_test_asset_sources_requirement_version_pk_requirement_versions', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['test_asset_pk'], ['test_assets.id'], name='fk_test_asset_sources_test_asset_pk_test_assets', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name='pk_test_asset_sources'),
    sa.UniqueConstraint('test_asset_pk', 'source_identity_hash', name='uq_test_asset_sources_test_asset_pk_source_identity_hash'),
    sa.UniqueConstraint('test_asset_source_id', name='uq_test_asset_sources_test_asset_source_id')
    )
    operations.create_index('ix_test_asset_sources_requirement_pk', 'test_asset_sources', ['requirement_pk'], unique=False)
    operations.create_index('ix_test_asset_sources_requirement_version_pk', 'test_asset_sources', ['requirement_version_pk'], unique=False)
    operations.create_index('ix_test_asset_sources_source_identity_hash', 'test_asset_sources', ['source_identity_hash'], unique=False)
    # ### end Alembic commands ###
