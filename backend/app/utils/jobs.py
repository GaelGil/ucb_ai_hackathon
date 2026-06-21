from __future__ import annotations

from collections.abc import Callable

from sqlmodel import Session

from app.utils.mappers import job_to_api
from app.database.models.job import Job as DbJob
from app.database.models.job import JobStatus as DbJobStatus
from app.database.models.language import now_utc
from app.schemas import Job
from app.integrations.tracing import Tracer


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

    def create_failed(
        self,
        job_type: str,
        error: str,
        metadata: dict | None = None,
        message: str = "Failed",
    ) -> Job:
        job = DbJob(
            type=job_type,
            status=DbJobStatus.failed,
            progress=100,
            message=message,
            error=error,
            job_metadata=metadata or {},
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job_to_api(job)

    def create_running(
        self,
        job_type: str,
        metadata: dict | None = None,
        message: str = "Started",
        progress: int = 5,
    ) -> Job:
        job = DbJob(
            type=job_type,
            status=DbJobStatus.running,
            progress=progress,
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
        return self.run_existing(db_job.id, callback)

    def run_existing(self, job_id: str, callback: Callable[[Job], dict | None]) -> Job:
        db_job = self.session.get(DbJob, job_id)
        if db_job is None:
            raise RuntimeError(f"Job {job_id} was not found.")
        db_job.status = DbJobStatus.running
        db_job.progress = max(db_job.progress, 5)
        db_job.updated_at = now_utc()
        self.session.add(db_job)
        self.session.commit()
        self.session.refresh(db_job)
        job = job_to_api(db_job)
        try:
            with self.tracer.span("job.run", job_id=job.id, job_type=job.type):
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
            persisted.job_metadata = {**(persisted.job_metadata or {}), "error": str(exc)}
            persisted.updated_at = now_utc()
            self.session.commit()
            self.session.refresh(persisted)
            return job_to_api(persisted)
