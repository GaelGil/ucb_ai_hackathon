from __future__ import annotations

from collections.abc import Callable

from sqlmodel import Session

from app.src.api.mappers import job_to_api
from app.src.database.models.job import Job as DbJob
from app.src.database.models.job import JobStatus as DbJobStatus
from app.src.database.models.language import now_utc
from app.src.models import Job
from app.src.tracing import Tracer


class JobRunner:
    def __init__(self, session: Session, tracer: Tracer) -> None:
        self.session = session
        self.tracer = tracer

    def create_succeeded(self, job_type: str, metadata: dict | None = None, message: str = "Completed") -> Job:
        job = DbJob(
            type=job_type,
            status=DbJobStatus.succeeded,
            progress=100,
            message=message,
            job_metadata=metadata or {},
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job_to_api(job)

    def run(self, job_type: str, callback: Callable[[Job], dict | None]) -> Job:
        db_job = DbJob(type=job_type, status=DbJobStatus.running, progress=5, message="Started")
        self.session.add(db_job)
        self.session.commit()
        self.session.refresh(db_job)
        job = job_to_api(db_job)
        try:
            with self.tracer.span("job.run", job_id=job.id, job_type=job_type):
                metadata = callback(job) or {}
            persisted = self.session.get(DbJob, job.id)
            if persisted is None:
                persisted = db_job
                self.session.add(persisted)
            persisted.status = DbJobStatus.succeeded
            persisted.progress = 100
            persisted.message = "Completed"
            persisted.error = None
            persisted.job_metadata = {**persisted.job_metadata, **metadata}
            persisted.updated_at = now_utc()
            self.session.commit()
            self.session.refresh(persisted)
            return job_to_api(persisted)
        except Exception as exc:
            self.session.rollback()
            persisted = self.session.get(DbJob, job.id)
            if persisted is None:
                persisted = db_job
                self.session.add(persisted)
            persisted.status = DbJobStatus.failed
            persisted.progress = 100
            persisted.message = "Failed"
            persisted.error = str(exc)
            persisted.updated_at = now_utc()
            self.session.commit()
            self.session.refresh(persisted)
            return job_to_api(persisted)
