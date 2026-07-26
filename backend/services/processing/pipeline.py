"""Pipeline orchestrator — coordinates step execution."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from backend.services.processing.models import (
    PipelineRun, PipelineStep, PipelineStatus, StepStatus,
    PIPELINE_STEP_ORDER, STEP_TO_PIPELINE_STATUS,
    validate_pipeline_transition, transition_pipeline,
)
from backend.services.processing.storage import PipelineRepository


class PipelineOrchestrator:
    """Orchestrates document processing pipeline execution.

    Product Layer, not Platform.
    """

    def __init__(self, dsn: str):
        self._repo = PipelineRepository(dsn)

    def create_pipeline(self, document_id: str) -> PipelineRun:
        """Create a new pipeline run for a document."""
        pipeline = PipelineRun(
            pipeline_id=str(uuid.uuid4()),
            document_id=document_id,
            status="PENDING",
            created_at=datetime.now(timezone.utc),
        )
        self._repo.save_pipeline(pipeline)

        # Create step records
        for idx, step_type in enumerate(PIPELINE_STEP_ORDER):
            step = PipelineStep(
                step_id=str(uuid.uuid4()),
                pipeline_id=pipeline.pipeline_id,
                step_type=step_type,
                status="PENDING",
                order_index=idx,
            )
            self._repo.save_step(step)

        return pipeline

    def run_pipeline(self, pipeline_id: str,
                     step_executors: dict[str, Callable],
                     ) -> PipelineRun:
        """Execute all pipeline steps sequentially.

        Args:
            pipeline_id: Pipeline to run.
            step_executors: Dict mapping step_type to callable.
                Each callable receives (PipelineRun, PipelineStep, PipelineRepository)
                and returns (success_bool, step_result_dict_or_error_msg).

        Returns:
            Updated PipelineRun.
        """
        pipeline = self._repo.get_pipeline(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        # Start pipeline
        err = transition_pipeline(pipeline, "RUNNING")
        if err:
            raise ValueError(err)
        self._repo.save_pipeline(pipeline)

        steps = self._repo.get_steps(pipeline_id)
        all_ok = True

        for step in steps:
            if step.step_type not in step_executors:
                self._repo.update_step_status(step.step_id, "SKIPPED")
                continue

            step_exec = step_executors[step.step_type]
            self._repo.update_step_status(step.step_id, "RUNNING")

            try:
                success, result_or_error = step_exec(pipeline, step, self._repo)

                if success:
                    step_result = result_or_error
                    step.status = "COMPLETED"
                    step.result = step_result if isinstance(step_result, dict) else {}
                    step.completed_at = datetime.now(timezone.utc)
                    self._repo.save_step(step)

                    # Update pipeline status for this step
                    if step.step_type in STEP_TO_PIPELINE_STATUS:
                        target = STEP_TO_PIPELINE_STATUS[step.step_type]
                        transition_pipeline(pipeline, target)
                        self._repo.save_pipeline(pipeline)
                else:
                    error_msg = result_or_error if isinstance(result_or_error, str) else str(result_or_error)
                    self._repo.update_step_status(step.step_id, "FAILED", error=error_msg)
                    pipeline.status = "FAILED"
                    pipeline.completed_at = datetime.now(timezone.utc)
                    self._repo.save_pipeline(pipeline)
                    all_ok = False
                    break

            except Exception as e:
                self._repo.update_step_status(step.step_id, "FAILED", error=str(e))
                pipeline.status = "FAILED"
                pipeline.completed_at = datetime.now(timezone.utc)
                self._repo.save_pipeline(pipeline)
                all_ok = False
                break

        if all_ok:
            pipeline.status = "COMPLETED"
            pipeline.completed_at = datetime.now(timezone.utc)
            self._repo.save_pipeline(pipeline)

        return pipeline

    def get_pipeline(self, pipeline_id: str) -> PipelineRun | None:
        return self._repo.get_pipeline(pipeline_id)

    def get_pipeline_by_document(self, document_id: str) -> PipelineRun | None:
        return self._repo.get_pipeline_by_document(document_id)

    def get_steps(self, pipeline_id: str) -> list[PipelineStep]:
        return self._repo.get_steps(pipeline_id)
