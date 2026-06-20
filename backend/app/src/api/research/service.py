from __future__ import annotations

from app.src.jobs import JobRunner
from app.src.models import Job, ResearchArtifact
from app.src.providers import BrowserbaseResearchProvider
from app.src.repositories import InMemoryRepository
from app.src.tracing import Tracer


class ResearchService:
    def __init__(
        self,
        repository: InMemoryRepository,
        research_provider: BrowserbaseResearchProvider,
        jobs: JobRunner,
        tracer: Tracer,
    ) -> None:
        self.repository = repository
        self.research_provider = research_provider
        self.jobs = jobs
        self.tracer = tracer

    def ensure_research(self, dataset_id: str, force: bool = False) -> tuple[ResearchArtifact, Job]:
        dataset = self.repository.get_dataset(dataset_id)
        existing = self.repository.get_research(dataset.id, dataset.language_code)
        if existing is not None and not force:
            job = self.repository.create_job(
                Job(
                    type="research",
                    status="succeeded",
                    progress=100,
                    message="Using cached research",
                    metadata={"dataset_id": dataset.id, "research_id": existing.id, "cached": True},
                )
            )
            return existing, job

        research_holder: dict[str, ResearchArtifact] = {}

        def callback(job: Job) -> dict:
            del job
            samples = [item.text for item in self.repository.list_items(dataset.id)[:20]]
            with self.tracer.span("research.create", dataset_id=dataset.id, language=dataset.language_code):
                artifact = self.research_provider.create_research(dataset, samples)
            saved = self.repository.save_research(artifact)
            research_holder["artifact"] = saved
            return {"dataset_id": dataset.id, "research_id": saved.id, "cached": False}

        job = self.jobs.run("research", callback)
        artifact = research_holder.get("artifact")
        if artifact is None:
            raise RuntimeError(job.error or "Research job failed before producing an artifact.")
        return artifact, job

    def get_research(self, dataset_id: str) -> ResearchArtifact | None:
        dataset = self.repository.get_dataset(dataset_id)
        return self.repository.get_research(dataset.id, dataset.language_code)
