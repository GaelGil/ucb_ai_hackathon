from __future__ import annotations

from collections.abc import Callable

from app.src.models import Job, JobStatus
from app.src.repositories import InMemoryRepository
from app.src.tracing import Tracer


class JobRunner:
    def __init__(self, repository: InMemoryRepository, tracer: Tracer) -> None:
        self.repository = repository
        self.tracer = tracer

    def run(self, job_type: str, callback: Callable[[Job], dict | None]) -> Job:
        job = self.repository.create_job(Job(type=job_type))
        self.repository.update_job(job.id, status=JobStatus.RUNNING, progress=5, message="Started")
        try:
            with self.tracer.span("job.run", job_id=job.id, job_type=job_type):
                metadata = callback(job) or {}
            return self.repository.update_job(
                job.id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                message="Completed",
                metadata={**self.repository.get_job(job.id).metadata, **metadata},
            )
        except Exception as exc:
            return self.repository.update_job(
                job.id,
                status=JobStatus.FAILED,
                progress=100,
                message="Failed",
                error=str(exc),
            )
