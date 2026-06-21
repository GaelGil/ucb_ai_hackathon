from __future__ import annotations

import threading

from flask import Blueprint, request
from sqlmodel import Session

from app.api.dependencies import AppServices, get_research_service, get_services
from app.api.responses import json_abort, json_response
from app.api.research.service import ResearchService
from app.database.models.research import ResearchType
from app.jobs import JobRunner
from app.schemas import ResearchArtifact, ResearchResponse


bp = Blueprint("research", __name__)


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


def _research_type() -> ResearchType:
    raw = request.args.get("type")
    if raw is None:
        return ResearchType.pos
    try:
        return ResearchType(raw)
    except ValueError:
        json_abort(422, f"Invalid research type: {raw}")


def _force() -> bool:
    return request.args.get("force", "false").strip().lower() in {"true", "1", "yes", "on"}


@bp.post("/datasets/<dataset_id>/research")
def create_research(dataset_id: str):
    research_type = _research_type()
    force = _force()
    print(
        "[research-debug] research endpoint reached "
        f"method=POST dataset_id={dataset_id} type={research_type.value} force={force}",
        flush=True,
    )
    services = get_services()
    if not services.settings.agent_jobs_background:
        print(
            "[research-debug] running research synchronously "
            f"dataset_id={dataset_id} type={research_type.value}",
            flush=True,
        )
        research, job = get_research_service().ensure_research(dataset_id, force=force, research_type=research_type)
        return json_response(ResearchResponse(research=research, job=job))

    service = get_research_service()
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
        threading.Thread(
            target=_run_research_background,
            args=(services, job.id, dataset_id, force, research_type),
            daemon=True,
        ).start()
    return json_response(ResearchResponse(research=research, job=job))


@bp.get("/datasets/<dataset_id>/research")
def get_research(dataset_id: str):
    research_type = _research_type()
    print(
        "[research-debug] research endpoint reached "
        f"method=GET dataset_id={dataset_id} type={research_type.value}",
        flush=True,
    )
    research = get_research_service().get_research(dataset_id, research_type=research_type)
    if research is None:
        return json_response(None)
    return json_response(research)
