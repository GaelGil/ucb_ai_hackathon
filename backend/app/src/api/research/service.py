from __future__ import annotations

from sqlmodel import Session, select

from app.src.api.mappers import dataset_to_api, research_to_api
from app.src.database.models import DataRow, Dataset, Research
from app.src.database.models.research import ResearchType
from app.src.jobs import JobRunner
from app.src.models import Job, ResearchArtifact
from app.src.providers import BrowserbaseResearchProvider
from app.src.repositories import NotFoundError
from app.src.tracing import Tracer


class ResearchService:
    def __init__(
        self,
        session: Session,
        research_provider: BrowserbaseResearchProvider,
        jobs: JobRunner,
        tracer: Tracer,
    ) -> None:
        self.session = session
        self.research_provider = research_provider
        self.jobs = jobs
        self.tracer = tracer

    def ensure_research(
        self,
        dataset_id: str,
        force: bool = False,
        research_type: ResearchType = ResearchType.pos,
    ) -> tuple[ResearchArtifact, Job]:
        dataset = self._get_dataset(dataset_id)
        existing = self._get_research_row(dataset.language_id, research_type)
        if existing is not None and not force:
            api_research = research_to_api(dataset, dataset.language, existing)
            warnings = existing.research_metadata.get("warnings", [])
            job = self.jobs.create_succeeded(
                "research",
                metadata={
                    "dataset_id": dataset.id,
                    "research_id": existing.id,
                    "research_type": research_type.value,
                    "cached": True,
                    "used_fallback": bool(warnings),
                    "warnings": warnings,
                },
                message="Using cached research",
            )
            return api_research, job

        research_holder: dict[str, Research] = {}

        def callback(job: Job) -> dict:
            del job
            samples = [
                row.text_content
                for row in self.session.exec(
                    select(DataRow).where(DataRow.dataset_id == dataset.id).where(DataRow.text_content.is_not(None)).limit(20)
                ).all()
                if row.text_content
            ]
            with self.tracer.span("research.create", dataset_id=dataset.id, language=dataset.language.code):
                artifact = self.research_provider.create_research(dataset_to_api(dataset), samples, research_type.value)
            warnings = [warning.model_dump(mode="json") for warning in artifact.warnings]
            if warnings:
                with self.tracer.span(
                    "provider.fallback",
                    dataset_id=dataset.id,
                    provider=warnings[0].get("provider"),
                    stage=warnings[0].get("stage"),
                    research_type=research_type.value,
                ):
                    pass

            row = existing or Research(language_id=dataset.language_id, type=research_type)
            row.notes = artifact.summary
            row.sources = [source.model_dump() for source in artifact.sources]
            row.research_metadata = {
                "guidelines": artifact.guidelines,
                "dataset_id": dataset.id,
                "research_type": research_type.value,
                "used_fallback": bool(warnings),
                "warnings": warnings,
            }
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            research_holder["row"] = row
            return {
                "dataset_id": dataset.id,
                "research_id": row.id,
                "research_type": research_type.value,
                "cached": False,
                "used_fallback": bool(warnings),
                "warnings": warnings,
            }

        job = self.jobs.run("research", callback)
        row = research_holder.get("row")
        if row is None:
            raise RuntimeError(job.error or "Research job failed before producing an artifact.")
        return research_to_api(dataset, dataset.language, row), job

    def get_research(self, dataset_id: str, research_type: ResearchType = ResearchType.pos) -> ResearchArtifact | None:
        dataset = self._get_dataset(dataset_id)
        row = self._get_research_row(dataset.language_id, research_type)
        return research_to_api(dataset, dataset.language, row) if row else None

    def _get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
        return dataset

    def _get_research_row(self, language_id: str, research_type: ResearchType) -> Research | None:
        return self.session.exec(
            select(Research).where(Research.language_id == language_id).where(Research.type == research_type)
        ).first()
