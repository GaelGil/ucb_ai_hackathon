from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlmodel import Session

from app.src.api.dependencies import AppServices, get_services
from app.src.api.dependencies import get_research_service
from app.src.api.research.service import ResearchService
from app.src.database.models.research import ResearchType
from app.src.jobs import JobRunner
from app.src.models import ResearchArtifact, ResearchResponse


router = APIRouter()


def _run_research_background(
    services: AppServices,
    job_id: str,
    dataset_id: str,
    force: bool,
    research_type: ResearchType,
) -> None:
    with Session(services.db_engine) as session:
        service = ResearchService(
            session=session,
            research_provider=services.research_provider,
            jobs=JobRunner(session, services.tracer),
            tracer=services.tracer,
        )
        service.complete_queued_research(
            job_id=job_id,
            dataset_id=dataset_id,
            force=force,
            research_type=research_type,
        )


@router.post("/datasets/{dataset_id}/research", response_model=ResearchResponse)
def create_research(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    service: ResearchService = Depends(get_research_service),
    force: bool = Query(default=False),
    research_type: ResearchType = Query(default=ResearchType.pos, alias="type"),
) -> ResearchResponse:
    services = get_services(request)
    if not services.settings.agent_jobs_background:
        research, job = service.ensure_research(dataset_id, force=force, research_type=research_type)
        return ResearchResponse(research=research, job=job)

    research, job = service.queue_research(dataset_id, force=force, research_type=research_type)
    if job.status.value == "running":
        background_tasks.add_task(
            _run_research_background,
            services,
            job.id,
            dataset_id,
            force,
            research_type,
        )
    return ResearchResponse(research=research, job=job)


@router.get("/datasets/{dataset_id}/research", response_model=ResearchArtifact | None)
def get_research(
    dataset_id: str,
    service: ResearchService = Depends(get_research_service),
    research_type: ResearchType = Query(default=ResearchType.pos, alias="type"),
) -> ResearchArtifact | None:
    return service.get_research(dataset_id, research_type=research_type)
