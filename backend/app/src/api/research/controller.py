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
    print(
        "[research-debug] background task started "
        f"job_id={job_id} dataset_id={dataset_id} type={research_type.value} force={force}",
        flush=True,
    )
    with Session(services.db_engine) as session:
        service = ResearchService(
            session=session,
            research_provider=services.research_provider,
            jobs=JobRunner(session, services.tracer),
            tracer=services.tracer,
        )
        try:
            completed_job = service.complete_queued_research(
                job_id=job_id,
                dataset_id=dataset_id,
                force=force,
                research_type=research_type,
            )
            print(
                "[research-debug] background task completed "
                f"job_id={job_id} dataset_id={dataset_id} type={research_type.value} "
                f"job_status={completed_job.status.value} error={completed_job.error}",
                flush=True,
            )
        except Exception as exc:
            print(
                "[research-debug] background task error "
                f"job_id={job_id} dataset_id={dataset_id} type={research_type.value} error={type(exc).__name__}: {exc}",
                flush=True,
            )
            raise


@router.post("/datasets/{dataset_id}/research", response_model=ResearchResponse)
def create_research(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    service: ResearchService = Depends(get_research_service),
    force: bool = Query(default=False),
    research_type: ResearchType = Query(default=ResearchType.pos, alias="type"),
) -> ResearchResponse:
    print(
        "[research-debug] research endpoint reached "
        f"method=POST dataset_id={dataset_id} type={research_type.value} force={force}",
        flush=True,
    )
    services = get_services(request)
    if not services.settings.agent_jobs_background:
        print(
            "[research-debug] running research synchronously "
            f"dataset_id={dataset_id} type={research_type.value}",
            flush=True,
        )
        research, job = service.ensure_research(dataset_id, force=force, research_type=research_type)
        return ResearchResponse(research=research, job=job)

    research, job = service.queue_research(dataset_id, force=force, research_type=research_type)
    print(
        "[research-debug] research queued "
        f"dataset_id={dataset_id} type={research_type.value} job_id={job.id} status={job.status.value}",
        flush=True,
    )
    if job.status.value == "running":
        print(
            "[research-debug] adding background task "
            f"job_id={job.id} dataset_id={dataset_id} type={research_type.value}",
            flush=True,
        )
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
    print(
        "[research-debug] research endpoint reached "
        f"method=GET dataset_id={dataset_id} type={research_type.value}",
        flush=True,
    )
    return service.get_research(dataset_id, research_type=research_type)
