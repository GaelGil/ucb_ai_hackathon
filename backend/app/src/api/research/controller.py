from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.src.api.dependencies import get_research_service
from app.src.api.research.service import ResearchService
from app.src.database.models.research import ResearchType
from app.src.models import ResearchArtifact, ResearchResponse


router = APIRouter()


@router.post("/datasets/{dataset_id}/research", response_model=ResearchResponse)
def create_research(
    dataset_id: str,
    service: ResearchService = Depends(get_research_service),
    force: bool = Query(default=False),
    research_type: ResearchType = Query(default=ResearchType.pos, alias="type"),
) -> ResearchResponse:
    research, job = service.ensure_research(dataset_id, force=force, research_type=research_type)
    return ResearchResponse(research=research, job=job)


@router.get("/datasets/{dataset_id}/research", response_model=ResearchArtifact | None)
def get_research(
    dataset_id: str,
    service: ResearchService = Depends(get_research_service),
    research_type: ResearchType = Query(default=ResearchType.pos, alias="type"),
) -> ResearchArtifact | None:
    return service.get_research(dataset_id, research_type=research_type)
