"""Explicit SQLite lifecycle with approved single-step schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import PersistenceError, UnsupportedSchemaVersionError

SQLITE_SCHEMA_VERSION = 20
_SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)

_V1_TABLE_STATEMENTS = (
    """CREATE TABLE schema_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL
)""",
    """CREATE TABLE processing_units (
    identity TEXT PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (length(trim(purpose)) > 0),
    independently_retryable INTEGER NOT NULL
        CHECK (independently_retryable IN (0, 1))
)""",
    """CREATE TABLE processing_unit_dependencies (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    dependency_id TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
    """CREATE TABLE processing_unit_capabilities (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    capability TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
    """CREATE TABLE processing_unit_result_kinds (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    result_kind TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
)

_V2_ADDITION_STATEMENTS = (
    """CREATE TABLE processing_runs (
    identity TEXT PRIMARY KEY,
    intent_purpose TEXT NOT NULL CHECK (length(trim(intent_purpose)) > 0),
    intent_retry_of TEXT,
    intent_reprocessing_of TEXT,
    working_context TEXT NOT NULL,
    configuration TEXT,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    reprocessing_of TEXT,
    CHECK (intent_retry_of IS NULL OR intent_reprocessing_of IS NULL)
)""",
    """CREATE TABLE processing_run_inputs (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_reference TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_upstream_results (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_units (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    processing_unit_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_unit_executions (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    unit_execution_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_results (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_failures (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    failure_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
)

_V3_ADDITION_STATEMENTS = (
    """CREATE TABLE unit_executions (
    identity TEXT PRIMARY KEY,
    processing_run_id TEXT NOT NULL,
    processing_unit_id TEXT NOT NULL,
    configuration TEXT,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    outcome_kind TEXT CHECK (
        outcome_kind IS NULL OR outcome_kind IN (
            'domain_result_generated', 'partial_result', 'no_result',
            'validation_failure', 'recoverable_failure',
            'non_recoverable_condition'
        )
    ),
    outcome_detail TEXT,
    retry_of TEXT,
    cancelled_from TEXT,
    recovery_of TEXT,
    CHECK (outcome_detail IS NULL OR outcome_kind IS NOT NULL)
)""",
    """CREATE TABLE unit_execution_inputs (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_reference TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_capabilities (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    capability TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_plugins (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    plugin_reference TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_results (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_failures (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    failure_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_diagnostics (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    diagnostic_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
)

_V4_ADDITION_STATEMENTS = (
    """CREATE TABLE domain_result_references (
    identity TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    source_media_id TEXT,
    source_timeline_id TEXT,
    revision_of TEXT,
    applicability TEXT
)""",
    """CREATE TABLE domain_result_upstream_results (
    domain_result_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    upstream_domain_result_id TEXT NOT NULL,
    PRIMARY KEY (domain_result_id, ordinal),
    FOREIGN KEY (domain_result_id) REFERENCES domain_result_references(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE failures (
    identity TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK (
        category IN (
            'preparation', 'capability', 'provider_or_plugin', 'processing',
            'validation', 'persistence', 'review_blocking', 'export',
            'external_consumer'
        )
    ),
    processing_run_id TEXT,
    unit_execution_id TEXT,
    retryable INTEGER NOT NULL CHECK (retryable IN (0, 1)),
    reprocessing_required INTEGER NOT NULL
        CHECK (reprocessing_required IN (0, 1)),
    human_action_required INTEGER NOT NULL
        CHECK (human_action_required IN (0, 1)),
    CHECK (processing_run_id IS NOT NULL OR unit_execution_id IS NOT NULL)
)""",
    """CREATE TABLE failure_affected_inputs (
    failure_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_reference TEXT NOT NULL,
    PRIMARY KEY (failure_id, ordinal),
    FOREIGN KEY (failure_id) REFERENCES failures(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE failure_affected_results (
    failure_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (failure_id, ordinal),
    FOREIGN KEY (failure_id) REFERENCES failures(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE failure_diagnostics (
    failure_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    diagnostic_id TEXT NOT NULL,
    PRIMARY KEY (failure_id, ordinal),
    FOREIGN KEY (failure_id) REFERENCES failures(identity)
        ON DELETE CASCADE
)""",
)

_V5_ADDITION_STATEMENTS = (
    """CREATE TABLE provider_transcript_results (
    identity TEXT PRIMARY KEY,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    provider_reference TEXT NOT NULL
        CHECK (length(trim(provider_reference)) > 0),
    original_content TEXT NOT NULL,
    plugin_reference TEXT,
    uncertainty REAL,
    normalized INTEGER NOT NULL CHECK (normalized = 0)
)""",
    """CREATE TABLE provider_transcript_result_diagnostics (
    provider_transcript_result_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    diagnostic_id TEXT NOT NULL,
    PRIMARY KEY (provider_transcript_result_id, ordinal),
    FOREIGN KEY (provider_transcript_result_id)
        REFERENCES provider_transcript_results(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE transcript_segments (
    identity TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    source_timeline_id TEXT,
    text TEXT NOT NULL,
    source_order INTEGER NOT NULL CHECK (source_order >= 0),
    start REAL,
    end REAL,
    speaker_label TEXT,
    confidence REAL,
    uncertainty REAL,
    replaces_segment_id TEXT,
    CHECK ((start IS NULL AND end IS NULL) OR
           (start IS NOT NULL AND end IS NOT NULL AND
            source_timeline_id IS NOT NULL AND start >= 0 AND end >= start))
)""",
    """CREATE TABLE raw_transcripts (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    provider_transcript_result_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    validation_id TEXT
)""",
    """CREATE TABLE raw_transcript_segments (
    raw_transcript_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    transcript_segment_id TEXT NOT NULL,
    PRIMARY KEY (raw_transcript_id, ordinal),
    FOREIGN KEY (raw_transcript_id) REFERENCES raw_transcripts(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE correction_candidates (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    transcript_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    proposed_text TEXT NOT NULL,
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    target_revision_id TEXT,
    confidence REAL,
    uncertainty REAL,
    capability TEXT,
    plugin_reference TEXT,
    provider_reference TEXT CHECK (
        provider_reference IS NULL OR length(trim(provider_reference)) > 0
    )
)""",
    """CREATE TABLE correction_candidate_evidence (
    correction_candidate_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    evidence TEXT NOT NULL,
    PRIMARY KEY (correction_candidate_id, ordinal),
    FOREIGN KEY (correction_candidate_id) REFERENCES correction_candidates(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE corrected_transcript_revisions (
    identity TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    domain_result_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    parent_raw_transcript_id TEXT,
    parent_revision_id TEXT,
    decision_reference TEXT,
    validation_id TEXT,
    applicability TEXT NOT NULL CHECK (
        applicability IN ('undetermined', 'stale', 'superseded', 'historical')
    ),
    CHECK ((parent_raw_transcript_id IS NOT NULL AND parent_revision_id IS NULL) OR
           (parent_raw_transcript_id IS NULL AND parent_revision_id IS NOT NULL))
)""",
    """CREATE TABLE corrected_transcript_revision_segments (
    transcript_revision_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    transcript_segment_id TEXT NOT NULL,
    PRIMARY KEY (transcript_revision_id, ordinal),
    FOREIGN KEY (transcript_revision_id)
        REFERENCES corrected_transcript_revisions(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE corrected_transcript_revision_candidates (
    transcript_revision_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    correction_candidate_id TEXT NOT NULL,
    PRIMARY KEY (transcript_revision_id, ordinal),
    FOREIGN KEY (transcript_revision_id)
        REFERENCES corrected_transcript_revisions(identity) ON DELETE CASCADE
)""",
)

_V6_ADDITION_STATEMENTS = (
    """CREATE TABLE review_candidate_references (
    identity TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    source_domain TEXT NOT NULL CHECK (length(trim(source_domain)) > 0),
    domain_result_id TEXT,
    source_media_id TEXT,
    source_timeline_id TEXT,
    processing_run_id TEXT,
    unit_execution_id TEXT,
    revision_reference TEXT,
    applicability TEXT NOT NULL,
    CHECK ((processing_run_id IS NULL AND unit_execution_id IS NULL) OR
           (processing_run_id IS NOT NULL AND unit_execution_id IS NOT NULL))
)""",
    """CREATE TABLE review_contexts (
    identity TEXT PRIMARY KEY,
    source_media_id TEXT,
    source_timeline_id TEXT,
    blocking_reason TEXT
)""",
    """CREATE TABLE review_context_domain_results (
    review_context_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (review_context_id, ordinal),
    FOREIGN KEY (review_context_id) REFERENCES review_contexts(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE review_context_evidence (
    review_context_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    evidence TEXT NOT NULL,
    PRIMARY KEY (review_context_id, ordinal),
    FOREIGN KEY (review_context_id) REFERENCES review_contexts(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE review_items (
    identity TEXT PRIMARY KEY,
    candidate_reference_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    applicability_at_creation TEXT NOT NULL,
    processing_run_id TEXT,
    unit_execution_id TEXT,
    CHECK ((processing_run_id IS NULL AND unit_execution_id IS NULL) OR
           (processing_run_id IS NOT NULL AND unit_execution_id IS NOT NULL))
)""",
    """CREATE TABLE transcript_review_preparations (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    item_count INTEGER NOT NULL CHECK (item_count >= 1),
    structural_valid INTEGER NOT NULL CHECK (structural_valid IN (0, 1)),
    provenance_complete INTEGER NOT NULL CHECK (provenance_complete IN (0, 1)),
    ordering_valid INTEGER NOT NULL CHECK (ordering_valid IN (0, 1))
)""",
    """CREATE TABLE transcript_review_preparation_items (
    transcript_review_preparation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    review_item_id TEXT NOT NULL,
    PRIMARY KEY (transcript_review_preparation_id, ordinal),
    FOREIGN KEY (transcript_review_preparation_id)
        REFERENCES transcript_review_preparations(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE transcript_review_preparation_candidates (
    transcript_review_preparation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    candidate_reference_id TEXT NOT NULL,
    PRIMARY KEY (transcript_review_preparation_id, ordinal),
    FOREIGN KEY (transcript_review_preparation_id)
        REFERENCES transcript_review_preparations(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE transcript_review_preparation_groups (
    transcript_review_preparation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    group_key TEXT NOT NULL CHECK (length(trim(group_key)) > 0),
    review_item_id TEXT NOT NULL,
    PRIMARY KEY (transcript_review_preparation_id, ordinal),
    FOREIGN KEY (transcript_review_preparation_id)
        REFERENCES transcript_review_preparations(identity) ON DELETE CASCADE
)""",
)

_V7_ADDITION_STATEMENTS = (
    """CREATE TABLE transcript_review_decisions (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('accept', 'reject', 'modify')),
    decided_at TEXT NOT NULL CHECK (length(trim(decided_at)) > 0),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    previous_decision_id TEXT,
    rationale TEXT,
    modified_text TEXT,
    CHECK ((kind = 'modify' AND modified_text IS NOT NULL) OR
           (kind IN ('accept', 'reject') AND modified_text IS NULL)),
    CHECK ((sequence = 0 AND previous_decision_id IS NULL) OR sequence > 0)
)""",
)

_V8_ADDITION_STATEMENTS = (
    """CREATE TABLE transcript_applicability_evaluations (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    decision_kind TEXT NOT NULL CHECK (decision_kind IN ('accept', 'reject', 'modify')),
    outcome TEXT NOT NULL CHECK (
        outcome IN ('applicable', 'not_applicable', 'superseded_by_modification')
    ),
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_evaluation_id TEXT,
    CHECK ((decision_kind = 'accept' AND outcome = 'applicable') OR
           (decision_kind = 'reject' AND outcome = 'not_applicable') OR
           (decision_kind = 'modify' AND outcome = 'superseded_by_modification')),
    CHECK ((sequence = 0 AND previous_evaluation_id IS NULL) OR sequence > 0)
)""",
)

_V10_ADDITION_STATEMENTS = (
    """CREATE TABLE transcript_readiness_evaluations (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    selection_outcome TEXT NOT NULL CHECK (selection_outcome IN ('selected', 'not_selected')),
    source_applicability_id TEXT NOT NULL,
    applicability_outcome TEXT NOT NULL CHECK (
        applicability_outcome IN ('applicable', 'not_applicable', 'superseded_by_modification')
    ),
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    validation_id TEXT NOT NULL,
    structural_valid INTEGER NOT NULL CHECK (structural_valid IN (0, 1)),
    outcome TEXT NOT NULL CHECK (outcome IN ('ready', 'not_ready')),
    reason_code TEXT NOT NULL CHECK (
        reason_code IN ('all_conditions_met', 'not_selected', 'not_applicable',
                        'superseded_by_modification', 'structural_validation_failed')
    ),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_readiness_id TEXT,
    CHECK ((outcome = 'ready' AND selection_outcome = 'selected'
            AND applicability_outcome = 'applicable' AND structural_valid = 1
            AND reason_code = 'all_conditions_met')
           OR (outcome = 'not_ready' AND reason_code <> 'all_conditions_met')),
    CHECK ((sequence = 0 AND previous_readiness_id IS NULL) OR sequence > 0)
)""",
)

_V11_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_transcript_intakes (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    readiness_outcome TEXT NOT NULL CHECK (readiness_outcome IN ('ready', 'not_ready')),
    outcome TEXT NOT NULL CHECK (outcome IN ('eligible', 'not_eligible')),
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    validation_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_intake_id TEXT,
    CHECK ((readiness_outcome = 'ready' AND outcome = 'eligible')
           OR (readiness_outcome = 'not_ready' AND outcome = 'not_eligible')),
    CHECK ((sequence = 0 AND previous_intake_id IS NULL) OR sequence > 0)
)""",
)

_V12_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_candidates (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_intake_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    validation_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_candidate_id TEXT,
    CHECK ((sequence = 0 AND previous_candidate_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_candidate_cues (
    identity TEXT PRIMARY KEY,
    subtitle_candidate_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_timeline_id TEXT,
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    display_order INTEGER NOT NULL CHECK (display_order >= 0),
    start REAL,
    end REAL,
    CHECK ((start IS NULL AND end IS NULL) OR
           (start IS NOT NULL AND end IS NOT NULL AND
            source_timeline_id IS NOT NULL AND start >= 0 AND end >= start)),
    UNIQUE (subtitle_candidate_id, ordinal),
    FOREIGN KEY (subtitle_candidate_id) REFERENCES subtitle_candidates(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE subtitle_candidate_cue_segments (
    subtitle_candidate_cue_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    transcript_segment_id TEXT NOT NULL,
    PRIMARY KEY (subtitle_candidate_cue_id, ordinal),
    FOREIGN KEY (subtitle_candidate_cue_id)
        REFERENCES subtitle_candidate_cues(identity) ON DELETE CASCADE
)""",
)

_V13_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_reading_revisions (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_intake_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    validation_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_reading_revision_id TEXT,
    CHECK ((sequence = 0 AND previous_reading_revision_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_reading_units (
    identity TEXT PRIMARY KEY,
    subtitle_reading_revision_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_timeline_id TEXT,
    display_order INTEGER NOT NULL CHECK (display_order >= 0),
    start REAL,
    end REAL,
    CHECK ((start IS NULL AND end IS NULL) OR
           (start IS NOT NULL AND end IS NOT NULL AND
            source_timeline_id IS NOT NULL AND start >= 0 AND end >= start)),
    UNIQUE (subtitle_reading_revision_id, ordinal),
    FOREIGN KEY (subtitle_reading_revision_id)
        REFERENCES subtitle_reading_revisions(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE subtitle_reading_unit_source_cues (
    subtitle_reading_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    subtitle_candidate_cue_id TEXT NOT NULL,
    PRIMARY KEY (subtitle_reading_unit_id, ordinal),
    FOREIGN KEY (subtitle_reading_unit_id)
        REFERENCES subtitle_reading_units(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE subtitle_reading_unit_lines (
    subtitle_reading_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    line TEXT NOT NULL CHECK (length(trim(line)) > 0),
    PRIMARY KEY (subtitle_reading_unit_id, ordinal),
    FOREIGN KEY (subtitle_reading_unit_id)
        REFERENCES subtitle_reading_units(identity) ON DELETE CASCADE
)""",
)

_V14_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_time_revisions (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_intake_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    validation_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_time_revision_id TEXT,
    CHECK ((sequence = 0 AND previous_time_revision_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_timed_units (
    identity TEXT PRIMARY KEY,
    subtitle_time_revision_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_reading_unit_id TEXT NOT NULL,
    timing_status TEXT NOT NULL CHECK (timing_status IN ('anchored', 'unresolved')),
    source_timeline_id TEXT,
    display_order INTEGER NOT NULL CHECK (display_order >= 0),
    start REAL,
    end REAL,
    CHECK ((timing_status = 'anchored' AND source_timeline_id IS NOT NULL
            AND start IS NOT NULL AND end IS NOT NULL AND start >= 0 AND end >= start)
        OR (timing_status = 'unresolved' AND source_timeline_id IS NULL
            AND start IS NULL AND end IS NULL)),
    UNIQUE (subtitle_time_revision_id, ordinal),
    FOREIGN KEY (subtitle_time_revision_id)
        REFERENCES subtitle_time_revisions(identity) ON DELETE CASCADE
)""",
)

_V15_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_validations (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_intake_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    source_transcript_validation_id TEXT NOT NULL,
    structural_valid INTEGER NOT NULL CHECK (structural_valid IN (0, 1)),
    provenance_complete INTEGER NOT NULL CHECK (provenance_complete IN (0, 1)),
    timeline_traceable INTEGER NOT NULL CHECK (timeline_traceable IN (0, 1)),
    ordering_consistent INTEGER NOT NULL CHECK (ordering_consistent IN (0, 1)),
    time_consistent INTEGER NOT NULL CHECK (time_consistent IN (0, 1)),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_validation_id TEXT,
    CHECK ((sequence = 0 AND previous_validation_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_validation_findings (
    identity TEXT PRIMARY KEY,
    subtitle_validation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    rule TEXT NOT NULL CHECK (length(trim(rule)) > 0),
    category TEXT NOT NULL CHECK (category IN (
        'provenance_integrity', 'timeline_traceability', 'unresolved_timing',
        'ordering', 'overlap'
    )),
    blocking INTEGER NOT NULL CHECK (blocking IN (0, 1)),
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    target_timed_unit_id TEXT,
    UNIQUE (subtitle_validation_id, ordinal),
    FOREIGN KEY (subtitle_validation_id)
        REFERENCES subtitle_validations(identity) ON DELETE CASCADE
)""",
)

_V16_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_review_preparations (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_validation_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_intake_id TEXT NOT NULL,
    source_readiness_id TEXT NOT NULL,
    source_selection_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    source_decision_id TEXT NOT NULL,
    source_review_item_id TEXT NOT NULL,
    source_candidate_reference_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    source_transcript_validation_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    item_count INTEGER NOT NULL CHECK (item_count >= 0),
    source_structural_valid INTEGER NOT NULL CHECK (source_structural_valid IN (0, 1)),
    provenance_complete INTEGER NOT NULL CHECK (provenance_complete IN (0, 1)),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_preparation_id TEXT,
    CHECK ((sequence = 0 AND previous_preparation_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_review_preparation_items (
    subtitle_review_preparation_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_finding_id TEXT NOT NULL,
    rule TEXT NOT NULL CHECK (length(trim(rule)) > 0),
    target_timed_unit_id TEXT,
    PRIMARY KEY (subtitle_review_preparation_id, ordinal),
    FOREIGN KEY (subtitle_review_preparation_id)
        REFERENCES subtitle_review_preparations(identity) ON DELETE CASCADE
)""",
)

_V17_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_review_decisions (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_preparation_id TEXT NOT NULL,
    source_validation_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_finding_id TEXT NOT NULL,
    rule TEXT NOT NULL CHECK (length(trim(rule)) > 0),
    reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('accept', 'reject', 'modify')),
    decided_at TEXT NOT NULL CHECK (length(trim(decided_at)) > 0),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    previous_decision_id TEXT,
    rationale TEXT,
    modified_text TEXT,
    CHECK ((kind = 'modify' AND modified_text IS NOT NULL) OR
           (kind IN ('accept', 'reject') AND modified_text IS NULL)),
    CHECK ((sequence = 0 AND previous_decision_id IS NULL) OR sequence > 0)
)""",
)

_V18_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_decision_revisions (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_review_decision_id TEXT NOT NULL,
    decision_kind TEXT NOT NULL CHECK (decision_kind IN ('accept', 'reject', 'modify')),
    outcome TEXT NOT NULL CHECK (outcome IN ('accepted', 'rejected', 'modified')),
    applied_text TEXT,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_preparation_id TEXT NOT NULL,
    source_validation_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_finding_id TEXT NOT NULL,
    rule TEXT NOT NULL CHECK (length(trim(rule)) > 0),
    target_timed_unit_id TEXT,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_revision_id TEXT,
    CHECK ((decision_kind = 'accept' AND outcome = 'accepted')
           OR (decision_kind = 'reject' AND outcome = 'rejected')
           OR (decision_kind = 'modify' AND outcome = 'modified')),
    CHECK ((outcome = 'modified' AND applied_text IS NOT NULL) OR
           (outcome IN ('accepted', 'rejected') AND applied_text IS NULL)),
    CHECK ((sequence = 0 AND previous_revision_id IS NULL) OR sequence > 0)
)""",
)

_V19_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_final_subtitles (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_decision_revision_id TEXT NOT NULL,
    decision_kind TEXT NOT NULL CHECK (decision_kind IN ('accept', 'reject', 'modify')),
    applied_outcome TEXT NOT NULL CHECK (applied_outcome IN ('accepted', 'rejected', 'modified')),
    final_outcome TEXT NOT NULL CHECK (final_outcome IN ('final', 'not_final')),
    applied_text TEXT,
    source_review_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_preparation_id TEXT NOT NULL,
    source_validation_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    source_candidate_id TEXT NOT NULL,
    source_finding_id TEXT NOT NULL,
    rule TEXT NOT NULL CHECK (length(trim(rule)) > 0),
    target_timed_unit_id TEXT,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_final_id TEXT,
    CHECK ((decision_kind = 'accept' AND applied_outcome = 'accepted')
           OR (decision_kind = 'reject' AND applied_outcome = 'rejected')
           OR (decision_kind = 'modify' AND applied_outcome = 'modified')),
    CHECK ((applied_outcome IN ('accepted', 'modified') AND final_outcome = 'final')
           OR (applied_outcome = 'rejected' AND final_outcome = 'not_final')),
    CHECK ((applied_outcome = 'modified' AND applied_text IS NOT NULL) OR
           (applied_outcome IN ('accepted', 'rejected') AND applied_text IS NULL)),
    CHECK ((sequence = 0 AND previous_final_id IS NULL) OR sequence > 0)
)""",
)

_V20_ADDITION_STATEMENTS = (
    """CREATE TABLE subtitle_approved_documents (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_time_revision_id TEXT NOT NULL,
    source_reading_revision_id TEXT NOT NULL,
    eligibility TEXT NOT NULL CHECK (eligibility IN ('eligible', 'ineligible')),
    ineligibility_reason TEXT,
    source_candidate_id TEXT NOT NULL,
    source_transcript_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    source_timeline_id TEXT NOT NULL,
    omitted_unit_count INTEGER NOT NULL CHECK (omitted_unit_count >= 0),
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_document_id TEXT,
    CHECK ((eligibility = 'eligible' AND ineligibility_reason IS NULL) OR
           (eligibility = 'ineligible' AND ineligibility_reason IS NOT NULL
            AND length(trim(ineligibility_reason)) > 0)),
    CHECK ((sequence = 0 AND previous_document_id IS NULL) OR sequence > 0)
)""",
    """CREATE TABLE subtitle_approved_units (
    identity TEXT PRIMARY KEY,
    subtitle_approved_document_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_timed_unit_id TEXT NOT NULL,
    source_reading_unit_id TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('accepted', 'modified', 'untouched')),
    display_order INTEGER NOT NULL CHECK (display_order >= 0),
    start REAL NOT NULL CHECK (start >= 0),
    end REAL NOT NULL CHECK (end >= start),
    source_final_subtitle_id TEXT,
    CHECK ((origin = 'untouched' AND source_final_subtitle_id IS NULL) OR
           (origin IN ('accepted', 'modified') AND source_final_subtitle_id IS NOT NULL)),
    UNIQUE (subtitle_approved_document_id, ordinal),
    FOREIGN KEY (subtitle_approved_document_id)
        REFERENCES subtitle_approved_documents(identity) ON DELETE CASCADE
)""",
    """CREATE TABLE subtitle_approved_unit_lines (
    subtitle_approved_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    line TEXT NOT NULL CHECK (length(trim(line)) > 0),
    PRIMARY KEY (subtitle_approved_unit_id, ordinal),
    FOREIGN KEY (subtitle_approved_unit_id)
        REFERENCES subtitle_approved_units(identity) ON DELETE CASCADE
)""",
)

_V9_ADDITION_STATEMENTS = (
    """CREATE TABLE transcript_current_selections (
    identity TEXT PRIMARY KEY,
    domain_result_id TEXT NOT NULL,
    source_applicability_id TEXT NOT NULL,
    applicability_outcome TEXT NOT NULL CHECK (
        applicability_outcome IN ('applicable', 'not_applicable', 'superseded_by_modification')
    ),
    outcome TEXT NOT NULL CHECK (outcome IN ('selected', 'not_selected')),
    source_decision_id TEXT NOT NULL,
    review_item_id TEXT NOT NULL,
    candidate_reference_id TEXT NOT NULL,
    source_revision_id TEXT NOT NULL,
    processing_run_id TEXT NOT NULL,
    unit_execution_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    previous_selection_id TEXT,
    CHECK ((applicability_outcome = 'applicable' AND outcome = 'selected') OR
           (applicability_outcome IN ('not_applicable', 'superseded_by_modification')
            AND outcome = 'not_selected')),
    CHECK ((sequence = 0 AND previous_selection_id IS NULL) OR sequence > 0)
)""",
)

_V1_EXPECTED_COLUMNS = {
    "schema_metadata": (
        ("singleton", "INTEGER", 0, 1),
        ("version", "INTEGER", 1, 0),
    ),
    "processing_units": (
        ("identity", "TEXT", 0, 1),
        ("purpose", "TEXT", 1, 0),
        ("independently_retryable", "INTEGER", 1, 0),
    ),
    "processing_unit_dependencies": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("dependency_id", "TEXT", 1, 0),
    ),
    "processing_unit_capabilities": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("capability", "TEXT", 1, 0),
    ),
    "processing_unit_result_kinds": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("result_kind", "TEXT", 1, 0),
    ),
}

_V2_EXPECTED_COLUMNS = {
    **_V1_EXPECTED_COLUMNS,
    "processing_runs": (
        ("identity", "TEXT", 0, 1),
        ("intent_purpose", "TEXT", 1, 0),
        ("intent_retry_of", "TEXT", 0, 0),
        ("intent_reprocessing_of", "TEXT", 0, 0),
        ("working_context", "TEXT", 1, 0),
        ("configuration", "TEXT", 0, 0),
        ("state", "TEXT", 1, 0),
        ("reprocessing_of", "TEXT", 0, 0),
    ),
    "processing_run_inputs": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("input_reference", "TEXT", 1, 0),
    ),
    "processing_run_upstream_results": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "processing_run_units": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("processing_unit_id", "TEXT", 1, 0),
    ),
    "processing_run_unit_executions": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("unit_execution_id", "TEXT", 1, 0),
    ),
    "processing_run_results": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "processing_run_failures": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("failure_id", "TEXT", 1, 0),
    ),
}

_V3_EXPECTED_COLUMNS = {
    **_V2_EXPECTED_COLUMNS,
    "unit_executions": (
        ("identity", "TEXT", 0, 1),
        ("processing_run_id", "TEXT", 1, 0),
        ("processing_unit_id", "TEXT", 1, 0),
        ("configuration", "TEXT", 0, 0),
        ("state", "TEXT", 1, 0),
        ("outcome_kind", "TEXT", 0, 0),
        ("outcome_detail", "TEXT", 0, 0),
        ("retry_of", "TEXT", 0, 0),
        ("cancelled_from", "TEXT", 0, 0),
        ("recovery_of", "TEXT", 0, 0),
    ),
    "unit_execution_inputs": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("input_reference", "TEXT", 1, 0),
    ),
    "unit_execution_capabilities": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("capability", "TEXT", 1, 0),
    ),
    "unit_execution_plugins": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("plugin_reference", "TEXT", 1, 0),
    ),
    "unit_execution_results": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "unit_execution_failures": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("failure_id", "TEXT", 1, 0),
    ),
    "unit_execution_diagnostics": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("diagnostic_id", "TEXT", 1, 0),
    ),
}

_V4_EXPECTED_COLUMNS = {
    **_V3_EXPECTED_COLUMNS,
    "domain_result_references": (
        ("identity", "TEXT", 0, 1),
        ("kind", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 0, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("revision_of", "TEXT", 0, 0),
        ("applicability", "TEXT", 0, 0),
    ),
    "domain_result_upstream_results": (
        ("domain_result_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("upstream_domain_result_id", "TEXT", 1, 0),
    ),
    "failures": (
        ("identity", "TEXT", 0, 1),
        ("category", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 0, 0),
        ("unit_execution_id", "TEXT", 0, 0),
        ("retryable", "INTEGER", 1, 0),
        ("reprocessing_required", "INTEGER", 1, 0),
        ("human_action_required", "INTEGER", 1, 0),
    ),
    "failure_affected_inputs": (
        ("failure_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("input_reference", "TEXT", 1, 0),
    ),
    "failure_affected_results": (
        ("failure_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "failure_diagnostics": (
        ("failure_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("diagnostic_id", "TEXT", 1, 0),
    ),
}

_V5_EXPECTED_COLUMNS = {
    **_V4_EXPECTED_COLUMNS,
    "provider_transcript_results": (
        ("identity", "TEXT", 0, 1),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("capability", "TEXT", 1, 0),
        ("provider_reference", "TEXT", 1, 0),
        ("original_content", "TEXT", 1, 0),
        ("plugin_reference", "TEXT", 0, 0),
        ("uncertainty", "REAL", 0, 0),
        ("normalized", "INTEGER", 1, 0),
    ),
    "provider_transcript_result_diagnostics": (
        ("provider_transcript_result_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("diagnostic_id", "TEXT", 1, 0),
    ),
    "transcript_segments": (
        ("identity", "TEXT", 0, 1),
        ("transcript_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("text", "TEXT", 1, 0),
        ("source_order", "INTEGER", 1, 0),
        ("start", "REAL", 0, 0),
        ("end", "REAL", 0, 0),
        ("speaker_label", "TEXT", 0, 0),
        ("confidence", "REAL", 0, 0),
        ("uncertainty", "REAL", 0, 0),
        ("replaces_segment_id", "TEXT", 0, 0),
    ),
    "raw_transcripts": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("provider_transcript_result_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 0, 0),
    ),
    "raw_transcript_segments": (
        ("raw_transcript_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("transcript_segment_id", "TEXT", 1, 0),
    ),
    "correction_candidates": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("transcript_id", "TEXT", 1, 0),
        ("segment_id", "TEXT", 1, 0),
        ("proposed_text", "TEXT", 1, 0),
        ("rationale", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("target_revision_id", "TEXT", 0, 0),
        ("confidence", "REAL", 0, 0),
        ("uncertainty", "REAL", 0, 0),
        ("capability", "TEXT", 0, 0),
        ("plugin_reference", "TEXT", 0, 0),
        ("provider_reference", "TEXT", 0, 0),
    ),
    "correction_candidate_evidence": (
        ("correction_candidate_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("evidence", "TEXT", 1, 0),
    ),
    "corrected_transcript_revisions": (
        ("identity", "TEXT", 0, 1),
        ("transcript_id", "TEXT", 1, 0),
        ("domain_result_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("parent_raw_transcript_id", "TEXT", 0, 0),
        ("parent_revision_id", "TEXT", 0, 0),
        ("decision_reference", "TEXT", 0, 0),
        ("validation_id", "TEXT", 0, 0),
        ("applicability", "TEXT", 1, 0),
    ),
    "corrected_transcript_revision_segments": (
        ("transcript_revision_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("transcript_segment_id", "TEXT", 1, 0),
    ),
    "corrected_transcript_revision_candidates": (
        ("transcript_revision_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("correction_candidate_id", "TEXT", 1, 0),
    ),
}

_V6_EXPECTED_COLUMNS = {
    **_V5_EXPECTED_COLUMNS,
    "review_candidate_references": (
        ("identity", "TEXT", 0, 1),
        ("kind", "TEXT", 1, 0),
        ("source_domain", "TEXT", 1, 0),
        ("domain_result_id", "TEXT", 0, 0),
        ("source_media_id", "TEXT", 0, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("processing_run_id", "TEXT", 0, 0),
        ("unit_execution_id", "TEXT", 0, 0),
        ("revision_reference", "TEXT", 0, 0),
        ("applicability", "TEXT", 1, 0),
    ),
    "review_contexts": (
        ("identity", "TEXT", 0, 1),
        ("source_media_id", "TEXT", 0, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("blocking_reason", "TEXT", 0, 0),
    ),
    "review_context_domain_results": (
        ("review_context_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "review_context_evidence": (
        ("review_context_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("evidence", "TEXT", 1, 0),
    ),
    "review_items": (
        ("identity", "TEXT", 0, 1),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("context_id", "TEXT", 1, 0),
        ("applicability_at_creation", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 0, 0),
        ("unit_execution_id", "TEXT", 0, 0),
    ),
    "transcript_review_preparations": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("context_id", "TEXT", 1, 0),
        ("item_count", "INTEGER", 1, 0),
        ("structural_valid", "INTEGER", 1, 0),
        ("provenance_complete", "INTEGER", 1, 0),
        ("ordering_valid", "INTEGER", 1, 0),
    ),
    "transcript_review_preparation_items": (
        ("transcript_review_preparation_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("review_item_id", "TEXT", 1, 0),
    ),
    "transcript_review_preparation_candidates": (
        ("transcript_review_preparation_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("candidate_reference_id", "TEXT", 1, 0),
    ),
    "transcript_review_preparation_groups": (
        ("transcript_review_preparation_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("group_key", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
    ),
}

_V7_EXPECTED_COLUMNS = {
    **_V6_EXPECTED_COLUMNS,
    "transcript_review_decisions": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("reviewer", "TEXT", 1, 0),
        ("kind", "TEXT", 1, 0),
        ("decided_at", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("previous_decision_id", "TEXT", 0, 0),
        ("rationale", "TEXT", 0, 0),
        ("modified_text", "TEXT", 0, 0),
    ),
}

_V8_EXPECTED_COLUMNS = {
    **_V7_EXPECTED_COLUMNS,
    "transcript_applicability_evaluations": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("decision_kind", "TEXT", 1, 0),
        ("outcome", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_evaluation_id", "TEXT", 0, 0),
    ),
}

_V9_EXPECTED_COLUMNS = {
    **_V8_EXPECTED_COLUMNS,
    "transcript_current_selections": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("applicability_outcome", "TEXT", 1, 0),
        ("outcome", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_selection_id", "TEXT", 0, 0),
    ),
}

_V10_EXPECTED_COLUMNS = {
    **_V9_EXPECTED_COLUMNS,
    "transcript_readiness_evaluations": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("selection_outcome", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("applicability_outcome", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 1, 0),
        ("structural_valid", "INTEGER", 1, 0),
        ("outcome", "TEXT", 1, 0),
        ("reason_code", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_readiness_id", "TEXT", 0, 0),
    ),
}

_V11_EXPECTED_COLUMNS = {
    **_V10_EXPECTED_COLUMNS,
    "subtitle_transcript_intakes": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("readiness_outcome", "TEXT", 1, 0),
        ("outcome", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_intake_id", "TEXT", 0, 0),
    ),
}

_V12_EXPECTED_COLUMNS = {
    **_V11_EXPECTED_COLUMNS,
    "subtitle_candidates": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_intake_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_candidate_id", "TEXT", 0, 0),
    ),
    "subtitle_candidate_cues": (
        ("identity", "TEXT", 0, 1),
        ("subtitle_candidate_id", "TEXT", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("text", "TEXT", 1, 0),
        ("display_order", "INTEGER", 1, 0),
        ("start", "REAL", 0, 0),
        ("end", "REAL", 0, 0),
    ),
    "subtitle_candidate_cue_segments": (
        ("subtitle_candidate_cue_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("transcript_segment_id", "TEXT", 1, 0),
    ),
}

_V13_EXPECTED_COLUMNS = {
    **_V12_EXPECTED_COLUMNS,
    "subtitle_reading_revisions": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_intake_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_reading_revision_id", "TEXT", 0, 0),
    ),
    "subtitle_reading_units": (
        ("identity", "TEXT", 0, 1),
        ("subtitle_reading_revision_id", "TEXT", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("display_order", "INTEGER", 1, 0),
        ("start", "REAL", 0, 0),
        ("end", "REAL", 0, 0),
    ),
    "subtitle_reading_unit_source_cues": (
        ("subtitle_reading_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("subtitle_candidate_cue_id", "TEXT", 1, 0),
    ),
    "subtitle_reading_unit_lines": (
        ("subtitle_reading_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("line", "TEXT", 1, 0),
    ),
}

_V14_EXPECTED_COLUMNS = {
    **_V13_EXPECTED_COLUMNS,
    "subtitle_time_revisions": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_intake_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("validation_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_time_revision_id", "TEXT", 0, 0),
    ),
    "subtitle_timed_units": (
        ("identity", "TEXT", 0, 1),
        ("subtitle_time_revision_id", "TEXT", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("source_reading_unit_id", "TEXT", 1, 0),
        ("timing_status", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 0, 0),
        ("display_order", "INTEGER", 1, 0),
        ("start", "REAL", 0, 0),
        ("end", "REAL", 0, 0),
    ),
}

_V15_EXPECTED_COLUMNS = {
    **_V14_EXPECTED_COLUMNS,
    "subtitle_validations": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_intake_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("source_transcript_validation_id", "TEXT", 1, 0),
        ("structural_valid", "INTEGER", 1, 0),
        ("provenance_complete", "INTEGER", 1, 0),
        ("timeline_traceable", "INTEGER", 1, 0),
        ("ordering_consistent", "INTEGER", 1, 0),
        ("time_consistent", "INTEGER", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_validation_id", "TEXT", 0, 0),
    ),
    "subtitle_validation_findings": (
        ("identity", "TEXT", 0, 1),
        ("subtitle_validation_id", "TEXT", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("rule", "TEXT", 1, 0),
        ("category", "TEXT", 1, 0),
        ("blocking", "INTEGER", 1, 0),
        ("description", "TEXT", 1, 0),
        ("target_timed_unit_id", "TEXT", 0, 0),
    ),
}

_V16_EXPECTED_COLUMNS = {
    **_V15_EXPECTED_COLUMNS,
    "subtitle_review_preparations": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_validation_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_intake_id", "TEXT", 1, 0),
        ("source_readiness_id", "TEXT", 1, 0),
        ("source_selection_id", "TEXT", 1, 0),
        ("source_applicability_id", "TEXT", 1, 0),
        ("source_decision_id", "TEXT", 1, 0),
        ("source_review_item_id", "TEXT", 1, 0),
        ("source_candidate_reference_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("source_transcript_validation_id", "TEXT", 1, 0),
        ("context_id", "TEXT", 1, 0),
        ("item_count", "INTEGER", 1, 0),
        ("source_structural_valid", "INTEGER", 1, 0),
        ("provenance_complete", "INTEGER", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_preparation_id", "TEXT", 0, 0),
    ),
    "subtitle_review_preparation_items": (
        ("subtitle_review_preparation_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_finding_id", "TEXT", 1, 0),
        ("rule", "TEXT", 1, 0),
        ("target_timed_unit_id", "TEXT", 0, 0),
    ),
}

_V17_EXPECTED_COLUMNS = {
    **_V16_EXPECTED_COLUMNS,
    "subtitle_review_decisions": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_preparation_id", "TEXT", 1, 0),
        ("source_validation_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_finding_id", "TEXT", 1, 0),
        ("rule", "TEXT", 1, 0),
        ("reviewer", "TEXT", 1, 0),
        ("kind", "TEXT", 1, 0),
        ("decided_at", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("previous_decision_id", "TEXT", 0, 0),
        ("rationale", "TEXT", 0, 0),
        ("modified_text", "TEXT", 0, 0),
    ),
}

_V18_EXPECTED_COLUMNS = {
    **_V17_EXPECTED_COLUMNS,
    "subtitle_decision_revisions": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_review_decision_id", "TEXT", 1, 0),
        ("decision_kind", "TEXT", 1, 0),
        ("outcome", "TEXT", 1, 0),
        ("applied_text", "TEXT", 0, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_preparation_id", "TEXT", 1, 0),
        ("source_validation_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_finding_id", "TEXT", 1, 0),
        ("rule", "TEXT", 1, 0),
        ("target_timed_unit_id", "TEXT", 0, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_revision_id", "TEXT", 0, 0),
    ),
}

_V19_EXPECTED_COLUMNS = {
    **_V18_EXPECTED_COLUMNS,
    "subtitle_final_subtitles": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_decision_revision_id", "TEXT", 1, 0),
        ("decision_kind", "TEXT", 1, 0),
        ("applied_outcome", "TEXT", 1, 0),
        ("final_outcome", "TEXT", 1, 0),
        ("applied_text", "TEXT", 0, 0),
        ("source_review_decision_id", "TEXT", 1, 0),
        ("review_item_id", "TEXT", 1, 0),
        ("candidate_reference_id", "TEXT", 1, 0),
        ("source_preparation_id", "TEXT", 1, 0),
        ("source_validation_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_finding_id", "TEXT", 1, 0),
        ("rule", "TEXT", 1, 0),
        ("target_timed_unit_id", "TEXT", 0, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_final_id", "TEXT", 0, 0),
    ),
}

_V20_EXPECTED_COLUMNS = {
    **_V19_EXPECTED_COLUMNS,
    "subtitle_approved_documents": (
        ("identity", "TEXT", 0, 1),
        ("domain_result_id", "TEXT", 1, 0),
        ("source_time_revision_id", "TEXT", 1, 0),
        ("source_reading_revision_id", "TEXT", 1, 0),
        ("eligibility", "TEXT", 1, 0),
        ("ineligibility_reason", "TEXT", 0, 0),
        ("source_candidate_id", "TEXT", 1, 0),
        ("source_transcript_id", "TEXT", 1, 0),
        ("source_revision_id", "TEXT", 1, 0),
        ("source_media_id", "TEXT", 1, 0),
        ("source_timeline_id", "TEXT", 1, 0),
        ("omitted_unit_count", "INTEGER", 1, 0),
        ("processing_run_id", "TEXT", 1, 0),
        ("unit_execution_id", "TEXT", 1, 0),
        ("sequence", "INTEGER", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("previous_document_id", "TEXT", 0, 0),
    ),
    "subtitle_approved_units": (
        ("identity", "TEXT", 0, 1),
        ("subtitle_approved_document_id", "TEXT", 1, 0),
        ("ordinal", "INTEGER", 1, 0),
        ("source_timed_unit_id", "TEXT", 1, 0),
        ("source_reading_unit_id", "TEXT", 1, 0),
        ("origin", "TEXT", 1, 0),
        ("display_order", "INTEGER", 1, 0),
        ("start", "REAL", 1, 0),
        ("end", "REAL", 1, 0),
        ("source_final_subtitle_id", "TEXT", 0, 0),
    ),
    "subtitle_approved_unit_lines": (
        ("subtitle_approved_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("line", "TEXT", 1, 0),
    ),
}


def initialize_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Create the latest schema for a new path; validate existing databases."""

    path = _validate_database_path(database_path)
    is_new = not path.exists()
    if not is_new and not path.is_file():
        raise PersistenceError("SQLite database path must be a file")
    connection = _connect(path)
    try:
        if is_new:
            _initialize_latest_schema(connection)
        _validate_initialized_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def open_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Open and validate a supported database without creating or migrating it."""

    path = _validate_database_path(database_path)
    if not path.is_file():
        raise PersistenceError("SQLite database must already be initialized")
    connection = _connect(path)
    try:
        _validate_initialized_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def migrate_sqlite_database(
    database_path: str | Path, target_version: int = SQLITE_SCHEMA_VERSION
) -> None:
    """Explicitly perform one approved migration step or validate a no-op target."""

    if target_version not in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20):
        raise PersistenceError(f"unsupported SQLite migration target: {target_version}")
    path = _validate_database_path(database_path)
    if not path.is_file():
        raise PersistenceError("SQLite database must already exist for migration")
    connection = _connect(path)
    try:
        current_version = _validate_initialized_connection(connection)
        if current_version == target_version:
            return
        if current_version == 1 and target_version == 2:
            _migrate_v1_to_v2(connection)
            return
        if current_version == 2 and target_version == 3:
            _migrate_v2_to_v3(connection)
            return
        if current_version == 3 and target_version == 4:
            _migrate_v3_to_v4(connection)
            return
        if current_version == 4 and target_version == 5:
            _migrate_v4_to_v5(connection)
            return
        if current_version == 5 and target_version == 6:
            _migrate_v5_to_v6(connection)
            return
        if current_version == 6 and target_version == 7:
            _migrate_v6_to_v7(connection)
            return
        if current_version == 7 and target_version == 8:
            _migrate_v7_to_v8(connection)
            return
        if current_version == 8 and target_version == 9:
            _migrate_v8_to_v9(connection)
            return
        if current_version == 9 and target_version == 10:
            _migrate_v9_to_v10(connection)
            return
        if current_version == 10 and target_version == 11:
            _migrate_v10_to_v11(connection)
            return
        if current_version == 11 and target_version == 12:
            _migrate_v11_to_v12(connection)
            return
        if current_version == 12 and target_version == 13:
            _migrate_v12_to_v13(connection)
            return
        if current_version == 13 and target_version == 14:
            _migrate_v13_to_v14(connection)
            return
        if current_version == 14 and target_version == 15:
            _migrate_v14_to_v15(connection)
            return
        if current_version == 15 and target_version == 16:
            _migrate_v15_to_v16(connection)
            return
        if current_version == 16 and target_version == 17:
            _migrate_v16_to_v17(connection)
            return
        if current_version == 17 and target_version == 18:
            _migrate_v17_to_v18(connection)
            return
        if current_version == 18 and target_version == 19:
            _migrate_v18_to_v19(connection)
            return
        if current_version == 19 and target_version == 20:
            _migrate_v19_to_v20(connection)
            return
        raise PersistenceError(
            f"unsupported SQLite migration: {current_version} to {target_version}"
        )
    finally:
        connection.close()


def validate_sqlite_connection(connection: sqlite3.Connection) -> int:
    """Validate a caller-owned connection and return its supported schema version."""

    return _validate_initialized_connection(connection)


def _validate_database_path(database_path: str | Path) -> Path:
    if isinstance(database_path, str) and (
        database_path == ":memory:" or database_path.startswith("file:")
    ):
        raise PersistenceError("SQLite memory and URI paths are not supported")
    try:
        path = Path(database_path)
    except TypeError:
        raise PersistenceError("SQLite database path must be path-like") from None
    if not path.is_absolute():
        raise PersistenceError("SQLite database path must be absolute")
    if not path.parent.exists() or not path.parent.is_dir():
        raise PersistenceError("SQLite database parent directory must exist")
    return path


def _connect(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            connection.close()
            raise PersistenceError("SQLite foreign key enforcement is unavailable")
        return connection
    except PersistenceError:
        raise
    except sqlite3.Error as error:
        raise PersistenceError(f"could not open SQLite database: {error}") from error


def _initialize_latest_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN")
        for statement in (
            *_V1_TABLE_STATEMENTS,
            *_V2_ADDITION_STATEMENTS,
            *_V3_ADDITION_STATEMENTS,
            *_V4_ADDITION_STATEMENTS,
            *_V5_ADDITION_STATEMENTS,
            *_V6_ADDITION_STATEMENTS,
            *_V7_ADDITION_STATEMENTS,
            *_V8_ADDITION_STATEMENTS,
            *_V9_ADDITION_STATEMENTS,
            *_V10_ADDITION_STATEMENTS,
            *_V11_ADDITION_STATEMENTS,
            *_V12_ADDITION_STATEMENTS,
            *_V13_ADDITION_STATEMENTS,
            *_V14_ADDITION_STATEMENTS,
            *_V15_ADDITION_STATEMENTS,
            *_V16_ADDITION_STATEMENTS,
            *_V17_ADDITION_STATEMENTS,
            *_V18_ADDITION_STATEMENTS,
            *_V19_ADDITION_STATEMENTS,
            *_V20_ADDITION_STATEMENTS,
        ):
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_metadata(singleton, version) VALUES (1, ?)",
            (SQLITE_SCHEMA_VERSION,),
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not initialize SQLite schema: {error}") from error


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V2_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 2 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V3_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 3 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v3_to_v4(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V4_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 4 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v4_to_v5(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V5_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 5 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v5_to_v6(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V6_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 6 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v6_to_v7(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V7_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 7 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v7_to_v8(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V8_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 8 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v8_to_v9(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V9_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 9 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v9_to_v10(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V10_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 10 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v10_to_v11(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V11_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 11 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v11_to_v12(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V12_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 12 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v12_to_v13(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V13_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 13 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v13_to_v14(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V14_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 14 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v14_to_v15(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V15_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 15 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v15_to_v16(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V16_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 16 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v16_to_v17(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V17_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 17 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v17_to_v18(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V18_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 18 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v18_to_v19(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V19_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 19 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v19_to_v20(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V20_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 20 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _validate_initialized_connection(connection: sqlite3.Connection) -> int:
    try:
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise PersistenceError("SQLite foreign key enforcement must be enabled")
        metadata_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_metadata'"
        ).fetchone()
        if metadata_exists is None:
            raise PersistenceError("SQLite database is not initialized")
        versions = connection.execute(
            "SELECT singleton, version FROM schema_metadata"
        ).fetchall()
        if len(versions) != 1 or versions[0][0] != 1:
            raise PersistenceError("SQLite schema version marker is malformed")
        version = versions[0][1]
        if version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedSchemaVersionError(
                f"unsupported SQLite schema version: {version}"
            )
        _validate_schema_shape(connection, version)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise PersistenceError("SQLite database contains foreign key violations")
        return version
    except (PersistenceError, UnsupportedSchemaVersionError):
        raise
    except sqlite3.Error as error:
        raise PersistenceError(f"could not validate SQLite schema: {error}") from error


def _validate_schema_shape(connection: sqlite3.Connection, version: int) -> None:
    expected_columns = {
        1: _V1_EXPECTED_COLUMNS,
        2: _V2_EXPECTED_COLUMNS,
        3: _V3_EXPECTED_COLUMNS,
        4: _V4_EXPECTED_COLUMNS,
        5: _V5_EXPECTED_COLUMNS,
        6: _V6_EXPECTED_COLUMNS,
        7: _V7_EXPECTED_COLUMNS,
        8: _V8_EXPECTED_COLUMNS,
        9: _V9_EXPECTED_COLUMNS,
        10: _V10_EXPECTED_COLUMNS,
        11: _V11_EXPECTED_COLUMNS,
        12: _V12_EXPECTED_COLUMNS,
        13: _V13_EXPECTED_COLUMNS,
        14: _V14_EXPECTED_COLUMNS,
        15: _V15_EXPECTED_COLUMNS,
        16: _V16_EXPECTED_COLUMNS,
        17: _V17_EXPECTED_COLUMNS,
        18: _V18_EXPECTED_COLUMNS,
        19: _V19_EXPECTED_COLUMNS,
        20: _V20_EXPECTED_COLUMNS,
    }[version]
    for table, expected in expected_columns.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        )
        if actual != expected:
            raise PersistenceError(f"SQLite schema table is malformed: {table}")
    _validate_v1_foreign_keys(connection)
    if version == 2:
        _validate_v2_foreign_keys(connection)
    elif version >= 3:
        _validate_v2_foreign_keys(connection)
        _validate_v3_foreign_keys(connection)
        if version >= 4:
            _validate_v4_foreign_keys(connection)
        if version >= 5:
            _validate_v5_foreign_keys(connection)
        if version >= 6:
            _validate_v6_foreign_keys(connection)


def _validate_v1_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "processing_unit_dependencies",
        "processing_unit_capabilities",
        "processing_unit_result_kinds",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "processing_units"
            and row[3] == "processing_unit_id"
            and row[4] == "identity"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v2_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "processing_run_inputs",
        "processing_run_upstream_results",
        "processing_run_units",
        "processing_run_unit_executions",
        "processing_run_results",
        "processing_run_failures",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "processing_runs"
            and row[3] == "processing_run_id"
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v3_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "unit_execution_inputs",
        "unit_execution_capabilities",
        "unit_execution_plugins",
        "unit_execution_results",
        "unit_execution_failures",
        "unit_execution_diagnostics",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "unit_executions"
            and row[3] == "unit_execution_id"
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v4_foreign_keys(connection: sqlite3.Connection) -> None:
    expected = (
        (
            "domain_result_upstream_results",
            "domain_result_references",
            "domain_result_id",
        ),
        ("failure_affected_inputs", "failures", "failure_id"),
        ("failure_affected_results", "failures", "failure_id"),
        ("failure_diagnostics", "failures", "failure_id"),
    )
    for table, parent, parent_column in expected:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == parent
            and row[3] == parent_column
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v5_foreign_keys(connection: sqlite3.Connection) -> None:
    expected = (
        (
            "provider_transcript_result_diagnostics",
            "provider_transcript_results",
            "provider_transcript_result_id",
        ),
        ("raw_transcript_segments", "raw_transcripts", "raw_transcript_id"),
        (
            "correction_candidate_evidence",
            "correction_candidates",
            "correction_candidate_id",
        ),
        (
            "corrected_transcript_revision_segments",
            "corrected_transcript_revisions",
            "transcript_revision_id",
        ),
        (
            "corrected_transcript_revision_candidates",
            "corrected_transcript_revisions",
            "transcript_revision_id",
        ),
    )
    for table, parent, parent_column in expected:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == parent
            and row[3] == parent_column
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v6_foreign_keys(connection: sqlite3.Connection) -> None:
    expected = (
        ("review_context_domain_results", "review_contexts", "review_context_id"),
        ("review_context_evidence", "review_contexts", "review_context_id"),
        (
            "transcript_review_preparation_items",
            "transcript_review_preparations",
            "transcript_review_preparation_id",
        ),
        (
            "transcript_review_preparation_candidates",
            "transcript_review_preparations",
            "transcript_review_preparation_id",
        ),
        (
            "transcript_review_preparation_groups",
            "transcript_review_preparations",
            "transcript_review_preparation_id",
        ),
    )
    for table, parent, parent_column in expected:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == parent
            and row[3] == parent_column
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _commit(connection: sqlite3.Connection) -> None:
    connection.execute("COMMIT")


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
