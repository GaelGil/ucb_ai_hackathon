from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.src.api.dependencies import get_research_service
from app.src.api.research.service import ResearchService
from app.src.models import ResearchResponse


router = APIRouter()


@router.post("/datasets/{dataset_id}/research", response_model=ResearchResponse)
def create_research(
    dataset_id: str,
    service: ResearchService = Depends(get_research_service),
    force: bool = Query(default=False),
) -> ResearchResponse:
    research, job = service.ensure_research(dataset_id, force=force)
    return ResearchResponse(research=research, job=job)


@router.get("/datasets/{dataset_id}/research")
def get_research(dataset_id: str, service: ResearchService = Depends(get_research_service)):
    research = service.get_research(dataset_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Research has not been generated for this dataset.")
    return research


#TODO: See google doc for reference
# Implement two endpoints
# endpoit calls agents
# angent returns list of sentences
# another one returns notes on a language.