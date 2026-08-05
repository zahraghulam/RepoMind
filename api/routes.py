"""
FastAPI Routes for RepoMind Agent System
"""

import traceback
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks

from api.errors import (
    InvalidInstructionError,
    InvalidRepoURLError,
    JobAlreadyRunningError,
)
from api.schemas import (
    JobStatus,
    JobStatusResponse,
    RefineRequest,
    RefineResponse,
    RunRequest,
    RunResponse,
)
from tools.agent_runner import run_agent

from utils.job_manager import job_manager

router = APIRouter(tags=["Agent"])


def process_job(job_id: str) -> None:
    """
    Background task that runs the agent and updates the job.
    """
    try:
        job = job_manager.get(job_id)

        job.status = JobStatus.running.value
        job_manager.update(job)

        result = run_agent(
            repo_url=job.repo_url,
            instruction=job.instruction,
            session_id=job_id,
            branch_name=getattr(job, "branch_name", "repomind/auto-fix"),
            pr_title_override=getattr(job, "pr_title", None),
        )

        pr_url = result.get("pr_url")

        if pr_url:
            job.status = JobStatus.completed.value
            job.pr_url = pr_url
            job.diff_summary = result.get("summary")
        else:
            job.status = JobStatus.failed.value
            job.error_message = (
                result.get("summary")
                or "Agent completed but no file changes were made."
            )

        job_manager.update(job)

    except RuntimeError:
        traceback.print_exc()
        raise


@router.post("/run", response_model=RunResponse)
async def run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
) -> RunResponse:

    if urlparse(request.repo_url).netloc != "github.com":
        raise InvalidRepoURLError(request.repo_url)

    if not request.instruction.strip():
        raise InvalidInstructionError()

    job_id = job_manager.create_job(
        repo_url=request.repo_url,
        instruction=request.instruction,
    )

    job = job_manager.get(job_id)

    job.branch_name = request.branch_name  # type: ignore[attr-defined]
    job.pr_title = request.pr_title  # type: ignore[attr-defined]

    background_tasks.add_task(process_job, job_id)

    return RunResponse(
        job_id=job_id,
        status=JobStatus.queued,
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def status(job_id: str) -> JobStatusResponse:

    job = job_manager.get(job_id)

    return JobStatusResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        pr_url=job.pr_url,
        diff_summary=job.diff_summary,
        error_message=job.error_message,
    )


@router.post("/refine", response_model=RefineResponse)
async def refine(
    request: RefineRequest,
    background_tasks: BackgroundTasks,
) -> RefineResponse:

    job = job_manager.get(request.job_id)

    if job.status == JobStatus.running.value:
        raise JobAlreadyRunningError(request.job_id)

    if not request.instruction.strip():
        raise InvalidInstructionError()

    job.instruction += f"\nRefinement: {request.instruction}"
    job.status = JobStatus.queued.value

    job_manager.update(job)

    background_tasks.add_task(process_job, request.job_id)

    return RefineResponse(
        job_id=request.job_id,
        status=JobStatus.queued,
        message="Refinement queued — agent will run with full prior context.",
    )
