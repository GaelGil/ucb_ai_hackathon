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
            api_research, job = self._cached_research_response(dataset, existing, research_type)
            return api_research, job

        research_holder: dict[str, Research] = {}

        def callback(job: Job) -> dict:
            del job
            row, metadata = self._generate_research_row(dataset, existing, research_type)
            research_holder["row"] = row
            return metadata

        job = self.jobs.run("research", callback)
        row = research_holder.get("row")
        if row is None:
            raise RuntimeError(job.error or "Research job failed before producing an artifact.")
        return research_to_api(dataset, dataset.language, row), job

    def queue_research(
        self,
        dataset_id: str,
        force: bool = False,
        research_type: ResearchType = ResearchType.pos,
    ) -> tuple[ResearchArtifact | None, Job]:
        dataset = self._get_dataset(dataset_id)
        existing = self._get_research_row(dataset.language_id, research_type)
        if existing is not None and not force:
            return self._cached_research_response(dataset, existing, research_type)
        job = self.jobs.create_running(
            "research",
            metadata={
                "dataset_id": dataset.id,
                "research_type": research_type.value,
                "cached": False,
                "provider": getattr(self.research_provider, "provider", "browserbase"),
                "model": getattr(self.research_provider, "model_name", None),
            },
            message="Research started",
        )
        return None, job

    def complete_queued_research(
        self,
        *,
        job_id: str,
        dataset_id: str,
        force: bool = False,
        research_type: ResearchType = ResearchType.pos,
    ) -> Job:
        dataset = self._get_dataset(dataset_id)
        existing = self._get_research_row(dataset.language_id, research_type)
        if existing is not None and not force:
            return self.jobs.create_succeeded(
                "research",
                metadata={
                    "dataset_id": dataset.id,
                    "research_id": existing.id,
                    "research_type": research_type.value,
                    "cached": True,
                },
                message="Using cached research",
            )

        def callback(job: Job) -> dict:
            del job
            _, metadata = self._generate_research_row(dataset, existing, research_type)
            return metadata

        return self.jobs.run_existing(job_id, callback)

    def get_research(self, dataset_id: str, research_type: ResearchType = ResearchType.pos) -> ResearchArtifact | None:
        dataset = self._get_dataset(dataset_id)
        row = self._get_research_row(dataset.language_id, research_type)
        return research_to_api(dataset, dataset.language, row) if row else None

    def _cached_research_response(
        self, dataset: Dataset, existing: Research, research_type: ResearchType
    ) -> tuple[ResearchArtifact, Job]:
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

    def _generate_research_row(
        self, dataset: Dataset, existing: Research | None, research_type: ResearchType
    ) -> tuple[Research, dict]:
        samples = [
            row.text_content
            for row in self.session.exec(
                select(DataRow).where(DataRow.dataset_id == dataset.id).where(DataRow.text_content.is_not(None)).limit(20)
            ).all()
            if row.text_content
        ]
        with self.tracer.span(
            "research.create",
            dataset_id=dataset.id,
            language=dataset.language.code,
            research_type=research_type.value,
        ):
            artifact = self.research_provider.create_research(dataset_to_api(dataset), samples, research_type.value)
        evaluation = self._evaluate_research(dataset, samples, artifact, research_type)
        if evaluation:
            artifact.metadata["evaluation"] = evaluation
            self.tracer.record_evaluation(
                f"{research_type.value}_research_quality",
                evaluation,
                dataset_id=dataset.id,
                language=dataset.language.code,
                research_type=research_type.value,
            )
        warnings = [warning.model_dump(mode="json") for warning in artifact.warnings]
        row = existing or Research(language_id=dataset.language_id, type=research_type)
        row.notes = artifact.summary
        row.sources = [source.model_dump() for source in artifact.sources]
        row.research_metadata = {
            **artifact.metadata,
            "guidelines": artifact.guidelines,
            "dataset_id": dataset.id,
            "research_type": research_type.value,
            "used_fallback": bool(warnings),
            "warnings": warnings,
        }
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row, {
            "dataset_id": dataset.id,
            "research_id": row.id,
            "research_type": research_type.value,
            "cached": False,
            "used_fallback": bool(warnings),
            "warnings": warnings,
            "provider": row.research_metadata.get("provider"),
            "model": row.research_metadata.get("model"),
            "source_count": len(row.sources),
            "evaluation": row.research_metadata.get("evaluation"),
        }

    def _evaluate_research(
        self,
        dataset: Dataset,
        samples: list[str],
        artifact: ResearchArtifact,
        research_type: ResearchType,
    ) -> dict:
        evaluator = getattr(self.research_provider, "evaluate_research", None)
        if evaluator is None:
            return artifact.metadata.get("evaluation") if isinstance(artifact.metadata.get("evaluation"), dict) else {}
        try:
            return evaluator(dataset_to_api(dataset), samples, artifact, research_type.value)
        except Exception as exc:
            return {"name": f"{research_type.value}_research_quality", "kind": "llm", "label": "error", "feedback": str(exc)}

    def _get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
        return dataset

    def _get_research_row(self, language_id: str, research_type: ResearchType) -> Research | None:
        return self.session.exec(
            select(Research).where(Research.language_id == language_id).where(Research.type == research_type)
        ).first()
